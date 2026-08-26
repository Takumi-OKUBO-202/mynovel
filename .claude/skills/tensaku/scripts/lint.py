#!/usr/bin/env python3
"""単話添削用の機械チェック。

使い方: python3 .claude/skills/tensaku/scripts/lint.py manuscript/part01/ep012.md [ep013.md ...]

出すのは材料であって結論ではない。ヒットした箇所は必ず本文を開いて文脈で判断する。
"""
import re
import sys

# 近接反復を数える語(CLAUDE.md「語の重複チェック」)
HEDGES = ["らしい", "らしき", "ようだ", "みたいだ", "だろう", "あっさり",
          "という感覚", "感覚", "なのに", "というより", "ずいぶん", "妙に",
          "思わず", "気がした", "どこか"]
# 指示語(遠い指示語・中身のない指示語の手がかり。ヒット自体は正常)
DEICTICS = ["その", "それ", "そこ", "この"]


def body_of(path):
    t = open(path, encoding="utf-8").read()
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"```.*?```", "", t, flags=re.S)
    return t


def check(path):
    t = body_of(path)
    chars = len("".join(t.split()))
    lines = t.split("\n")
    paras = [p.strip() for p in lines if p.strip()]

    print(f"== {path}")
    print(f"文字数(空白除く): {chars}")
    if chars > 4600:
        print("  ★ 4,000字目安を大きく超過。削るか分割を検討")

    # 「た。」で終わる段落の連続(地の文のみ。会話文・◇はリセット)
    run = 0
    best = 0
    for p in paras:
        if p == "◇" or p.startswith("「") or p.startswith("『"):
            run = 0
            continue
        if p.endswith("た。"):
            run += 1
            best = max(best, run)
            if run == 4:
                print(f"  ★ た。終わり段落が4連続: …{p[:28]}")
        else:
            run = 0

    # 4文以上の段落(地の文のみ)
    for p in paras:
        if p == "◇" or p.startswith("「"):
            continue
        n = len(re.findall(r"。", p))
        if n >= 4:
            print(f"  ★ {n}文の段落: {p[:36]}…")

    # アラビア数字・数値の混入(レベル表記等は本文では漢数字/「Lv」表記を確認)
    for i, ln in enumerate(lines, 1):
        for m in re.finditer(r"[0-90-9]+", ln):
            print(f"  ★ 数字の混入 L{i}: …{ln.strip()[:40]}")
            break

    # 語の反復
    for w in HEDGES:
        n = len(re.findall(re.escape(w), t))
        if (w in ("感覚", "なのに", "というより") and n >= 1) or n >= 2:
            print(f"  ・「{w}」 {n}回 → 各出現を目視で判定")

    # 副詞らしき「〜と、」「〜り」語の頻出上位(同じ副詞の繰り返し検出の補助)
    adverbs = re.findall(r"[ぁ-ん]{2,4}(?:と|り)(?=、)", t)
    from collections import Counter
    for w, n in Counter(adverbs).most_common():
        if n >= 3:
            print(f"  ・副詞候補「{w}」 {n}回")

    # 空行の連続(2連=◇の前後、3連=一拍の間。4連以上は事故)
    blank = 0
    for i, ln in enumerate(lines, 1):
        if ln.strip() == "":
            blank += 1
        else:
            if blank >= 4:
                print(f"  ★ 空行{blank}連続 (L{i}の直前)")
            blank = 0

    # ◇の書式(前後空行2つ+全角スペース4つ)
    for i, ln in enumerate(lines, 1):
        if ln.strip() == "◇" and ln != "　　　　◇":
            print(f"  ★ ◇の書式が規定と違う L{i}: {ln!r}")

    print()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        check(p)
