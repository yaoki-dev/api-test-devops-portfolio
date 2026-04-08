#!/bin/bash
# CodeGraphContext MCP Server Wrapper (macOS Seatbelt Patch)
# Purpose: Allow binary loading for tree-sitter under Seatbelt

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && git rev-parse --show-toplevel)"
GEMINI_TMP="$PROJECT_ROOT/.gemini/tmp"
DEFAULT_CGC_STATE_BASE="${TMPDIR:-/tmp}/cgc-state"
PROJECT_KEY="$(printf '%s' "$PROJECT_ROOT" | shasum | awk '{print $1}' | cut -c1-12)"
CGC_STATE_DIR="${CGC_STATE_DIR:-${DEFAULT_CGC_STATE_BASE}-${PROJECT_KEY}}"

mkdir -p "$CGC_STATE_DIR"
export FALKORDB_PATH="${FALKORDB_PATH:-$CGC_STATE_DIR/falkordb_data}"
export FALKORDB_SOCKET_PATH="${FALKORDB_SOCKET_PATH:-$CGC_STATE_DIR/falkordb.sock}"
LOCK_DIR="$CGC_STATE_DIR/.lock_cgc_mcp_wrapper"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  OLD_PID="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "[CGC Patch] cgc_mcp_wrapper already running (pid=$OLD_PID), exiting."
    exit 0
  fi
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR"
fi
echo $$ > "$LOCK_DIR/pid"
cleanup_lockdir() { rm -rf "$LOCK_DIR"; }
trap cleanup_lockdir EXIT INT TERM

# 1. Resolve PYTHONPATH for local tree-sitter-language-pack
export PYTHONPATH="$GEMINI_TMP:$PYTHONPATH"

# 2. Configure environment and start MCP server via Python
python -c "
import sys
import os
import threading
import time
from pathlib import Path

# --- Apply Seatbelt Patch ---
libs_path = Path(r'$GEMINI_TMP/tree-sitter-libs')
if libs_path.exists():
    try:
        sys.path.insert(0, r'$GEMINI_TMP')
        from tree_sitter_language_pack import configure
        configure(cache_dir=str(libs_path))
    except Exception:
        pass

# --- Monkeypatch for missing languages (e.g. c_sharp) ---
try:
    from codegraphcontext.tools.graph_builder import TreeSitterParser
    original_parser_init = TreeSitterParser.__init__
    def patched_parser_init(self, language_name):
        try:
            original_parser_init(self, language_name)
        except Exception:
            if language_name in ('python', 'py'):
                raise
            self.language = None
            self.parser = None
    TreeSitterParser.__init__ = patched_parser_init
except ImportError:
    pass

# --- Force watchdog to avoid macOS FSEvents in sandboxed environments ---
try:
    from watchdog.observers.polling import PollingObserver
    import codegraphcontext.core.watcher as watcher_module
    watcher_module.Observer = PollingObserver
except ImportError:
    pass

# --- Align watcher refresh with index-time ignore rules ---
try:
    import pathspec
    from codegraphcontext.cli.config_manager import get_config_value
    from codegraphcontext.tools.graph_builder import DEFAULT_IGNORE_PATTERNS
    from codegraphcontext.tools.handlers import watcher_handlers
    from codegraphcontext.utils.debug_log import info_logger, error_logger

    # Read config once to avoid per-event file I/O under high-frequency changes.
    _IGNORE_HIDDEN = (get_config_value('IGNORE_HIDDEN_FILES') or 'true').lower() == 'true'
    _IGNORE_DIRS = {
        d.strip().lower()
        for d in (get_config_value('IGNORE_DIRS') or '').split(',')
        if d.strip()
    }
    _RECONCILE_INTERVAL_SEC = float(
        os.getenv('CGC_WATCH_RECONCILE_SEC') or (get_config_value('CGC_WATCH_RECONCILE_SEC') or '60')
    )
    _STATE_LOCK = threading.Lock()
    _REFRESH_STATE = {
        'running': False,
        'pending_paths': set(),
        'last_event_ts': 0.0,
        'last_reconcile_ts': 0.0,
    }

    def _load_ignore_spec(repo_path: Path):
        cgcignore_path = None
        ignore_root = repo_path.resolve()
        curr = repo_path.resolve()
        if not curr.is_dir():
            curr = curr.parent

        while True:
            candidate = curr / '.cgcignore'
            if candidate.exists():
                cgcignore_path = candidate
                ignore_root = curr
                break
            if curr.parent == curr:
                break
            curr = curr.parent

        if cgcignore_path:
            with open(cgcignore_path) as f:
                user_patterns = [
                    line.strip() for line in f.read().splitlines()
                    if line.strip() and not line.strip().startswith('#')
                ]
            ignore_patterns = DEFAULT_IGNORE_PATTERNS + user_patterns
        else:
            ignore_patterns = DEFAULT_IGNORE_PATTERNS

        return ignore_root, pathspec.PathSpec.from_lines('gitwildmatch', ignore_patterns)

    def _iter_supported_files(repo_path: Path, graph_builder):
        supported_extensions = graph_builder.parsers.keys()
        files = [f for f in repo_path.rglob('*') if f.is_file() and f.suffix in supported_extensions]

        if _IGNORE_HIDDEN:
            kept_files = []
            for f in files:
                try:
                    parts = f.relative_to(repo_path).parts
                except ValueError:
                    parts = f.parts
                if any(part.startswith('.') for part in parts):
                    continue
                kept_files.append(f)
            files = kept_files

        if _IGNORE_DIRS:
            ignore_dirs = _IGNORE_DIRS
            if ignore_dirs:
                kept_files = []
                for f in files:
                    try:
                        parts = set(p.lower() for p in f.relative_to(repo_path).parent.parts)
                    except ValueError:
                        parts = set()
                    if not parts.intersection(ignore_dirs):
                        kept_files.append(f)
                files = kept_files

        ignore_root, spec = _load_ignore_spec(repo_path)
        filtered_files = []
        for f in files:
            try:
                rel_path = f.relative_to(ignore_root)
            except ValueError:
                filtered_files.append(f)
                continue
            if not spec.match_file(str(rel_path)):
                filtered_files.append(f)
        return filtered_files

    def _patched_initial_scan(self):
        info_logger(f'Performing initial scan for watcher: {self.repo_path}')
        files = _iter_supported_files(self.repo_path, self.graph_builder)
        self.imports_map = self.graph_builder._pre_scan_for_imports(files)
        self.all_file_data = []
        for f in files:
            parsed_data = self.graph_builder.parse_file(self.repo_path, f)
            if 'error' not in parsed_data:
                self.all_file_data.append(parsed_data)
        self.graph_builder._create_all_function_calls(self.all_file_data, self.imports_map)
        self.graph_builder._create_all_inheritance_links(self.all_file_data, self.imports_map)
        info_logger(f'Initial scan and graph linking complete for: {self.repo_path}')

    def _patched_full_handle_modification(self, event_path_str: str):
        with _STATE_LOCK:
            _REFRESH_STATE['pending_paths'].add(event_path_str)
            _REFRESH_STATE['last_event_ts'] = time.monotonic()
            if _REFRESH_STATE['running']:
                info_logger(f'Refresh already running; queued latest event: {event_path_str}')
                return
            _REFRESH_STATE['running'] = True

        while True:
            with _STATE_LOCK:
                pending_paths = list(_REFRESH_STATE['pending_paths'])
                _REFRESH_STATE['pending_paths'].clear()

            if not pending_paths:
                with _STATE_LOCK:
                    _REFRESH_STATE['running'] = False
                return

            try:
                info_logger(
                    f'File change detected, starting full repository refresh for {len(pending_paths)} files.'
                )
                files = _iter_supported_files(self.repo_path, self.graph_builder)
                self.imports_map = self.graph_builder._pre_scan_for_imports(files)
                info_logger('Refreshed global imports map.')
                now = time.monotonic()
                # Fast path: apply only the observed changed files.
                for changed_path in pending_paths:
                    changed_path_obj = Path(changed_path)
                    self.graph_builder.update_file_in_graph(
                        changed_path_obj, self.repo_path, self.imports_map
                    )

                # Safety net: periodically reconcile all files to recover from
                # coalesced/dropped events under burst load.
                need_reconcile = (
                    _REFRESH_STATE['last_reconcile_ts'] == 0.0
                    or (now - _REFRESH_STATE['last_reconcile_ts']) >= _RECONCILE_INTERVAL_SEC
                )
                if need_reconcile:
                    info_logger(
                        f'Running periodic full reconcile (interval={_RECONCILE_INTERVAL_SEC}s).'
                    )
                    for current_path in files:
                        self.graph_builder.update_file_in_graph(
                            current_path, self.repo_path, self.imports_map
                        )
                    _REFRESH_STATE['last_reconcile_ts'] = now

                # Apply explicit deletion updates for removed paths.
                for changed_path in pending_paths:
                    changed_path_obj = Path(changed_path)
                    if not changed_path_obj.exists():
                        self.graph_builder.update_file_in_graph(
                            changed_path_obj, self.repo_path, self.imports_map
                        )

                # Rebuild in-memory file data and link graph globally.
                self.all_file_data = []
                for f in files:
                    parsed_data = self.graph_builder.parse_file(self.repo_path, f)
                    if 'error' not in parsed_data:
                        self.all_file_data.append(parsed_data)
                info_logger('Refreshed in-memory cache of all file data.')
                info_logger('Re-linking the entire graph for calls and inheritance...')
                self.graph_builder._create_all_function_calls(self.all_file_data, self.imports_map)
                self.graph_builder._create_all_inheritance_links(self.all_file_data, self.imports_map)
                info_logger('Graph refresh complete! ✅')
            except Exception as e:
                error_logger(f'Graph refresh failed for pending batch: {e}')

            with _STATE_LOCK:
                has_pending = bool(_REFRESH_STATE['pending_paths'])
                quiet_for = time.monotonic() - _REFRESH_STATE['last_event_ts']
                if has_pending:
                    continue
                # Run a trailing refresh after a short quiet period so that
                # write bursts completed during sync are not missed.
                if quiet_for < 1.0:
                    sleep_sec = 1.0 - quiet_for
                else:
                    _REFRESH_STATE['running'] = False
                    return
            time.sleep(sleep_sec)

    def _patched_watch_directory(code_watcher, list_repositories_func, add_code_func, **args):
        from pathlib import Path

        path = args.get('path')
        if not path:
            return {'error': 'Path is a required argument.'}

        path_obj = Path(path).resolve()
        path_str = str(path_obj)

        if not path_obj.is_dir():
            return {
                'success': True,
                'status': 'path_not_found',
                'message': f\"Path '{path_str}' does not exist or is not a directory.\",
            }

        try:
            if path_str in code_watcher.watched_paths:
                return {'success': True, 'message': f'Already watching directory: {path_str}'}

            indexed_repos_result = list_repositories_func()
            indexed_repos = indexed_repos_result.get('repositories', [])
            is_already_indexed = any(Path(repo['path']).resolve() == path_obj for repo in indexed_repos)

            if is_already_indexed:
                code_watcher.watch_directory(path_str, perform_initial_scan=False)
                return {
                    'success': True,
                    'message': f\"Path '{path_str}' is already indexed. Now watching for live changes.\",
                }

            scan_job_result = add_code_func(path=path_str, is_dependency=False)
            if 'error' in scan_job_result:
                return scan_job_result

            code_watcher.watch_directory(path_str, perform_initial_scan=True)
            return {
                'success': True,
                'message': f\"Path '{path_str}' was not indexed. Started initial scan and now watching for live changes.\",
                'job_id': scan_job_result.get('job_id'),
                'details': 'Use check_job_status to monitor the initial scan.',
            }
        except Exception as e:
            return {'error': f'Failed to start watching directory: {e}'}

    watcher_module.RepositoryEventHandler._initial_scan = _patched_initial_scan
    watcher_module.RepositoryEventHandler._handle_modification = _patched_full_handle_modification
    watcher_handlers.watch_directory = _patched_watch_directory
except Exception as e:
    print(f'[CGC Patch] Failed to align watcher refresh with ignore rules: {e}')

# --- Optional PoC: incremental update strategy for watcher refresh ---
# Default to the upstream full refresh path because it is the only mode verified
# to keep cross-file state consistent for create/modify/delete events.
watch_mode = os.getenv('CGC_WATCH_UPDATE_MODE', 'full').lower()
if watch_mode == 'incremental':
    try:
        from pathlib import Path
        from codegraphcontext.utils.debug_log import info_logger, error_logger

        def patched_handle_modification(self, event_path_str: str):
            modified_path = Path(event_path_str)
            try:
                # Skip unsupported files early.
                if modified_path.exists() and modified_path.suffix not in self.graph_builder.parsers:
                    return
                if (not modified_path.exists()) and modified_path.suffix not in self.graph_builder.parsers:
                    return

                # Keep repository-level imports map generated by initial scan.
                file_data = self.graph_builder.update_file_in_graph(
                    modified_path, self.repo_path, self.imports_map
                )

                # Re-link only the changed file for fast local consistency.
                if file_data and isinstance(file_data, dict) and 'error' not in file_data and 'deleted' not in file_data:
                    self.graph_builder._create_all_function_calls([file_data], self.imports_map)
                    self.graph_builder._create_all_inheritance_links([file_data], self.imports_map)
                    info_logger(f'Incremental graph refresh complete for: {event_path_str}')
            except Exception as e:
                error_logger(f'Incremental graph refresh failed for {event_path_str}: {e}')

        watcher_module.RepositoryEventHandler._handle_modification = patched_handle_modification
        print('[CGC Patch] watcher update mode: incremental')
    except Exception:
        pass
else:
    print(f'[CGC Patch] watcher update mode: {watch_mode} (upstream)')

# --- Start real cgc mcp ---
from codegraphcontext.cli.main import app
sys.argv = ['cgc', 'mcp', 'start']
try:
    app()
except SystemExit:
    pass
"
