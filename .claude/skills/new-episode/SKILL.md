---
name: new-episode
description: Use this skill when the user wants to write a new episode/chapter of the novel — triggers on phrases like "新しい話を書きたい", "次の話を書く", "第◯話を執筆", "続きを書いて". Orchestrates the full pipeline from plot check through draft, continuity check, proofreading, and updating the bible/foreshadowing tracker.
---

# 新話執筆ワークフロー

新しい話を書く際は、以下の手順を順番に実行する。

## 手順

1. **プロット確認**: `plot/arcs/` に該当話のプロットがあるか確認する。なければユーザーと相談して作成する(`plot/arcs/_template.md`を使う)
2. **下書き生成**: `episode-drafter` エージェントに依頼し、`manuscript/_draft/` に下書きを作成する
3. **整合性チェック**: `continuity-editor` エージェントに下書きをチェックさせる。矛盾が見つかった場合はユーザーに報告し、修正方針を確認してから下書きを修正する
4. **校正**: `proofreader` エージェントで文章面をチェックし、指摘を反映する
5. **確定稿への移動**: 問題がなければ `manuscript/_draft/` から該当する `manuscript/partNN/` へファイルを移動する
6. **設定・伏線の更新**:
   - `bible/timeline.md` に今回のイベントを追記
   - `bible/characters/` の該当キャラに変化があれば「変遷ログ」に追記
   - `plot/foreshadowing.md` に、新たに仕込んだ伏線を追加し、回収した伏線の状態を更新
7. 必要であれば `marketing-editor` エージェントで次話予告文を作成する

## 注意

- 各ステップの成果物(指摘事項など)は必ずユーザーに要約して伝え、次に進んでよいか確認してから進める
- ステップを飛ばして本文だけ量産しない。特に手順6(設定更新)を省略すると、後の話で矛盾が発生しやすい
- **恒久ルール(確定)**: レベルアップ・新スキル・新ステータス項目など「初出の要素」が登場する話数では、`episode-drafter`のセルフチェック項目「新要素の説明不足がないか」を必ず確認する。読者にも主人公にも、何が起きた・何ができるようになったのかが説明不足なまま伝わらず、かつ急な変化に主人公が疑問も持たず順応してしまっていないかを、下書き段階・`continuity-editor`チェック段階の両方で意識する
