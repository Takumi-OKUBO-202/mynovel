---
name: trend-research
description: Use this skill when the user wants to research current trends on Narou/Kakuyomu, wants a market report, wants to check whether the story's differentiation points still hold up, or wants to set up periodic (e.g. weekly) trend research. Triggers on phrases like "トレンド調査して", "今なろうで流行ってるものを調べて", "市場リサーチして".
---

# 市場リサーチワークフロー

## 手順

1. `market-researcher` エージェントに調査を依頼し、`research/trends/YYYY-MM-DD.md` にレポートを作成させる
2. 既存の `research/competitors/` の分析があれば合わせて参照し、変化点があれば競合分析ファイルも更新する
3. レポートの「差別化ポイントの検証結果」をユーザーに要約して伝える
4. 必要な軌道修正(タグ変更、次アークの見せ場調整など)があればユーザーと相談し、合意した内容を `plot/outline.md` に反映する

## 定期実行(任意)

ユーザーが「毎週自動でリサーチしてほしい」等、定期実行を希望した場合は、`create_trigger`(Routine)を使って `market-researcher` エージェントを週次で起動する設定を提案する。**ただし、スケジュール実行の作成自体はユーザーの明示的な合意を得てから行う。** 設定例:

- cron: `0 9 * * 1`(毎週月曜9:00 UTC — 日本時間は+9時間なのでJST 18:00相当。ユーザーの希望時刻に合わせて調整する)
- prompt: 「trend-researchスキルを実行し、なろう/カクヨムの最新トレンドを調査してresearch/trends/に記録してください」
