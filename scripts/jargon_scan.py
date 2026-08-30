#!/usr/bin/env python3
"""jargon_scan.py — 禁用词双范围扫描（LaTeX 源码 + PDF 渲染文本）。

用途：词汇轮的清零验收。必须同时扫源码和 pdftotext 抽取的可见文本——
图内标签由绘图脚本继承变量名，是行话残留的最高发区，且在源码里 grep 不到。
（见 references/03-diction.md）

模式文件格式：一行一个正则；空行和 # 开头的行忽略；
              也接受一整行 alternation（a|b|c），按整体正则处理。

用法:
    python jargon_scan.py --patterns banned.txt --tex sections_zh --pdf dist/r22_full.pdf
    python jargon_scan.py --patterns banned.txt --tex sections_zh --tex si --case-sensitive
    python jargon_scan.py --patterns banned.txt --pdf main.pdf --context 1

输出: 每个命中给 来源:行号: 匹配文本，并按范围汇总命中数。
      末尾打印可粘进交付说明的 PROOF 块（含模式数、范围、命中数、退出码）。

退出码: 0 = 零命中（清零通过）, 1 = 有命中, 2 = 环境或用法错误

注意两个已知盲区（脚本无法覆盖，必须人工补）：
  1. 位图图片与已转曲文字不会被 pdftotext 抽出 —— 这类图需逐页目检。
  2. 换行会切断短语造成假阴性 —— 命中 0 时用更短的片段复查一次。
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_patterns(path: Path) -> list[str]:
    pats = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pats.append(line)
    return pats


def pdf_to_text(pdf: Path) -> str:
    if shutil.which("pdftotext") is None:
        print("ERROR: 找不到 pdftotext，请安装 poppler-utils 或 xpdf", file=sys.stderr)
        raise SystemExit(2)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
        out = Path(tf.name)
    try:
        r = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), str(out)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"ERROR: pdftotext 失败 ({pdf}): {r.stderr.strip()}", file=sys.stderr)
            raise SystemExit(2)
        return out.read_text(encoding="utf-8", errors="replace")
    finally:
        out.unlink(missing_ok=True)


def collect_tex(paths, glob):
    """返回 (files, missing)。missing 非空时 main 会硬失败——
    路径打错却返回退出码 0 等于发一张什么都没验的合格证。"""
    files = []
    missing = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(p.rglob(glob)))
        elif p.is_file():
            files.append(p)
        else:
            missing.append(p)
    seen = list(dict.fromkeys(f.resolve() for f in files))
    return [Path(f) for f in seen], missing


def strip_comments(text: str) -> str:
    """逐行截断未转义 % 之后的内容，保持行号不变。"""
    out = []
    for line in text.split("\n"):
        i, n, cut = 0, len(line), None
        while i < n:
            c = line[i]
            if c == "\\":
                i += 2
                continue
            if c == "%":
                cut = i
                break
            i += 1
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def strip_envs(text: str, envs, label: str):
    """剥离 LaTeX 注释，再把指定环境的内容抹成等量空行（行号全程不变）。

    典型用途：--exclude-env algorithmic。中文母稿的伪代码体按期刊惯例写英文
    （见 references/10-chinese.md §六），那里的英文不是行话残留。

    **注释必须先剥掉再剥环境**：一个被注释掉的 \\begin{algorithmic} 会让非贪婪
    匹配从它开始一路吞到下一个真实 \\end，把中间的正文连同真行话一起静默排除，
    退出码照样是 0。剥注释同时意味着 .tex 注释里的行话不计入命中——注释不是
    读者可见文本，这是想要的行为。

    返回 (text, warnings)。\\begin 与 \\end 数量不等时**跳过该环境的剥离**并告警：
    宁可假阳性，不要假通过。
    """
    warnings = []
    text = strip_comments(text)          # 先剥注释，剥离与计数都基于同一份文本
    for env in envs:
        nb = len(re.findall(r"\\begin\{" + re.escape(env) + r"\*?\}", text))
        ne = len(re.findall(r"\\end\{" + re.escape(env) + r"\*?\}", text))
        if nb != ne:
            warnings.append(f"{label}: 环境 {env} 的 \\begin({nb}) 与 \\end({ne}) 不配平，"
                            f"跳过剥离（该文件按未排除处理）")
            continue
        rx = re.compile(
            r"\\begin\{" + re.escape(env) + r"\*?\}.*?\\end\{" + re.escape(env) + r"\*?\}",
            re.S,
        )
        text = rx.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return text, warnings


def scan(label: str, text: str, regexes, context: int) -> list[str]:
    lines = text.splitlines()
    hits = []
    for i, line in enumerate(lines, 1):
        for pat, rx in regexes:
            for m in rx.finditer(line):
                hits.append(f"{label}:{i}: [{pat}] -> {m.group(0)!r}")
                if context:
                    lo, hi = max(0, i - 1 - context), min(len(lines), i + context)
                    for j in range(lo, hi):
                        mark = ">" if j == i - 1 else " "
                        hits.append(f"    {mark} {j + 1}: {lines[j].strip()}")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--patterns", type=Path, required=True, help="禁用词模式文件")
    ap.add_argument("--tex", type=Path, action="append", default=[],
                    help="源码文件或目录，可重复")
    ap.add_argument("--pdf", type=Path, action="append", default=[],
                    help="渲染 PDF，可重复")
    ap.add_argument("--glob", default="*.tex", help="目录递归时的文件名模式（默认 *.tex）")
    ap.add_argument("--exclude-env", action="append", default=[], metavar="ENV",
                    help="扫描源码时排除该 LaTeX 环境的内容（如 algorithmic），可重复；"
                         "只作用于 --tex，PDF 侧无法排除")
    ap.add_argument("--case-sensitive", action="store_true", help="区分大小写（默认不区分）")
    ap.add_argument("--context", type=int, default=0, help="命中行前后各显示 N 行")
    args = ap.parse_args()

    if not args.patterns.is_file():
        print(f"ERROR: 模式文件不存在: {args.patterns}", file=sys.stderr)
        return 2
    if not args.tex and not args.pdf:
        print("ERROR: 至少要给一个 --tex 或 --pdf 扫描范围", file=sys.stderr)
        return 2
    if not args.pdf:
        print("WARN: 未给 --pdf。只扫源码会漏掉图内标签——那是行话残留的最高发区。",
              file=sys.stderr)

    pats = load_patterns(args.patterns)
    if not pats:
        print(f"ERROR: 模式文件为空: {args.patterns}", file=sys.stderr)
        return 2
    flags = 0 if args.case_sensitive else re.IGNORECASE
    try:
        regexes = [(p, re.compile(p, flags)) for p in pats]
    except re.error as e:
        print(f"ERROR: 正则编译失败: {e}", file=sys.stderr)
        return 2

    scopes = []          # (范围名, 文件数, 命中数)
    all_hits = []
    env_warnings = []

    if args.tex:
        tex_files, missing = collect_tex(args.tex, args.glob)
        if missing:
            for p in missing:
                print(f"ERROR: --tex 路径不存在: {p}", file=sys.stderr)
            return 2
        if not tex_files:
            print(f"ERROR: --tex 扫描范围为空（没有匹配 {args.glob} 的文件）——"
                  f"不构成清零证明。", file=sys.stderr)
            return 2
        n = 0
        for f in tex_files:
            body = f.read_text(encoding="utf-8", errors="replace")
            if args.exclude_env:
                body, w = strip_envs(body, args.exclude_env, str(f))
                env_warnings.extend(w)
            h = scan(str(f), body, regexes, args.context)
            all_hits.extend(h)
            n += sum(1 for x in h if not x.startswith("    "))
        excl = f"，已排除环境 {'/'.join(args.exclude_env)}" if args.exclude_env else ""
        scopes.append((f"LaTeX 源码{excl}", len(tex_files), n))

    for pdf in args.pdf:
        if not pdf.is_file():
            print(f"ERROR: PDF 不存在: {pdf}", file=sys.stderr)
            return 2
        h = scan(f"{pdf.name}(text)", pdf_to_text(pdf), regexes, args.context)
        all_hits.extend(h)
        n = sum(1 for x in h if not x.startswith("    "))
        scopes.append((f"PDF 可见文本 {pdf.name}", 1, n))

    if all_hits:
        print("HITS")
        for h in all_hits:
            print(h)
        print()

    total = sum(n for _, _, n in scopes)
    code = 1 if total else 0

    print("=" * 60)
    print("PROOF")
    print(f"  模式数：{len(pats)}")
    print(f"  模式文件：{args.patterns}")
    print("  扫描范围与结果：")
    for name, nfiles, nhits in scopes:
        print(f"    - {name}（{nfiles} 个文件）：匹配数 {nhits}")
    if env_warnings:
        print("  环境剥离告警（这些文件按未排除处理）：")
        for w in env_warnings:
            print(f"    ! {w}")
    print(f"  合计命中：{total}")
    print(f"  退出码：{code}    （0 = 零残留，1 = 存在命中）")
    print("  验收口径：命中数 = 已人工判定豁免数，且每条豁免在交付说明中列出理由。")
    if code == 0:
        print("  提醒：位图/转曲文字不会被 pdftotext 抽出，这类图仍需逐页目检；")
        print("        若某模式为长短语，换更短的片段复查一次以排除换行伪影。")
    else:
        print("  提醒：PDF 侧无法排除 LaTeX 环境。若命中落在英文伪代码体内，")
        print("        按 references/10-chinese.md §六 属规则允许，人工判定后可豁免。")
    print("=" * 60)
    return code


if __name__ == "__main__":
    sys.exit(main())
