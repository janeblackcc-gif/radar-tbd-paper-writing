#!/usr/bin/env python3
"""run_regressions.py — 门禁回归总闸。

跑 tests/fixtures/<gate>/<case>/case.json 里的每个用例，断言退出码与输出片段。
用例只用合成片段，不含真稿；真稿端到端用 tests/golden/local_paths.json（gitignored）引用。

case.json 字段：
    gate                  脚本名（不带 .py）
    args                  参数列表；{dir} 展开为用例目录
    expect_exit           期望退出码
    expect_contains       stdout 里必须出现的片段（列表，可空）
    expect_not_contains   stdout 里不得出现的片段（列表，可空）
    synth_pgm             （仅 page_fill）合成页面规格 [{"fill":1.0,"two_col":true}, ...]，
                          运行前生成到 {dir}/pgm/，跑完删除
    git_case              （change_ledger / semantic_diff --old-rev 用）{"base":"base","new":"new"}：
                          把 {dir}/base 复制到临时目录并 git commit，再用 {dir}/new 覆盖工作区；
                          此时 {dir} 指向该临时目录，跑完删除
    kind                  must_change | must_preserve | manual_review（只作分组显示）

golden（tests/golden/local_paths.json，gitignored）两种条目：
    {"name", "config", "only": [...], "expect_verdict"}                跑 run_gates.py，比判定
    {"name", "script": "semantic_diff", "args": [...], "expect_exit", "expect_contains", "expect_not_contains"}
                                                                      直接跑单个门禁脚本（真稿 git 历史回放）

用法:  python run_regressions.py [--filter 子串] [--golden tests/golden/local_paths.json]
退出码: 0 = 全绿, 1 = 有失败, 2 = 用法错误
"""

from __future__ import annotations

import argparse
import json
import os
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURES = ROOT / "tests" / "fixtures"


def synth_pgm(spec: list[dict], out: Path, w: int = 330, h: int = 470) -> None:
    """生成 P5 灰度页：正文区从 8% 到 92% 页高；每页按 fill 比例画「文字行」；
    two_col 时中缝留白；页脚画一小段页码。"""
    out.mkdir(parents=True, exist_ok=True)
    for i, page in enumerate(spec, 1):
        px = bytearray(b"\xff" * (w * h))
        top, bottom = int(0.08 * h), int(0.92 * h)
        fill = float(page.get("fill", 1.0))
        two_col = bool(page.get("two_col", False))
        right_fill = float(page.get("right_fill", fill))
        margin = int(0.1 * w)
        gutter = max(3, int(0.02 * w))
        y = top
        line_h, gap = 3, 4
        end_left = top + int((bottom - top) * fill)
        end_right = top + int((bottom - top) * right_fill)
        while y + line_h <= bottom:
            for yy in range(y, y + line_h):
                if two_col:
                    if y < end_left:
                        for x in range(margin, w // 2 - gutter):
                            px[yy * w + x] = 0
                    if y < end_right:
                        for x in range(w // 2 + gutter, w - margin):
                            px[yy * w + x] = 0
                else:
                    if y < end_left:
                        for x in range(margin, w - margin):
                            px[yy * w + x] = 0
            y += line_h + gap
        # 页脚页码
        fy = int(0.96 * h)
        for yy in range(fy, fy + 2):
            for x in range(w // 2 - 3, w // 2 + 3):
                px[yy * w + x] = 0
        (out / f"p-{i:02d}.pgm").write_bytes(f"P5\n{w} {h}\n255\n".encode() + bytes(px))


def _copy_tree(src: Path, dst: Path) -> None:
    for p in src.rglob("*"):
        if p.is_file():
            q = dst / p.relative_to(src)
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, q)


def make_git_case(case_dir: Path, spec: dict) -> Path:
    """base/ → 临时仓库首个提交；new/ → 工作区。返回临时仓库路径。"""
    tmp = Path(tempfile.mkdtemp(prefix="gate_git_"))
    env = {**os.environ, "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
    _copy_tree(case_dir / spec.get("base", "base"), tmp)
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "base"]):
        subprocess.run(cmd, cwd=str(tmp), check=True, capture_output=True, env=env)
    for p in tmp.iterdir():
        if p.name != ".git":
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    _copy_tree(case_dir / spec.get("new", "new"), tmp)
    return tmp


def run_case(case_dir: Path, case: dict) -> tuple[bool, str]:
    gate = case["gate"]
    script = HERE / f"{gate}.py"
    if not script.is_file():
        return False, f"脚本不存在 {script.name}"
    pgm_dir = None
    if case.get("synth_pgm"):
        pgm_dir = case_dir / "pgm"
        synth_pgm(case["synth_pgm"], pgm_dir)
    work_dir, tmp_repo = case_dir, None
    if case.get("git_case"):
        if not shutil.which("git"):
            return False, "需要 git（git_case 用例）"
        tmp_repo = make_git_case(case_dir, case["git_case"])
        work_dir = tmp_repo
    args = [a.replace("{dir}", str(work_dir)) for a in case.get("args", [])]
    try:
        r = subprocess.run([sys.executable, str(script)] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=str(work_dir))
    finally:
        if pgm_dir:
            shutil.rmtree(pgm_dir, ignore_errors=True)
        if tmp_repo:
            shutil.rmtree(tmp_repo, ignore_errors=True)
    return check_result(r, case)


def check_result(r: subprocess.CompletedProcess, case: dict) -> tuple[bool, str]:
    out = r.stdout + "\n" + r.stderr
    problems = []
    if r.returncode != case["expect_exit"]:
        problems.append(f"退出码 {r.returncode} ≠ 期望 {case['expect_exit']}")
    for s in case.get("expect_contains", []):
        if s not in out:
            problems.append(f"缺少输出片段 {s!r}")
    for s in case.get("expect_not_contains", []):
        if s in out:
            problems.append(f"不该出现的输出片段 {s!r}")
    if problems:
        tail = "\n".join(out.strip().splitlines()[-12:])
        return False, "; ".join(problems) + "\n      --- 输出尾部 ---\n      " + tail.replace("\n", "\n      ")
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--filter", default="", help="只跑路径含该子串的用例")
    ap.add_argument("--golden", type=Path, default=ROOT / "tests" / "golden" / "local_paths.json")
    args = ap.parse_args()

    cases = sorted(FIXTURES.glob("*/*/case.json"))
    if args.filter:
        cases = [c for c in cases if args.filter in str(c)]
    if not cases:
        print("ERROR: 没有用例", file=sys.stderr)
        return 2

    failed = 0
    by_kind: dict[str, list[str]] = {}
    for cj in cases:
        case = json.loads(cj.read_text(encoding="utf-8"))
        ok, msg = run_case(cj.parent, case)
        name = f"{cj.parent.parent.name}/{cj.parent.name}"
        kind = case.get("kind", "other")
        by_kind.setdefault(kind, []).append(("PASS" if ok else "FAIL") + "  " + name + ("" if ok else f"\n      {msg}"))
        failed += 0 if ok else 1
    for kind in ("must_change", "must_preserve", "manual_review", "other"):
        if kind in by_kind:
            print(f"[{kind}]")
            for ln in by_kind[kind]:
                print("  " + ln)

    # golden：真稿端到端（本地路径，不入库）
    if args.golden.is_file():
        gold = json.loads(args.golden.read_text(encoding="utf-8"))
        print("[golden]")
        for g in gold.get("cases", []):
            if g.get("script"):
                script = HERE / f"{g['script']}.py"
                if not script.is_file():
                    print(f"  FAIL  {g['name']}（脚本不存在 {script.name}）"); failed += 1; continue
                r = subprocess.run([sys.executable, str(script)] + [str(a) for a in g.get("args", [])],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
                ok, msg = check_result(r, g)
                failed += 0 if ok else 1
                print(f"  {'PASS' if ok else 'FAIL'}  {g['name']}" + ("" if ok else f"\n      {msg}"))
                continue
            cfg = Path(g["config"])
            if not cfg.is_file():
                print(f"  SKIP  {g['name']}（配置不存在：{cfg}）")
                continue
            r = subprocess.run([sys.executable, str(HERE / "run_gates.py"), "--config", str(cfg)] +
                               sum((["--only", o] for o in g.get("only", [])), []),
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            verdict = next((ln.split(":", 1)[1].strip() for ln in r.stdout.splitlines() if ln.startswith("VERDICT:")), "?")
            ok = verdict == g["expect_verdict"]
            failed += 0 if ok else 1
            print(f"  {'PASS' if ok else 'FAIL'}  {g['name']}: {verdict}（期望 {g['expect_verdict']}）")
    else:
        print(f"[golden] 未配置（{args.golden} 不存在，跳过真稿端到端）")

    print("-" * 50)
    print(f"用例 {len(cases)}；失败 {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
