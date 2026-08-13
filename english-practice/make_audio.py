#!/usr/bin/env python3
"""phrases.txt から「日本語 → 間 → 英語 → 間」の音声ファイルを1本作る。

    pip install edge-tts imageio-ffmpeg
    python make_audio.py --limit 1 -o test.mp3   # まず1組だけ試す
    python make_audio.py                          # 全部

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
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 「た」〜「熙」などのCJK統合漢字・ひらがな・カタカナ・全角記号
CJK = re.compile(r"[　-ヿ㐀-䶿一-鿿＀-￯]")
RATE = re.compile(r"^[+-]\d+%$")

# 読み上げの推定速度(--dry-run の所要時間見積もりにのみ使う)
JA_CHARS_PER_SEC = 7.0
EN_WORDS_PER_SEC = 2.6


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

def parse(path: Path, validate: bool = True) -> list[tuple[str, str]]:
    """phrases.txt を読み、(日本語, 英語) の組のリストを返す。

    「#」で始まる行と空行は無視し、残りを上から2行ずつ組にする。
    """
    lines: list[tuple[int, str]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        lines.append((lineno, text))

    problems: list[str] = []
    if len(lines) % 2 != 0:
        last_no, last_text = lines[-1]
        problems.append(
            f"  行 {last_no}: 行数が奇数です。相方のない行があります -> {last_text}"
        )

    pairs: list[tuple[str, str]] = []
    for i in range(0, len(lines) - len(lines) % 2, 2):
        (ja_no, ja), (en_no, en) = lines[i], lines[i + 1]
        if validate:
            if not CJK.search(ja):
                problems.append(
                    f"  行 {ja_no}: 日本語のはずが日本語の文字がありません -> {ja}"
                )
            if CJK.search(en):
                problems.append(
                    f"  行 {en_no}: 英語のはずが日本語の文字が混じっています -> {en}"
                )
        pairs.append((ja, en))

    if problems:
        out(f"{path.name} の日英のペアリングが崩れています:")
        for p in problems[:20]:
            out(p)
        if len(problems) > 20:
            out(f"  ...ほか {len(problems) - 20} 件")
        out("")
        out("2行1組(日本語→英語)の並びを直してから再実行してください。")
        out("意図的な並びであれば --no-validate を付けると無視できます。")
        sys.exit(1)

    return pairs


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


def estimate_sec(ja: str, en: str, pause_ja: float, pause_en: float) -> float:
    return (
        len(ja) / JA_CHARS_PER_SEC
        + len(en.split()) / EN_WORDS_PER_SEC
        + pause_ja
        + pause_en
    )


def hhmmss(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600:d}時間{s % 3600 // 60:02d}分{s % 60:02d}秒"


# --------------------------------------------------------------------------
# 合成
# --------------------------------------------------------------------------

async def synth_one(
    text: str, voice: str, rate: str, dest: Path, proxy: str | None, sem
) -> None:
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
                    text, voice, rate=rate, proxy=proxy
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

    raise RuntimeError(f"合成に失敗しました: {text[:40]!r} ({last_error})")


async def synth_all(jobs, proxy: str | None, concurrency: int) -> None:
    sem = asyncio.Semaphore(concurrency)
    done = 0
    total = len(jobs)
    tasks = [
        asyncio.ensure_future(synth_one(t, v, r, d, proxy, sem)) for t, v, r, d in jobs
    ]
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


def cache_path(cache_dir: Path, voice: str, rate: str, text: str) -> Path:
    key = hashlib.sha256(f"{voice}\x00{rate}\x00{text}".encode("utf-8")).hexdigest()
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


def build(pairs, cache_dir, args) -> None:
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

    gap_ja = silence(args.pause_ja)
    gap_en = silence(args.pause_en)
    written = 0

    try:
        encoder.stdin.write(silence(0.5))  # 頭の余白
        written += len(silence(0.5))
        for i, (ja, en) in enumerate(pairs, start=1):
            ja_pcm = decode_pcm(
                ffmpeg, cache_path(cache_dir, args.ja_voice, args.ja_rate, norm_ja(ja))
            )
            en_pcm = decode_pcm(
                ffmpeg, cache_path(cache_dir, args.en_voice, args.en_rate, norm_en(en))
            )
            for chunk in (ja_pcm, gap_ja, en_pcm, gap_en):
                encoder.stdin.write(chunk)
                written += len(chunk)
            if i % 25 == 0 or i == len(pairs):
                out(f"  連結 {i}/{len(pairs)}")
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
        description="phrases.txt から日英交互の練習用MP3を作る",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("-o", "--out", default="business-english.mp3", help="出力ファイル")
    ap.add_argument("-i", "--input", default=str(HERE / "phrases.txt"), help="対訳ファイル")
    ap.add_argument("--limit", type=int, default=None, help="先頭N組だけ生成(お試し用)")
    ap.add_argument("--dry-run", action="store_true", help="合成せず組数と推定時間だけ表示")
    ap.add_argument("--ja-voice", default="ja-JP-NanamiNeural", help="日本語の声")
    ap.add_argument("--en-voice", default="en-US-AndrewNeural", help="英語の声")
    ap.add_argument("--ja-rate", default="+0%", help="日本語の速度(例 -10%%)")
    ap.add_argument("--en-rate", default="+0%", help="英語の速度(例 -10%%)")
    ap.add_argument("--pause-ja", type=float, default=2.0, help="日本語のあとの無音(秒)")
    ap.add_argument("--pause-en", type=float, default=1.5, help="英語のあとの無音(秒)")
    ap.add_argument("--bitrate", default="64k", help="MP3のビットレート")
    ap.add_argument("--concurrency", type=int, default=4, help="同時に合成する数")
    ap.add_argument("--cache-dir", default=str(HERE / ".cache-tts"), help="合成結果の置き場")
    ap.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY"), help="社内プロキシ")
    ap.add_argument("--no-validate", action="store_true", help="日英ペアリングの検査を省く")
    args = ap.parse_args()

    for name, value in (("--ja-rate", args.ja_rate), ("--en-rate", args.en_rate)):
        if not RATE.match(value):
            out(f"{name} は '+0%' や '-10%' の形式で指定してください(受け取った値: {value})")
            sys.exit(1)

    src = Path(args.input)
    if not src.exists():
        out(f"対訳ファイルが見つかりません: {src}")
        sys.exit(1)

    pairs = parse(src, validate=not args.no_validate)
    total_pairs = len(pairs)
    if args.limit:
        pairs = pairs[: args.limit]

    est = sum(estimate_sec(ja, en, args.pause_ja, args.pause_en) for ja, en in pairs)
    out(f"対訳ファイル : {src}")
    out(f"組数         : {len(pairs)} 組(ファイル全体では {total_pairs} 組)")
    out(f"構成         : 日本語 → {args.pause_ja}秒 → 英語 → {args.pause_en}秒")
    out(f"声           : {args.ja_voice} / {args.en_voice}")
    out(f"推定再生時間 : 約{hhmmss(est)}")
    out("")

    if args.dry_run:
        out("--dry-run のため、ここで終了します。")
        out("最初の3組:")
        for ja, en in pairs[:3]:
            out(f"  JA: {norm_ja(ja)}")
            out(f"  EN: {norm_en(en)}")
            out("")
        return

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    jobs: dict[Path, tuple[str, str, str, Path]] = {}
    for ja, en in pairs:
        for text, voice, rate in (
            (norm_ja(ja), args.ja_voice, args.ja_rate),
            (norm_en(en), args.en_voice, args.en_rate),
        ):
            dest = cache_path(cache_dir, voice, rate, text)
            jobs[dest] = (text, voice, rate, dest)

    pending = [j for j in jobs.values() if not j[3].exists()]
    out(f"合成対象 {len(pending)} セグメント(キャッシュ済み {len(jobs) - len(pending)} 件)")

    try:
        if pending:
            asyncio.run(synth_all(pending, args.proxy, args.concurrency))
        out("音声を連結します。")
        build(pairs, cache_dir, args)
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
