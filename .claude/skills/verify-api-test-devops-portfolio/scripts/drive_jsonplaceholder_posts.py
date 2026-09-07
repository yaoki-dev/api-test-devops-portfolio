#!/usr/bin/env python3
"""Drive the public read-only JSONPlaceholder Posts path and emit bounded evidence."""

from __future__ import annotations

import json

from utils.jsonplaceholder_client_sync import SyncJSONPlaceholderClient


def main() -> None:
    """Fetch one post and a filtered list through the public synchronous client."""
    print(json.dumps({"action": "get_post", "endpoint": "/posts/1"}, sort_keys=True))
    with SyncJSONPlaceholderClient() as client:
        post = client.get_post(1)
        posts = client.get_posts(limit=2, user_id=1)

    assert post.id == 1
    assert post.user_id == 1
    assert 0 < len(posts) <= 2
    assert all(item.user_id == 1 for item in posts)

    evidence = {
        "action": "get_posts",
        "filter": {"limit": 2, "user_id": 1},
        "result": {
            "post_id": post.id,
            "post_model": type(post).__name__,
            "filtered_count": len(posts),
            "all_filtered_results_match_user_id": all(item.user_id == 1 for item in posts),
        },
        "verification_status": "passed",
    }
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
