---
name: marketing-strategy
description: Use this skill when the user wants to plan, execute, or review the marketing side of the novel — launch timing, which platforms to post to, posting frequency and cadence, title/summary/tag/genre decisions, KPI review of PV and bookmarks, contest calendar planning, or asks whether just posting episodes is enough. Triggers on phrases like "マーケティング戦略", "どこに投稿すべき", "いつ公開する", "更新頻度", "伸びない", "ヒットさせたい", "宣伝".
---

# マーケティング戦略ワークフロー

**作品を「読まれる状態」に置くための工程。** 本文の質を上げる工程(`new-episode`・`episode-review`)とは別物で、どちらかで代替できない。

## 正となるファイル

| ファイル | 役割 |
|---|---|
| `publishing/marketing-strategy.md` | **戦略の正。** 媒体・時期・頻度・KPI・改善課題の決定事項。判断はすべてここに書き戻す |
| `publishing/metrics.md` | 実績の記録。週次で更新する |
| `publishing/submission-log.md` | 応募・打診の履歴 |
| `research/trends/` | 市場リサーチの成果物(`trend-research`スキルが作る) |

**このスキルは戦略を「決める・見直す」工程で、決定事項は必ず`publishing/marketing-strategy.md`に反映する。** 会話の中だけで決めて終わりにしない。

## 使い分け

- 市場そのものを調べる → `trend-research`スキル(`market-researcher`エージェント)
- あらすじ・タイトル・タグの**文章を作る** → `marketing-editor`エージェント
- 新人賞応募・書籍化打診の**実務** → `submission-prep`スキル
- **このスキルは上記を束ねて「次に何をやるか」を決める場所**

## 手順

### A. 現状を測る(必ず最初にやる)

1. `publishing/marketing-strategy.md` を読み、前回決めたことと未着手の項目を確認する
2. `publishing/metrics.md` の直近の実績を確認する。**未公開なら「まだ公開していない」ことを現状として扱う**
3. 本文の在庫を実測する。**話数と字数はエージェントの自己申告ではなく下のスクリプトで測る**

```bash
python3 -c "
import re,glob,os
tot=0
for f in sorted(glob.glob('manuscript/part01/*.md')):
    b=re.sub(r'<!--.*?-->','',open(f).read(),flags=re.S)
    n=len(re.sub(r'\s','',b)); tot+=n
    print(os.path.basename(f), n, (re.search(r'^# (.+)$',b,flags=re.M) or [None,''])[1])
print('TOTAL',tot)
"
ls manuscript/_draft/    # 未確定の在庫
```

### B. 診断する

**入口(読まれ始めるまで)と中身(読み続けてもらえるか)を分けて見る。** 数字が悪いときに本文から直すのは最も遠回りで、多くの場合は入口の問題である。

| 層 | 見るもの | 数字での現れ方 |
|---|---|---|
| 入口 | タイトル・あらすじ・タグ・ジャンル・表紙・投稿時刻 | PVが伸びない |
| 第1話 | 冒頭の掴み・1話目の引き | PVはあるが2話目に進まない |
| 序盤 | 見せ場までの話数・情報量 | 3〜5話で離脱する |
| 継続 | 更新頻度・アークの緩急・カタルシスの収支 | ブクマは増えるが評価が入らない |

**離脱率が最も高い層から順に手を入れる。** 全部を同時に直さない。

### C. 市場側を更新する(必要なときだけ)

前回の`research/trends/`が**1か月以上古い**、または媒体・コンテストの制度が絡む判断をするときだけ、`trend-research`スキルを実行する。**毎回は回さない。**

**コンテストの日程・応募規定は必ず公式で確認する。** 前年の日程は目安にしかならず、記憶や推測で書かない。確認できなかった項目は`publishing/marketing-strategy.md`の「未確認事項」に残す。

### D. 打ち手を決める

`publishing/marketing-strategy.md` の該当セクションを更新する。**新しく決めたことだけでなく、「やらないと決めたこと」も残す**(後で同じ検討を繰り返さないため)。

成果物の文章(タイトル案・あらすじ・タグ案・宣伝文)が必要なときだけ `marketing-editor` エージェントを呼ぶ。**このスキル1回あたりのエージェント呼び出しは最大2回**(`market-researcher` → `marketing-editor`)。

### E. 計測する

公開後は**週1回** `publishing/metrics.md` に記録する。判断基準は同ファイルの「判断基準」節にある。

- 基準を**上回った** → 何が効いたかを`marketing-strategy.md`に記録し、その打ち手を厚くする
- 基準を**下回った** → 上の診断表で層を特定し、**入口から**直す

## 注意

- **数字が動かないことを本文の質の問題だと即断しない。** 未公開・低露出の段階では、そもそも読まれていないだけのことが大半
- **媒体を増やすことは打ち手ではない。** 同時掲載は運用コストが話数×媒体数で増える。増やすなら、その媒体でしか得られないもの(コンテスト・書籍化ルート・収益還元)を先に言語化する
- **規約を確認せずに同時掲載・コンテスト応募を進めない。** 二重投稿の可否、コンテスト応募中の他サイト掲載可否は媒体・賞ごとに違う
- **本文の改稿が必要という結論になった場合、独断で書き換えない。** 改稿はユーザーに確認し、`new-episode`/`episode-review`の工程に戻す
- **CLAUDE.mdの執筆規約(数値を出さない、1話4,000字前後、冗長さの排除)はマーケティング上の理由でも曲げない。** 数字を出さない方針は差別化の一部として扱い、あらすじ・タグで期待値を合わせる方向で解決する
