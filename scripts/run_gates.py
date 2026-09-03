#!/usr/bin/env python3
"""run_gates.py — 门禁编排器：按注册表逐门执行，聚合成四态判定。

    BLOCKED    契约门失败或工具错误 → 禁止改稿
    TARGETED   硬门失败 → 定点修（报告里有 unit / reason）
    REVIEW     只剩待审项或软热区 → 人工判定
    FROZEN_OK  全过 → 停止；再改只能由导师意见或新事实触发

没有总分，不可补偿：一个硬门失败不会被别的门的高分抵消。

用法:
    python run_gates.py --config paper.gates.json [--registry gates/gates.json]
                        [--only id ...] [--skip id ...] [--report gate_report.md] [--json gate_report.json]
                        [--allow-skip]     # 允许硬门因缺输入被跳过时仍可判 FROZEN_OK（默认不允许）

退出码: 0 = FROZEN_OK, 1 = TARGETED/REVIEW, 3 = BLOCKED, 2 = 用法/环境错误
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_args(template: list[str], values: dict[str, str]) -> tuple[list[str], list[str]]:
    """把 {name} 替换成配置值；返回 (args, 缺失键)。"""
    out, missing = [], []
    for a in template:
        if a.startswith("{") and a.endswith("}"):
            key = a[1:-1]
            v = values.get(key)
            if v is None or v == "":
                missing.append(key)
            else:
                out.append(str(v))
        else:
            out.append(a)
    return out, missing


def proof_block(stdout: str) -> str:
    lines = stdout.splitlines()
    try:
        i = max(idx for idx, ln in enumerate(lines) if ln.strip() == "PROOF")
    except ValueError:
        return ""
    block = []
    for ln in lines[i:]:
        if ln.startswith("=" * 20) and block:
            break
        block.append(ln)
    return "\n".join(block)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, required=True, help="项目配置 paper.gates.json")
    ap.add_argument("--registry", type=Path, default=SKILL_ROOT / "gates" / "gates.json")
    ap.add_argument("--only", action="append", default=[], help="只跑这些 gate id")
    ap.add_argument("--skip", action="append", default=[], help="跳过这些 gate id")
    ap.add_argument("--report", type=Path, help="写 Markdown 报告")
    ap.add_argument("--json", type=Path, help="写 JSON 结果")
    ap.add_argument("--allow-skip", action="store_true")
    args = ap.parse_args()

    if not args.config.is_file():
        print(f"ERROR: 配置不存在: {args.config}", file=sys.stderr)
        return 2
    if not args.registry.is_file():
        print(f"ERROR: 注册表不存在: {args.registry}", file=sys.stderr)
        return 2
    cfg = load_json(args.config)
    reg = load_json(args.registry)
    root = args.config.parent

    def abspath(v):
        if isinstance(v, list):
            v = v[0] if v else None
        if not v:
            return None
        p = Path(v)
        return str(p if p.is_absolute() else (root / p))

    values: dict[str, str] = {"config": str(args.config.resolve())}
    for key in ("sections", "pdf", "pdf_base", "macro_base", "macro_new", "outline", "glossary",
                "exemptions", "ledger", "banned_terms", "main"):
        v = abspath(cfg.get(key))
        if v:
            values[key] = v
    if "macro_new" not in values and cfg.get("macros"):
        values["macro_new"] = abspath(cfg["macros"])
    for k, v in cfg.items():                      # 其余标量键（如 base_rev）原样可用
        if isinstance(v, str) and k not in values:
            values[k] = v
    if "exemptions" not in values:
        values["exemptions"] = str(root / "paper.exemptions.json")  # 允许不存在

    semantics = {int(k): v for k, v in reg["exit_semantics"].items()}
    results = []
    for g in reg["gates"]:
        gid = g["id"]
        if args.only and gid not in args.only:
            continue
        if gid in args.skip:
            results.append({"id": gid, "status": "SKIPPED", "reason": "--skip", "severity": g["severity"]})
            continue
        gargs, missing = resolve_args(g["args"], values)
        need = [k for k in g.get("requires", []) if k not in values] + missing
        if need:
            results.append({"id": gid, "status": "SKIPPED", "reason": f"缺输入 {sorted(set(need))}",
                            "severity": g["severity"]})
            continue
        script = HERE / g["script"]
        if not script.is_file():
            results.append({"id": gid, "status": "ERROR", "reason": f"脚本不存在 {script.name}", "severity": g["severity"]})
            continue
        # page_delta 的归因项
        if gid == "page_delta":
            for k, v in (cfg.get("attributions") or {}).items():
                gargs += ["-a", f"{k}={v}"]
        cmd = [sys.executable, str(script)] + gargs
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        status = semantics.get(r.returncode, f"EXIT{r.returncode}")
        if gid == "jargon_scan" and r.returncode == 1:
            status = "REVIEW_REQUIRED"   # 命中数需与人工豁免数比对，脚本本身不能判失败
        if g["severity"] == "soft" and r.returncode == 1:
            status = "REVIEW_REQUIRED"   # 软门按定义不得失败；退出 1 视为待审并在报告里标注
            notes_soft = f"软门 {gid} 返回了退出码 1——软门不得判失败，已降为待审；请检查脚本"
            results.append({"id": gid + "(note)", "status": "NOTE", "reason": notes_soft, "severity": "soft"})
        results.append({"id": gid, "status": status, "exit": r.returncode, "severity": g["severity"],
                        "on_fail": g.get("on_fail", "TARGETED"), "cmd": " ".join(cmd),
                        "proof": proof_block(r.stdout), "stdout": r.stdout, "stderr": r.stderr.strip()})

    # ---- 聚合 ----
    verdict = "FROZEN_OK"
    notes = []
    if any(x["status"] == "ERROR" for x in results):
        verdict = "BLOCKED"; notes.append("有门禁因工具/用法错误未能执行——不能出具任何合格证")
    elif any(x["status"] == "HARD_FAIL" and x.get("on_fail") == "BLOCKED" for x in results):
        verdict = "BLOCKED"; notes.append("契约门失败")
    elif any(x["status"] == "HARD_FAIL" and x["severity"] == "hard" for x in results):
        verdict = "TARGETED"
    elif any(x["status"] == "REVIEW_REQUIRED" for x in results):
        verdict = "REVIEW"
    hard_skipped = [x["id"] for x in results if x["status"] == "SKIPPED" and x["severity"] == "hard"]
    if verdict == "FROZEN_OK" and hard_skipped and not args.allow_skip:
        verdict = "REVIEW"; notes.append(f"硬门被跳过（缺输入）：{hard_skipped}；补齐后重跑或 --allow-skip")

    # ---- 输出 ----
    print(f"{'gate':<20} {'sev':<5} {'status':<16} note")
    print("-" * 64)
    for x in results:
        print(f"{x['id']:<20} {x['severity']:<5} {x['status']:<16} {x.get('reason', '')}")
    print("-" * 64)
    print(f"VERDICT: {verdict}")
    for n in notes:
        print(f"  ! {n}")
    print(json.dumps(reg["verdicts"][verdict], ensure_ascii=False))

    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    if args.report:
        md = [f"# 门禁报告 {stamp}", "", f"配置：`{args.config}`", "", f"## 判定：**{verdict}**", ""]
        md += [f"- {n}" for n in notes]
        md += ["", "| gate | severity | status |", "|---|---|---|"]
        md += [f"| {x['id']} | {x['severity']} | {x['status']} {x.get('reason', '')} |" for x in results]
        for x in results:
            if x.get("proof"):
                md += ["", f"## {x['id']}", "", "```", x["proof"], "```"]
                if x.get("stderr"):
                    md += ["", "stderr:", "```", x["stderr"], "```"]
        args.report.write_text("\n".join(md) + "\n", encoding="utf-8")
        print(f"report → {args.report}")
    if args.json:
        args.json.write_text(json.dumps({"verdict": verdict, "notes": notes, "time": stamp,
                                         "results": [{k: v for k, v in x.items() if k != "stdout"} for x in results]},
                                        ensure_ascii=False, indent=1), encoding="utf-8")
    return {"FROZEN_OK": 0, "TARGETED": 1, "REVIEW": 1, "BLOCKED": 3}[verdict]


if __name__ == "__main__":
    sys.exit(main())
