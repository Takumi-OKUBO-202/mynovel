#!/usr/bin/env python3
"""対訳ファイルから練習用の音声ファイルを1本作る。

    pip install edge-tts imageio-ffmpeg

    # 第一弾: 日本語 → 間 → 英語 → 間
    python make_audio.py -i phrases.txt -o business-english.mp3

    # 第二弾: 英語だけ。重要表現(通常) → 例文(0.75倍) → 例文(通常)
    python make_audio.py -i phrases2.txt -o business-english-2.mp3 --english-only

くわしくは README.md を参照。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import re
import subprocess
import sys
from collections import Counter, namedtuple
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ひらがな・カタカナ・CJK統合漢字・全角記号
CJK = re.compile(r"[　-ヿ㐀-䶿一-鿿＀-￯]")
RATE = re.compile(r"^[+-]\d+%$")
SECTION = re.compile(r"^#\s*=+\s*(.+?)\s*=+\s*$")

# セクション名にこの語が入っていると、そのセクションは「見出し語の組」と
# 「例文の組」で2組1セットとして扱う(--english-only のときだけ効く)
PATTERN_MARKER = "見出し語"

# 読み上げの推定速度(--dry-run の所要時間見積もりにのみ使う)
JA_CHARS_PER_SEC = 7.0
EN_WORDS_PER_SEC = 2.6

Pair = namedtuple("Pair", "ja en section")
Segment = namedtuple("Segment", "text voice rate pause")


def out(msg: str) -> None:
    """Windows の cp932 コンソールでも落ちないように出力する。"""
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, errors="replace").decode(enc))


# --------------------------------------------------------------------------
# パース
# --------------------------------------------------------------------------

def is_pattern_section(section: str) -> bool:
    return PATTERN_MARKER in section


def parse(path: Path, validate: bool = True, english_only: bool = False) -> list[Pair]:
    """対訳ファイルを読み、(日本語, 英語, セクション名) のリストを返す。

    「#」で始まる行と空行は無視し、残りを上から2行ずつ組にする。
    「# ===== 見出し =====」の形のコメントはセクション名として覚えておく。
    """
    entries: list[tuple[int, str, str]] = []
    section = ""
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = raw.strip()
        if text.startswith("#"):
            found = SECTION.match(text)
            if found:
                section = found.group(1)
            continue
        if text:
            entries.append((lineno, text, section))

    problems: list[str] = []
    if len(entries) % 2 != 0:
        last_no, last_text, _ = entries[-1]
        problems.append(
            f"  行 {last_no}: 行数が奇数です。相方のない行があります -> {last_text}"
        )

    pairs: list[Pair] = []
    for i in range(0, len(entries) - len(entries) % 2, 2):
        (ja_no, ja, sec), (en_no, en, _) = entries[i], entries[i + 1]
        if validate:
            if not CJK.search(ja):
                problems.append(
                    f"  行 {ja_no}: 日本語のはずが日本語の文字がありません -> {ja}"
                )
            if CJK.search(en):
                problems.append(
                    f"  行 {en_no}: 英語のはずが日本語の文字が混じっています -> {en}"
                )
        pairs.append(Pair(ja, en, sec))

    if validate and english_only:
        # 見出し語と例文で2組1セットなので、組数は偶数でなければならない
        for sec, count in Counter(
            p.section for p in pairs if is_pattern_section(p.section)
        ).items():
            if count % 2:
                problems.append(
                    f"  セクション「{sec}」の組数が奇数です({count}組)。"
                    "見出し語と例文で2組1セットです"
                )

    if problems:
        out(f"{path.name} の並びが崩れています:")
        for p in problems[:20]:
            out(p)
        if len(problems) > 20:
            out(f"  ...ほか {len(problems) - 20} 件")
        out("")
        out("2行1組(日本語→英語)の並びを直してから再実行してください。")
        out("意図的な並びであれば --no-validate を付けると無視できます。")
        sys.exit(1)

    return pairs


def group_blocks(pairs: list[Pair], english_only: bool) -> list[tuple[Pair | None, Pair]]:
    """(見出し語, 例文) のブロックに分ける。見出し語がなければ None。

    セクション名に「見出し語」が入っているセクションだけ、
    同じセクション内の2組を1ブロックにまとめる。
    """
    if not english_only:
        return [(None, p) for p in pairs]

    blocks: list[tuple[Pair | None, Pair]] = []
    i = 0
    while i < len(pairs):
        head = pairs[i]
        paired = (
            is_pattern_section(head.section)
            and i + 1 < len(pairs)
            and pairs[i + 1].section == head.section
        )
        if paired:
            blocks.append((head, pairs[i + 1]))
            i += 2
        else:
            blocks.append((None, head))
            i += 1
    return blocks


# --------------------------------------------------------------------------
# 読み上げ用のテキスト整形
# --------------------------------------------------------------------------

def norm_ja(text: str) -> str:
    text = text.replace("〜", "").replace("～", "")
    text = text.replace("／", "、").replace("・", "、")
    return text.strip()


def norm_en(text: str) -> str:
    # 用語集の "A / B" は「スラッシュ」で妙な間が空くので "A, or B" に読み替える
    text = re.sub(r"\s+/\s+", ", or ", text)
    # 先頭の "..., " を落とす("..., if that makes sense." のような断片用)
    text = re.sub(r"^[.…]+\s*,?\s*", "", text)
    # 末尾の三点リーダは普通のピリオドに寄せる
    text = re.sub(r"\s*[.…]{2,}\s*$", ".", text)
    return text.strip()


def rate_factor(rate: str) -> float:
    """'-25%' -> 0.75 のように、読み上げ時間の倍率に直す。"""
    return 1.0 / (1.0 + int(rate.rstrip("%")) / 100.0)


def hhmmss(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600:d}時間{s % 3600 // 60:02d}分{s % 60:02d}秒"


# --------------------------------------------------------------------------
# 音声の組み立て計画
# --------------------------------------------------------------------------

def plan_segments(blocks, args) -> list[Segment]:
    """ブロックの並びを、読み上げる断片の並びに展開する。"""
    segments: list[Segment] = []
    for head, body in blocks:
        if args.english_only:
            if head is not None:
                segments.append(
                    Segment(norm_en(head.en), args.en_voice, args.en_rate, args.pause_key)
                )
            body_en = norm_en(body.en)
            segments.append(Segment(body_en, args.en_voice, args.slow_rate, args.pause_slow))
            segments.append(Segment(body_en, args.en_voice, args.en_rate, args.pause_end))
        else:
            segments.append(
                Segment(norm_ja(body.ja), args.ja_voice, args.ja_rate, args.pause_ja)
            )
            segments.append(
                Segment(norm_en(body.en), args.en_voice, args.en_rate, args.pause_en)
            )
    return segments


def estimate_sec(segments: list[Segment]) -> float:
    total = 0.0
    for seg in segments:
        if CJK.search(seg.text):
            spoken = len(seg.text) / JA_CHARS_PER_SEC
        else:
            spoken = len(seg.text.split()) / EN_WORDS_PER_SEC
        total += spoken / rate_factor(seg.rate) + seg.pause
    return total


def write_script(blocks, path: Path) -> None:
    """音声と同じ順序の日英併記テキストを書き出す。"""
    lines = [
        "# 音声と同じ順序の日英併記テキスト(聞きながら目で追う用)",
        "# 番号は音声の再生順です。",
    ]
    section = None
    for index, (head, body) in enumerate(blocks, start=1):
        if body.section != section:
            section = body.section
            lines += ["", "", f"# ===== {section} =====" if section else ""]
        lines.append("")
        if head is not None:
            lines.append(f"{index:03d}  {head.en}")
            lines.append(f"     {head.ja}")
            lines.append(f"     {body.en}")
            lines.append(f"     {body.ja}")
        else:
            lines.append(f"{index:03d}  {body.en}")
            lines.append(f"     {body.ja}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    out(f"日英併記テキスト: {path}")


# --------------------------------------------------------------------------
# 合成
# --------------------------------------------------------------------------

async def synth_one(seg: Segment, dest: Path, proxy: str | None, sem) -> None:
    """1セグメントを合成して dest に保存する。既にあれば何もしない。"""
    import edge_tts

    if dest.exists() and dest.stat().st_size > 0:
        return

    tmp = dest.with_suffix(".part")
    last_error: Exception | None = None
    async with sem:
        for attempt in range(3):
            try:
                await edge_tts.Communicate(
                    seg.text, seg.voice, rate=seg.rate, proxy=proxy
                ).save(str(tmp))
                if tmp.stat().st_size == 0:
                    raise RuntimeError("空の音声が返りました")
                tmp.replace(dest)
                return
            except Exception as exc:  # noqa: BLE001 - 何が来ても再試行したい
                last_error = exc
                tmp.unlink(missing_ok=True)
                if attempt < 2:
                    await asyncio.sleep(2 ** (attempt + 1))

    raise RuntimeError(f"合成に失敗しました: {seg.text[:40]!r} ({last_error})")


async def synth_all(jobs, proxy: str | None, concurrency: int) -> None:
    sem = asyncio.Semaphore(concurrency)
    done = 0
    total = len(jobs)
    tasks = [asyncio.ensure_future(synth_one(s, d, proxy, sem)) for s, d in jobs]
    try:
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 10 == 0 or done == total:
                out(f"  合成 {done}/{total}")
    finally:
        # 1件でも失敗したら残りを畳む(取得済みの分はキャッシュに残る)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def cache_path(cache_dir: Path, seg: Segment) -> Path:
    key = hashlib.sha256(
        f"{seg.voice}\x00{seg.rate}\x00{seg.text}".encode("utf-8")
    ).hexdigest()
    return cache_dir / f"{key[:24]}.mp3"


# --------------------------------------------------------------------------
# 連結
#
# pydub は長さの取得に ffprobe を必要とするが imageio-ffmpeg は ffmpeg しか
# 同梱しないため、ここでは ffmpeg を直接使う。各セグメントを 24kHz モノラルの
# 生PCMに戻し、無音を挟みながらエンコーダの標準入力へ流し込む。
# --------------------------------------------------------------------------

SAMPLE_RATE = 24000
BYTES_PER_SEC = SAMPLE_RATE * 2  # 16bit モノラル
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def decode_pcm(ffmpeg: str, path: Path) -> bytes:
    proc = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path),
         "-f", "s16le", "-acodec", "pcm_s16le",
         "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(
            f"音声の読み込みに失敗しました: {path}\n"
            f"{proc.stderr.decode('utf-8', 'ignore').strip()}\n"
            "壊れたキャッシュかもしれません。--cache-dir のフォルダを消して再実行してください。"
        )
    return proc.stdout


def silence(seconds: float) -> bytes:
    return b"\x00" * (int(seconds * BYTES_PER_SEC) // 2 * 2)


def build(segments: list[Segment], cache_dir: Path, args) -> None:
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    dest = Path(args.out).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    encoder = subprocess.Popen(
        [ffmpeg, "-v", "error", "-y",
         "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-i", "-",
         "-b:a", args.bitrate, str(dest)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW,
    )

    written = 0
    try:
        head = silence(0.5)  # 頭の余白
        encoder.stdin.write(head)
        written += len(head)
        for i, seg in enumerate(segments, start=1):
            pcm = decode_pcm(ffmpeg, cache_path(cache_dir, seg))
            gap = silence(seg.pause)
            encoder.stdin.write(pcm)
            encoder.stdin.write(gap)
            written += len(pcm) + len(gap)
            if i % 50 == 0 or i == len(segments):
                out(f"  連結 {i}/{len(segments)}")
    finally:
        encoder.stdin.close()
        stderr = encoder.stderr.read().decode("utf-8", "ignore").strip()
        encoder.wait()

    if encoder.returncode != 0:
        raise RuntimeError(f"MP3の書き出しに失敗しました:\n{stderr}")

    out("")
    out(f"完成: {dest}  ({hhmmss(written / BYTES_PER_SEC)} / "
        f"{dest.stat().st_size / 1e6:.1f}MB)")


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="対訳ファイルから練習用のMP3を作る",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("-o", "--out", default="business-english.mp3", help="出力ファイル")
    ap.add_argument("-i", "--input", default=str(HERE / "phrases.txt"), help="対訳ファイル")
    ap.add_argument("--english-only", action="store_true",
                    help="日本語を読み上げず、重要表現→0.75倍→通常速度で英語だけ読む")
    ap.add_argument("--script-out", default=None,
                    help="音声と同じ順序の日英併記テキストの出力先")
    ap.add_argument("--limit", type=int, default=None, help="先頭N項目だけ生成(お試し用)")
    ap.add_argument("--dry-run", action="store_true", help="合成せず項目数と推定時間だけ表示")
    ap.add_argument("--ja-voice", default="ja-JP-NanamiNeural", help="日本語の声")
    ap.add_argument("--en-voice", default="en-US-AndrewNeural", help="英語の声")
    ap.add_argument("--ja-rate", default="+0%", help="日本語の速度(例 -10%%)")
    ap.add_argument("--en-rate", default="+0%", help="英語の通常速度(例 -10%%)")
    ap.add_argument("--slow-rate", default="-25%", help="ゆっくり読むときの速度(0.75倍相当)")
    ap.add_argument("--pause-ja", type=float, default=2.0,
                    help="日本語のあとの無音(秒/--english-only では使わない)")
    ap.add_argument("--pause-en", type=float, default=1.5,
                    help="英語のあとの無音(秒/--english-only では使わない)")
    ap.add_argument("--pause-key", type=float, default=0.8,
                    help="重要表現のあとの無音(秒/--english-only 用)")
    ap.add_argument("--pause-slow", type=float, default=1.0,
                    help="ゆっくり読んだあとの無音(秒/--english-only 用)")
    ap.add_argument("--pause-end", type=float, default=1.8,
                    help="項目の最後の無音(秒/--english-only 用)")
    ap.add_argument("--bitrate", default="64k", help="MP3のビットレート")
    ap.add_argument("--concurrency", type=int, default=4, help="同時に合成する数")
    ap.add_argument("--cache-dir", default=str(HERE / ".cache-tts"), help="合成結果の置き場")
    ap.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY"), help="社内プロキシ")
    ap.add_argument("--no-validate", action="store_true", help="日英の並びの検査を省く")
    args = ap.parse_args()

    for name, value in (("--ja-rate", args.ja_rate), ("--en-rate", args.en_rate),
                        ("--slow-rate", args.slow_rate)):
        if not RATE.match(value):
            out(f"{name} は '+0%' や '-25%' の形式で指定してください(受け取った値: {value})")
            sys.exit(1)

    src = Path(args.input)
    if not src.exists():
        out(f"対訳ファイルが見つかりません: {src}")
        sys.exit(1)

    pairs = parse(src, validate=not args.no_validate, english_only=args.english_only)
    blocks = group_blocks(pairs, args.english_only)
    total_blocks = len(blocks)
    if args.limit:
        blocks = blocks[: args.limit]

    segments = plan_segments(blocks, args)

    out(f"対訳ファイル : {src}")
    out(f"項目数       : {len(blocks)} 項目(ファイル全体では {total_blocks} 項目)")
    if args.english_only:
        out("構成         : 英語のみ。重要表現 → "
            f"例文({args.slow_rate} のゆっくり) → 例文(通常速度)")
    else:
        out(f"構成         : 日本語 → {args.pause_ja}秒 → 英語 → {args.pause_en}秒")
    out(f"声           : "
        f"{args.en_voice if args.english_only else args.ja_voice + ' / ' + args.en_voice}")
    out(f"読み上げ断片 : {len(segments)} 個")
    out(f"推定再生時間 : 約{hhmmss(estimate_sec(segments))}")
    out("")

    if args.script_out:
        write_script(blocks, Path(args.script_out))
        out("")

    if args.dry_run:
        out("--dry-run のため、ここで終了します。")
        return

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    jobs = {cache_path(cache_dir, s): (s, cache_path(cache_dir, s)) for s in segments}
    pending = [j for j in jobs.values() if not j[1].exists()]
    out(f"合成対象 {len(pending)} セグメント(キャッシュ済み {len(jobs) - len(pending)} 件)")

    try:
        if pending:
            asyncio.run(synth_all(pending, args.proxy, args.concurrency))
        out("音声を連結します。")
        build(segments, cache_dir, args)
    except RuntimeError as exc:
        out("")
        out(str(exc))
        out("")
        out("よくある原因:")
        out("  ・edge-tts が古い          -> pip install -U edge-tts")
        out("  ・社内プロキシ配下にいる    -> --proxy http://プロキシ:ポート を付ける")
        out("  ・一時的な接続エラー        -> 同じコマンドを再実行(済んだ分はキャッシュされます)")
        sys.exit(1)


if __name__ == "__main__":
    main()
