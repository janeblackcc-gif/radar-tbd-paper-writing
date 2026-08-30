#!/usr/bin/env python3
"""page_delta.py — 逐页字符数 delta 归因（必要条件检查）。

残差非零**即证明**存在未申报的改动；残差为零**不构成**充分证明——等长改写
不产生 delta。充分性由 09-mechanics.md 的三列对照单 + 源码 git diff 闭合。
（见 references/09-mechanics.md 第六节）

用法:
    python page_delta.py base.pdf new.pdf
    python page_delta.py base.pdf new.pdf -a abstract=+40 -a "section 5.3=+123"
    python page_delta.py base.pdf new.pdf --strip-ws        # 忽略空白差异

依赖: pdftotext（poppler / xpdf）需在 PATH 上。

退出码: 0 = 残差为 0（或未给归因项），1 = 残差非零，2 = 环境或用法错误
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows 控制台默认 GBK，会把中文提示打成乱码
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def extract_pages(pdf: Path, strip_ws: bool) -> list[str]:
    """pdftotext 抽取全文并按换页符切页。"""
    if shutil.which("pdftotext") is None:
        print("ERROR: 找不到 pdftotext，请安装 poppler-utils 或 xpdf", file=sys.stderr)
        raise SystemExit(2)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
        out = Path(tf.name)
    try:
        r = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", str(pdf), str(out)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(f"ERROR: pdftotext 失败 ({pdf}): {r.stderr.strip()}", file=sys.stderr)
            raise SystemExit(2)
        text = out.read_text(encoding="utf-8", errors="replace")
    finally:
        out.unlink(missing_ok=True)

    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()                       # pdftotext 末尾多一个空段
    if strip_ws:
        pages = ["".join(p.split()) for p in pages]
    return pages


def parse_attr(items: list[str]) -> list[tuple[str, int]]:
    out = []
    for it in items:
        if "=" not in it:
            print(f"ERROR: 归因项格式应为 NAME=DELTA，收到 {it!r}", file=sys.stderr)
            raise SystemExit(2)
        name, _, val = it.rpartition("=")
        try:
            out.append((name.strip(), int(val.strip().lstrip("+"))))
        except ValueError:
            print(f"ERROR: 归因项 {it!r} 的 delta 不是整数", file=sys.stderr)
            raise SystemExit(2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", type=Path, help="改动前的 PDF")
    ap.add_argument("new", type=Path, help="改动后的 PDF")
    ap.add_argument("-a", "--attribute", action="append", default=[], metavar="NAME=DELTA",
                    help="已申报的改动及其字符增量，可重复")
    ap.add_argument("--strip-ws", action="store_true",
                    help="比较前去掉全部空白（排版重流引起的假 delta）")
    ap.add_argument("--quiet-equal", action="store_true", help="不打印零 delta 的页")
    args = ap.parse_args()

    for p in (args.base, args.new):
        if not p.is_file():
            print(f"ERROR: 文件不存在: {p}", file=sys.stderr)
            return 2

    old = extract_pages(args.base, args.strip_ws)
    new = extract_pages(args.new, args.strip_ws)

    print(f"BASE: {args.base.name}  {len(old)} pages")
    print(f"NEW : {args.new.name}  {len(new)} pages")
    if len(old) != len(new):
        print(f"PAGE-COUNT-DELTA: {len(new) - len(old):+d}  (逐页对齐仅在共同页范围内有意义)")
    print()
    print(f"{'page':>5}  {'base':>8}  {'new':>8}  {'delta':>8}")
    print("-" * 35)

    n = max(len(old), len(new))
    for i in range(n):
        a = len(old[i]) if i < len(old) else 0
        b = len(new[i]) if i < len(new) else 0
        d = b - a
        if d == 0 and args.quiet_equal:
            continue
        print(f"{i + 1:>5}  {a:>8}  {b:>8}  {d:>+8d}")

    total_old = sum(len(p) for p in old)
    total_new = sum(len(p) for p in new)
    total_delta = total_new - total_old
    print("-" * 35)
    print(f"{'TOTAL':>5}  {total_old:>8}  {total_new:>8}  {total_delta:>+8d}")

    attrs = parse_attr(args.attribute)
    if not attrs:
        print("\n（未给归因项；用 -a NAME=DELTA 申报各处改动以计算残差）")
        return 0

    print("\nATTRIBUTION")
    print(f"  whole-document delta : {total_delta:+d}")
    acc = 0
    width = max(len(k) for k, _ in attrs)
    for name, d in attrs:
        acc += d
        print(f"  {name:<{width}} delta : {d:+d}")
    residual = total_delta - acc
    print(f"  {'residual':<{width}}       : {residual:+d}")
    print(f"\nVERDICT: {'PASS' if residual == 0 else 'FAIL — 存在未申报的改动'}")
    if residual == 0:
        print("注意：等长改写不产生 delta。残差为零是必要条件，不是充分证明——"
              "充分性由三列对照单 + 源码 diff 闭合。")
    return 0 if residual == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
