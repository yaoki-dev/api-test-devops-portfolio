#!/usr/bin/env python3
"""
Day 51セクションを正規表現で抽出・置換するスクリプト
Week 9の内容を「プロフィール磨き上げ」から「GitHub Profile最適化」に更新
"""

import re
from pathlib import Path

# ファイルパス
FILE_PATH = Path(
    "/Users/yuta/Yuta/python/api-test-devops-portfolio/docs/プロジェクト再編/ポートフォリオ戦略分析_改善版.md"
)

# Day 51の新しい内容
NEW_DAY51_CONTENT = """## Day 51 (水) - Task 9.3: GitHub Profile最適化

#### 📚 学習サマリー
- **学習内容**:
  - プロフェッショナルなGitHub Profileベストプラクティス（採用担当者視点での評価ポイント）
  - contribution可視化戦略（commit履歴、activity heatmap活用法）
  - pinned repositories選定基準（技術スタック・実装品質・文書化レベル）

- **ポートフォリオ成果物**:
  - [ ] Profile README作成（自己紹介・技術スタック・連絡先情報）
  - [ ] Pinned repositories最適化（6件選定、技術多様性重視）
  - [ ] Contribution可視化（activity graph活性化、緑マス充実化）
  - [ ] 技術タグ整理（言語・フレームワーク・ツールの明示的記載）

#### 📊 時間配分
- **学習時間**: 2H
  - GitHub Profile評価基準学習: 45分
  - contribution可視化戦略学習: 45分
  - pinned repositories選定原則学習: 30分

- **実装時間**: 0H（**Week 9は新規実装ゼロ** - 既存リポジトリの最適化のみ）

**Phase時間配分**:
- **Phase 1（概念理解）**: 2.0H
- **Phase 2（AI協働実装）**: 4.0H
  - AI実装支援: 2.5H（Profile README構成設計、pinned repos選定支援）
  - 自力実装: 1.5H（Profile作成、リポジトリ説明精緻化）

#### 💻 具体的実装内容

**GitHub Profile最適化**:
1. **Profile README作成**:
   - 自己紹介セクション（30-50単語、技術的背景強調）
   - 技術スタックセクション（Python, Docker, CI/CD等の視覚的表示）
   - 連絡先情報（GitHub, LinkedIn, Email）
   - statsバッジ追加（GitHub Stats, Most Used Languages）

2. **Pinned Repositories最適化（6件選定）**:
   - 本プロジェクト（api-test-devops-portfolio）を必ず含める
   - 技術多様性重視（Python, Docker, CI/CD, Testing等）
   - 各リポジトリのREADME品質確認（8.0/10以上）
   - リポジトリ説明文の最適化（1行で技術価値を明示）

3. **Contribution可視化**:
   - Activity graph活性化（緑マス充実化戦略）
   - Commit履歴の整備（コミットメッセージ品質確認）
   - Issue/PR活動の可視化（オープンソース貢献記録）

4. **技術タグ整理**:
   - 言語タグ（Python, Shell等）
   - フレームワークタグ（pytest, Docker, GitHub Actions）
   - ツールタグ（Git, GitHub, Docker Desktop）

#### ✅ チェックポイント
- [ ] Profile README完成（200-300単語、バッジ3つ以上）
- [ ] Pinned repositories 6件選定完了
- [ ] 各リポジトリREADME品質8.0/10以上
- [ ] Activity graph緑マス充実化
- [ ] GitHub Profile品質スコア9.0/10以上

#### 📚 参考リソース
- GitHub Profile Best Practices: プロフェッショナルなProfile作成ガイド
- Awesome GitHub Profile README: Profile READMEインスピレーション集
- GitHub Stats Badges: statsバッジの効果的な活用法

#### 🤖 AI サポート例

**AI依頼テンプレート（Profile README作成）**:
```
「プロフェッショナルなGitHub Profile READMEを作成してください:

**技術背景**:
- Python開発者（APIテスト + DevOps学習中）
- httpx, pytest, Docker, CI/CDの実装経験

**要件**:
1. 自己紹介: 30-50単語、技術的背景強調
2. 技術スタック: Python, Docker, pytest, GitHub Actions
3. GitHub Stats: statsバッジ2つ以上
4. 連絡先: GitHub, Email

**目標**:
- 採用担当者が5秒で技術レベルを把握可能
- 視覚的魅力（バッジ・アイコン活用）
- プロフェッショナル印象」
```

**AI依頼テンプレート（Pinned Repositories選定）**:
```
「Pinned Repositories 6件の選定基準と推奨を提案してください:

**現在のリポジトリ**:
- api-test-devops-portfolio（本プロジェクト、必須含め）
- その他既存リポジトリ

**選定基準**:
1. 技術多様性（Python, Docker, CI/CD等）
2. README品質（8.0/10以上）
3. 実装品質（テスト・文書化レベル）
4. 市場価値への寄与

**目標**:
- 技術スタックの幅広さを証明
- 実装品質の高さを証明
- DevOpsスキルを証明」
```

**AI成果物レビュー観点**:
- [ ] Profile READMEが採用担当者視点で魅力的か
- [ ] Pinned repositoriesが技術多様性を示すか
- [ ] 各リポジトリREADMEが実装品質を証明するか
- [ ] GitHub Profile全体の統一感・プロフェッショナル性

#### 📋 成果物チェックリスト

**必須成果物**:
- [ ] Profile README完成（200-300単語）
- [ ] GitHub Statsバッジ2つ以上
- [ ] Pinned repositories 6件選定
- [ ] 各リポジトリ説明文最適化
- [ ] Activity graph緑マス充実化

**品質基準**:
- [ ] Profile READMEの可読性・魅力性
- [ ] Pinned repositoriesの技術多様性
- [ ] 各リポジトリREADME品質8.0/10以上
- [ ] GitHub Profile品質スコア9.0/10以上
- [ ] 採用担当者の5秒判断で好印象

---
"""


def main():
    """Day 51セクションを更新"""

    # ファイル読み込み
    print(f"📖 Reading file: {FILE_PATH}")
    content = FILE_PATH.read_text(encoding="utf-8")

    # Day 51セクションを正規表現で抽出・置換
    # パターン: "## Day 51" から次の "## Day 52" の直前まで
    pattern = r"## Day 51 \(水\) - Task 9\.3:.*?(?=\n## Day 52 \(木\))"

    # 置換前のマッチ確認
    matches = re.findall(pattern, content, re.DOTALL)
    if not matches:
        print("❌ Error: Day 51 section not found!")
        return

    print(f"✅ Found Day 51 section ({len(matches[0])} characters)")

    # 置換実行
    updated_content = re.sub(pattern, NEW_DAY51_CONTENT.strip(), content, flags=re.DOTALL)

    # ファイル書き込み
    print(f"💾 Writing updated content to: {FILE_PATH}")
    FILE_PATH.write_text(updated_content, encoding="utf-8")

    print("✅ Day 51 section successfully updated!")
    print("\n📝 Updated content:")
    print("-" * 80)
    print("タイトル: GitHub Profile最適化")
    print("学習時間: 2H")
    print("実装時間: 0H (Week 9は新規実装ゼロ)")
    print("成果物: Profile README + Pinned repositories最適化")
    print("-" * 80)


if __name__ == "__main__":
    main()
