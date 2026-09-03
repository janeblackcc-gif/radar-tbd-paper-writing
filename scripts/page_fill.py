#!/usr/bin/env python3
"""page_fill.py — 页级填充度门禁：抓半空页（硬门，可按页豁免）。

事故来源：第二篇 v0.4 在结果章加了四个 \\FloatBarrier，第 9/11/12 页各空一半，
13 页变 15 页；源码 diff 看不出来，只有页级渲染能看见。本脚本把「页级目检」
中最机械的一项自动化：**非末页的正文区若尾部空白超过阈值即失败**。

做法：pdftoppm -gray -r 40 → 纯 Python 解析 PGM(P5) → 逐行墨迹 → 剔除页脚簇
→ 以全稿最深的正文底线为基准，算每页（整页与左右半页）的尾部空白占比。
双栏稿一侧栏提前结束同样会被抓到。

用法:
    python page_fill.py --pdf main.pdf [--threshold 0.35] [--exempt 12] [--exemptions ex.json]
    python page_fill.py --pgm-dir tests/fixtures/.../pgm       # 回归用：直接喂 PGM

退出码: 0 = PASS, 1 = HARD_FAIL, 2 = 环境或用法错误
豁免文件格式（与其他门禁同一文件）：{"page_fill": [{"page": 12, "reason": "..."}]}
"""

from __future__ import annotations

import argparse
import json
import math
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


def read_pgm(path: Path) -> tuple[int, int, int, bytes]:
    data = path.read_bytes()
    # 头：P5 <ws> W <ws> H <ws> MAXVAL <单个空白> 数据
    tokens: list[bytes] = []
    i = 0
    while len(tokens) < 4:
        while i < len(data) and data[i:i + 1].isspace():
            i += 1
        if data[i:i + 1] == b"#":
            while i < len(data) and data[i:i + 1] not in (b"\n", b"\r"):
                i += 1
            continue
        j = i
        while j < len(data) and not data[j:j + 1].isspace():
            j += 1
        tokens.append(data[i:j])
        i = j
    i += 1  # 单个空白
    if tokens[0] != b"P5":
        raise ValueError(f"{path}: 不是 P5 PGM")
    w, h, maxval = int(tokens[1]), int(tokens[2]), int(tokens[3])
    if maxval > 255:
        raise ValueError(f"{path}: 只支持 8 位灰度")
    return w, h, maxval, data[i:i + w * h]


def render(pdf: Path, dpi: int, workdir: Path) -> list[Path]:
    if shutil.which("pdftoppm") is None:
        print("ERROR: 找不到 pdftoppm，请安装 poppler-utils", file=sys.stderr)
        raise SystemExit(2)
    r = subprocess.run(["pdftoppm", "-gray", "-r", str(dpi), str(pdf), str(workdir / "p")],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        print(f"ERROR: pdftoppm 失败: {r.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    return sorted(workdir.glob("p-*.pgm"))


def row_ink(w: int, h: int, px: bytes, x0: int, x1: int, dark: int) -> list[int]:
    """每行在 [x0,x1) 内的暗像素数。"""
    out = []
    for y in range(h):
        row = px[y * w + x0: y * w + x1]
        out.append(sum(1 for b in row if b < dark))
    return out


def clusters(inked: list[bool]) -> list[tuple[int, int]]:
    """连续 True 段 → [(start,end)]。"""
    out = []
    s = None
    for i, v in enumerate(inked):
        if v and s is None:
            s = i
        elif not v and s is not None:
            out.append((s, i - 1))
            s = None
    if s is not None:
        out.append((s, len(inked) - 1))
    return out


def body_extent(ink: list[int], h: int, min_ink: int) -> tuple[int | None, int | None, int | None]:
    """返回 (正文首墨行, 正文末墨行, 页脚首行或 None)。
    页脚判据：最后一个墨迹簇高度 < 2.5% 页高，且与前一簇间隔 > 3% 页高。"""
    inked = [v >= min_ink for v in ink]
    cl = clusters(inked)
    if not cl:
        return None, None, None
    footer = None
    if len(cl) >= 2:
        s, e = cl[-1]
        ps, pe = cl[-2]
        if (e - s + 1) < 0.025 * h and (s - pe) > 0.03 * h:
            footer = s
            cl = cl[:-1]
    return cl[0][0], cl[-1][1], footer


def analyse(pages: list[tuple[int, int, bytes]], dark: int, col_gap_frac: float) -> list[dict]:
    """逐页计算整页与左右半页的正文末行；再以全稿最深末行为基准求尾部空白占比。"""
    per: list[dict] = []
    for idx, (w, h, px) in enumerate(pages, 1):
        min_ink = max(2, int(0.004 * w))
        whole = row_ink(w, h, px, 0, w, dark)
        top, bottom, footer = body_extent(whole, h, min_ink)
        # 双栏判定：在有正文墨迹的行里，中缝细条（默认 1.2% 页宽）为空白的行占多数。
        # 通栏浮动体（figure*/table*）会跨越中缝，所以看比例而不是绝对计数。
        half = max(1, int(w * col_gap_frac / 2))
        gx0, gx1 = w // 2 - half, w // 2 + half
        gutter = row_ink(w, h, px, gx0, gx1, dark)
        body_rows = [y for y in range(h) if whole[y] >= min_ink and (top is None or top <= y <= (bottom if bottom is not None else h))]
        blank_gutter = sum(1 for y in body_rows if gutter[y] == 0)
        two_col = bool(body_rows) and blank_gutter >= 0.6 * len(body_rows)
        cols = {}
        if two_col:
            for name, (x0, x1) in (("left", (0, w // 2)), ("right", (w // 2, w))):
                ink = row_ink(w, h, px, x0, x1, dark)
                t, b, _ = body_extent(ink, h, max(2, int(0.004 * (x1 - x0))))
                cols[name] = b
        per.append({"page": idx, "w": w, "h": h, "top": top, "bottom": bottom,
                    "footer": footer, "two_col": two_col, "cols": cols})

    # 基准：非末页中最深的正文末行（页脚以上）
    candidates = [p["bottom"] for p in per[:-1] if p["bottom"] is not None] or \
                 [p["bottom"] for p in per if p["bottom"] is not None]
    ref_bottom = max(candidates) if candidates else None
    tops = [p["top"] for p in per if p["top"] is not None]
    ref_top = min(tops) if tops else 0
    for p in per:
        p["ref_bottom"] = ref_bottom
        if ref_bottom is None or p["bottom"] is None:
            p["blank_whole"] = None
            p["blank_cols"] = {}
            continue
        body_h = max(1, ref_bottom - ref_top)
        p["blank_whole"] = max(0.0, (ref_bottom - p["bottom"]) / body_h)
        p["blank_cols"] = {k: (max(0.0, (ref_bottom - v) / body_h) if v is not None else 1.0)
                           for k, v in p["cols"].items()}
    return per


def load_page_exemptions(path: Path | None) -> dict[int, str]:
    if not path or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for it in data.get("page_fill", []):
        if isinstance(it, dict) and "page" in it:
            out[int(it["page"])] = str(it.get("reason", ""))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", type=Path)
    src.add_argument("--pgm-dir", type=Path, help="已渲染的 P5 PGM 目录（回归用）")
    ap.add_argument("--dpi", type=int, default=40)
    ap.add_argument("--threshold", type=float, default=0.35, help="尾部空白占正文高度的比例上限")
    ap.add_argument("--dark", type=int, default=200, help="灰度 < 该值算墨迹")
    ap.add_argument("--col-gap", type=float, default=0.012, help="中缝检测竖条宽度占页宽比例（40 dpi A4 ≈ 4 px）")
    ap.add_argument("--exempt", type=int, action="append", default=[], help="豁免页号，可重复")
    ap.add_argument("--exemptions", type=Path, help="豁免 JSON（键 page_fill）")
    ap.add_argument("--json", type=Path, help="把逐页结果写成 JSON")
    args = ap.parse_args()

    pages: list[tuple[int, int, bytes]] = []
    tmp = None
    try:
        if args.pdf:
            if not args.pdf.is_file():
                print(f"ERROR: PDF 不存在: {args.pdf}", file=sys.stderr)
                return 2
            tmp = Path(tempfile.mkdtemp(prefix="page_fill_"))
            files = render(args.pdf, args.dpi, tmp)
        else:
            if not args.pgm_dir.is_dir():
                print(f"ERROR: 目录不存在: {args.pgm_dir}", file=sys.stderr)
                return 2
            files = sorted(args.pgm_dir.glob("*.pgm"))
        if not files:
            print("ERROR: 没有页面图像", file=sys.stderr)
            return 2
        for f in files:
            w, h, _, px = read_pgm(f)
            pages.append((w, h, px))
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    per = analyse(pages, args.dark, args.col_gap)
    exempt = {p: "命令行" for p in args.exempt}
    exempt.update(load_page_exemptions(args.exemptions))

    n = len(per)
    fails, exempted = [], []
    print(f"{'page':>5} {'2col':>5} {'whole':>7} {'left':>7} {'right':>7}  note")
    print("-" * 50)
    for p in per:
        bw = p["blank_whole"]
        bl = p["blank_cols"].get("left")
        br = p["blank_cols"].get("right")
        worst = max([v for v in (bw, bl, br) if v is not None], default=None)
        note = ""
        if p["page"] == n:
            note = "末页，不计"
        elif worst is None:
            note = "空白页？"
            fails.append((p["page"], 1.0, "整页无墨迹"))
        elif worst > args.threshold:
            if p["page"] in exempt:
                note = f"超阈但已豁免：{exempt[p['page']]}"
                exempted.append(p["page"])
            else:
                note = f"超阈 {worst:.2f} > {args.threshold}"
                fails.append((p["page"], worst, note))
        fmt = lambda v: f"{v:7.2f}" if v is not None else f"{'—':>7}"
        print(f"{p['page']:>5} {'Y' if p['two_col'] else 'N':>5} {fmt(bw)} {fmt(bl)} {fmt(br)}  {note}")

    if args.json:
        args.json.write_text(json.dumps(per, ensure_ascii=False, indent=1), encoding="utf-8")

    code = 1 if fails else 0
    print("=" * 60)
    print("PROOF")
    print("  门禁：page_fill")
    print(f"  页数：{n}；阈值：{args.threshold}；dpi：{args.dpi}")
    print(f"  超阈页：{[f[0] for f in fails] or '无'}；已豁免页：{exempted or '无'}")
    print(f"  判定：{'HARD_FAIL' if fails else 'PASS'}")
    print(f"  退出码：{code}")
    print("  口径：非末页的正文尾部空白 / 全稿正文高度；双栏稿按左右半页分别计。")
    print("  常见根因：\\FloatBarrier、[H]/[p] 浮动、过大浮动体推挤、章末 \\clearpage。")
    print("=" * 60)
    return code


if __name__ == "__main__":
    sys.exit(main())
