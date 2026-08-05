---
name: episode-review
description: Use this skill to run a strict reader-perspective review over several consecutive finished episodes — checking for missing setup, monotony across episodes, whether the emotional beats land, and whether the protagonist keeps losing initiative. Triggers on phrases like "レビューして", "読者視点で見て", "単調になってないか確認して", "厳しく評価して". Also invoked as a mandatory step from the new-episode skill every 3 episodes.
---

# 読者視点レビュー

書き上げた話を**まとめて読者の目で読み直し、離脱しそうな箇所を潰す**工程。`new-episode`スキルの必須工程でもある。

`continuity-editor`が見るのは設定との整合と文章の粗であり、**この工程が見るのは「読み物として成立しているか」**。役割が違うので、どちらかで代替しない。

## 手順

1. **対象を決める**
   - 原則、**直近の連続3話**。1話だけのレビューは行わない(単調さは複数話を横に並べないと判定できないため)
   - あわせて**直前2〜3話**を比較対象として特定する(こちらはレビューしない)

2. **機械チェックを先に流す**
   - 下記スクリプトで、文字数 / 4文以上の段落 / 「〜した。」の連続 / 数値・金額の混入を出す
   - **結果はエージェントに渡す材料であって、結論ではない**

3. **`reader-reviewer` エージェントを呼ぶ**
   - 対象話のパスと、比較対象の直前話のパスを明示して渡す
   - 機械チェックの結果も一緒に渡す

4. **指摘をユーザーに要約報告する**
   - `致命的` / `要修正` / `検討` の三段階で仕分けて伝える
   - 全文を貼らない。**何を直すのかと、なぜ直すのかだけ**を伝える

5. **反映する**
   - `致命的`・`要修正` は本文に反映する
   - `検討` は `HANDOFF.md` の「未対応の改善課題」へ追記し、次回以降に回す(その場で全部やらない)

6. **反映した話数だけ、機械チェックを再実行する**

## 機械チェック

```bash
# 文字数(4,000字前後が目安。短い分には可)と4文以上の段落
for f in manuscript/part01/epNNN.md ...; do python3 -c "
import re, sys
t = open(sys.argv[1]).read()
b = re.sub(r'<!--.*?-->', '', t, flags=re.S); b = re.sub(r'\`\`\`.*?\`\`\`', '', b, flags=re.S)
hits = [i for i, l in enumerate(t.split('\n'), 1) if l.startswith('　') and l.count('。') >= 4]
print(sys.argv[1], '| 文字数', len(b), '| 4文以上の段落', hits or 'なし')
" "$f"; done

# 「〜した。」の連続(戦闘・山場で4以上なら要修正)
python3 -c "
import re, sys
t = re.sub(r'<!--.*?-->', '', open(sys.argv[1]).read(), flags=re.S)
t = re.sub(r'\`\`\`.*?\`\`\`', '', t, flags=re.S)
run = []
for l in [l for l in t.split('\n') if l.startswith('　')]:
    if l.rstrip().endswith('た。'): run.append(l)
    else:
        if len(run) >= 4: print(len(run), '連続:', run[0][:40])
        run = []
" FILE

# 数値・金額の混入(Lv表記と見出しの話数を除く)
python3 -c "
import re, sys
t = re.sub(r'<!--.*?-->', '', open(sys.argv[1]).read(), flags=re.S)
t = re.sub(r'\`\`\`.*?\`\`\`', '', t, flags=re.S)
t = re.sub(r'Lv\d+', '', t); t = re.sub(r'^#.*$', '', t, flags=re.M)
for i, l in enumerate(t.split('\n'), 1):
    if re.search(r'[0-9]|[0-9]|ユン|\bY\b', l): print(i, l.strip()[:80])
" FILE
```

## 注意

- **この工程は省略できない。** `new-episode`の手順から必須で呼ばれる。3話たまったらレビューを通し、**未実行のまま4話目の下書きに入らない**
- **4文以上の段落チェックは誤検出する。** 「泣き声。日食。灰。渇き。飢え。そして——静けさ。」(第17話)のような**意図的な短文リズム**も引っかかる。機械的に割らず、密な説明文かどうかを目で判断する
- **エージェントが自己申告する文字数を鵜呑みにしない。** 過去に1,350字の乖離が起きている。必ず上のスクリプトで実測する
- **「特に問題ありません」だけの報告を受け取らない。** 指摘ゼロで返ってきた場合は、観点ごとの判断根拠が書かれているかを確認する(書かれていなければ差し戻す)
- **足す提案より削る提案を優先する。** 本作の一貫した課題は冗長さであり、レビューを加筆の口実にしない
- 反映によって話の骨格を変える必要が出た場合は、**独断で変えずユーザーに確認する**
