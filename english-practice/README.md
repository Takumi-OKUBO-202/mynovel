# ビジネス英語 リスニング／スピーキング練習用 音声生成

o9 Solutions との要件定義ミーティング向けの日英対訳(222組)を、
**「日本語 → 2秒の間 → 英語 → 1.5秒の間」** の順で読み上げる **MP3を1本** 作ります。

> このディレクトリは小説プロジェクトとは無関係な学習用の資材です。

音声は **お手元のPCで生成してください。** Claude が動いている実行環境からは、
自然な音声を出せるサービス(Microsoft・Google など)への通信が組織のポリシーで遮断されており、
到達できるのは機械的な合成音声だけでした。発音のお手本にならないため、
ローカル実行用のスクリプトをお渡しする形にしています。

---

## Mac での手順

### 1. ターミナルを開く

`Command` + `Space` を押して「ターミナル」と打ち、Enter。黒い(または白い)文字だけの
ウィンドウが出ます。以降はここにコマンドを貼り付けて Enter を押していきます。

### 2. ファイルを取ってくる

次の5行を**まとめてコピーして貼り付け**、Enter。

```bash
mkdir -p ~/Desktop/English && cd ~/Desktop/English
BASE=https://raw.githubusercontent.com/Takumi-OKUBO-202/mynovel/claude/business-japanese-phrases-mjsca4/english-practice
curl -fLO $BASE/make_audio.py
curl -fLO $BASE/phrases.txt
wc -l make_audio.py phrases.txt
```

最後に **`354 make_audio.py`** と **`718 phrases.txt`** と表示されれば成功です。
行数が違う場合は取得に失敗しているので、もう一度実行してください。

> ブラウザやチャットからファイルを保存する方法だと、**ダウンロードに失敗したときに
> エラーページの中身がそのままファイル名だけ正しく保存される**ことがあります
> (実行すると1行目で `SyntaxError` になる)。curl なら失敗が失敗として分かるので確実です。

### 3. 準備(初回だけ)

次の3行を貼り付けて Enter。1〜2分かかります。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install edge-tts imageio-ffmpeg
```

- 1〜2行目 … このフォルダ専用の Python 環境を作る(Mac に元から入っている
  Python を汚さないため。`pip install` が権限エラーで失敗するのも防げます)
- 3行目 … 必要なものを2つ入れる
  - **edge-tts** … Microsoft Edge の読み上げ音声。無料、アカウント登録不要
  - **imageio-ffmpeg** … 音声の連結に使う ffmpeg。これも pip で入るので別途インストールは不要

最後に `Successfully installed ...` と出れば成功です。

### 4. まず1組だけ試す

いきなり全部作らず、声と間の長さを確認してください。

```bash
python make_audio.py --limit 1 -o test.mp3
open test.mp3
```

10秒ほどで `test.mp3` ができ、`open` で再生されます。
「日本語 → 2秒の間 → 英語 → 1.5秒の間」になっているか確認してください。

### 5. 全部作る

```bash
python make_audio.py
open .
```

`business-english.mp3` ができます。222組・**約39分・30MB前後**。
初回は444回ぶんの読み上げを取得するので、**5〜10分**かかります。
`open .` でフォルダが開くので、あとは iPhone に送るなり好きに使ってください。

**途中で止まっても、同じコマンドをもう一度実行すれば続きから再開します**
(取得済みの音声は `.cache-tts/` に貯まります)。

### 6. 第二弾(英語のみ)を作る

第二弾 `phrases2.txt` は**日本語を読み上げません**。日本語が流れると意識が
そちらへ行ってしまうためです。代わりに英語を次の順で読みます。

- **構文**(ファイル前半) … 重要表現(通常速度) → 例文(0.75倍) → 例文(通常速度)
- **場面別フレーズ**(ファイル後半) … 例文(0.75倍) → 例文(通常速度)

```bash
curl -fLO $BASE/phrases2.txt
python make_audio.py -i phrases2.txt -o business-english-2.mp3 --english-only \
  --script-out business-english-2-script.txt
```

181項目・**約26分**。`--script-out` を付けると、**音声とまったく同じ順番・同じ番号**の
日英併記テキストが一緒にできるので、聞きながら目で追えます。

日本語も聞きたい場合は `--english-only` を外せば、第一弾と同じ日→英の形式になります。

### 7. 第一弾と第二弾をつなげた長い版を作る

`-i` に対訳ファイルを**並べた順**につながります。第二弾のあとに第一弾を、
どちらも英語のみの構成で1本にする場合はこうです。

```bash
python make_audio.py -i phrases2.txt phrases.txt -o business-english-full.mp3 \
  --english-only --script-out business-english-full-script.txt
```

403項目・**約1時間1分**。番号は通しで振られ、日英併記テキストの見出しには
どちらのファイル由来かが `phrases2 / ...`、`phrases / ...` と入ります。

第一弾の Part3(業務用語集)も英語だけで読み上げられるので、
用語の聞き取り練習も兼ねられます。

### 次回以降

ターミナルを閉じたあとにもう一度やるときは、この2行から始めてください。

```bash
cd ~/Desktop/English
source .venv/bin/activate
```

---

## 調整のしかた

| やりたいこと | 指定 |
|---|---|
| 英語をゆっくりにする | `--en-rate -15%` |
| 日本語を速くして待ち時間を減らす | `--ja-rate +20%` |
| 英語を考える時間を長くする | `--pause-ja 4` |
| 復唱する時間を作る | `--pause-en 4` |
| 日本語を男声にする | `--ja-voice ja-JP-KeitaNeural` |
| 英語を女声にする | `--en-voice en-US-AvaNeural` |
| 中身を確認するだけ(通信なし) | `--dry-run` |
| 社内プロキシ経由で使う | `--proxy http://proxy.example.com:8080` |

英語のみ(`--english-only`)のときは、間の指定が別になります。

| やりたいこと | 指定 |
|---|---|
| ゆっくり読みをもっと遅くする | `--slow-rate -35%` |
| 重要表現のあとの間を長くする | `--pause-key 1.5` |
| ゆっくりのあとの間を長くする | `--pause-slow 2` |
| 復唱する時間を作る | `--pause-end 4` |
| 音声と同じ順序の日英テキストを出す | `--script-out script.txt` |

初期設定は **日本語＝Nanami(女声)/ 英語＝Andrew(男声)** です。
声を分けてあるのは、聞いていて日本語と英語の切り替わりが分かるようにするためです。

使える声の一覧は次のコマンドで確認できます。

```bash
edge-tts --list-voices
```

`--pause-ja` や声を変えても、**取得済みの音声は再利用されるので作り直しは速いです**
(声や速度を変えたぶんだけ取り直します)。

すべてのオプションは `python make_audio.py --help` で見られます。

---

## 文章を足す・直す

`phrases.txt` を編集するだけです。

```
# 「#」で始まる行は読み上げません(見出し用)

これは我々にとって必須要件です。
This one is a must-have for us.
```

**日本語の行 → 英語の行 の2行1組**、という並びだけ守ってください。
空行・コメント行はいくつ入れても構いません。

`--english-only` のときだけ、もう一つ決まりがあります。
**セクション名に「見出し語」という語が入っているセクション**は、
「見出し語の組」と「例文の組」で**2組1セット**として扱われます
(`phrases2.txt` の `# ===== Part2 よく使う構文(見出し語 → 例文) =====` がこれ)。
そのセクションの組数が奇数だとエラーになります。

並びが崩れると、スクリプトが**崩れた行番号を指摘して停止します**(音声は作りません)。
`--dry-run` を付ければ、通信せずに組数と並びのチェックだけができます。

読み上げのときに以下は自動で調整されます。

- 用語集の `倉庫間移動 / inter-warehouse transfer / stock transfer` のようなスラッシュは
  `inter-warehouse transfer, or stock transfer` と読み替え(「スラッシュ」で間が空くのを防ぐため)
- 日本語の見出し語にある `〜`(`〜のはずだ` など)は読み上げから除去

---

## うまくいかないとき

| 症状 | 対処 |
|---|---|
| `no such file or directory: ~/Desktop/english` | フォルダの場所か名前が違います。Finder でフォルダを右クリック →「"english" をコピー」ではなく、フォルダをターミナルにドラッグ&ドロップするとパスが入ります |
| `command not found: python3` | ターミナルで `xcode-select --install` を実行(Apple の Python が入ります) |
| `pip: command not found` | `source .venv/bin/activate` を実行し忘れています。手順3をやり直してください |
| `externally-managed-environment` | 同上。`.venv` を有効にしてから `pip install` してください |
| 1行目が `<?xml` で `SyntaxError` | ファイルの中身がダウンロードエラーのページになっています。手順2の curl で取り直してください |
| `403` や `No server date in headers` | `pip install -U edge-tts`(トークンの仕様変更で古い版が弾かれます) |
| `403` が何度も出る | 取得が速すぎる可能性があります。`--concurrency 2` を付けて実行 |
| 会社のネットワークで繋がらない | `--proxy http://プロキシ:ポート` を付ける |
| 途中で止まった | 同じコマンドを再実行(キャッシュから再開します) |
| 音がおかしい・途切れる | `.cache-tts/` フォルダを削除して作り直す |
| ペアリングのエラーが出るが意図通り | `--no-validate` を付ける |

上のどれでも直らないときは、ターミナルに出たメッセージをそのまま貼って教えてください。

---

## 元テキストからの修正点

`phrases.txt` は頂いた文章そのままですが、1箇所だけ単語の欠落を補いました。

- 修正前: `Third, transfers have to respect freshness and  dates.`
- 修正後: `Third, transfers have to respect remaining shelf life and best-before dates.`
- 理由: 対応する日本語「鮮度期限と賞味期限を守った移動であること」に対して英語側の語が抜けていたため
