#!/usr/bin/env python3
"""change_ledger.py — 段落级改动归因门禁（硬门；page_delta「残差 = 0」的段落级版）。

两版之间每个变了的段落单元，都必须能在候选账本 edits/units.jsonl 里找到一条
decision ∈ {accept, manual} 的记录；找不到 = 未申报改动 = HARD_FAIL。
等长改写、只换同义词的改动也逃不过——page_delta 抓不到的那一类。

账本一行一 JSON（schema 见 references/12-edit-contract.md §四）：
  {"unit_id": "05_results#12@af95d455", "covers": ["05_results#12", "05_results#13"],
   "decision": "accept", "reason_code": "hedge_over_budget", "round": 3, ...}
covers 里的 id 可以不带 @hash（按 文件#序号 匹配旧版或新版都算）。

用法:
    python change_ledger.py --config paper.gates.json --base-rev HEAD [--ledger edits/units.jsonl]
退出码: 0 = PASS, 1 = HARD_FAIL, 4 = REVIEW_REQUIRED, 2 = 用法/环境错误
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latex_scope as ls  # noqa: E402


def load_ledger(path: Path) -> list[dict]:
    out = []
    for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError as e:
            print(f"ERROR: 账本第 {i} 行不是合法 JSON：{e}", file=sys.stderr)
            raise SystemExit(2)
    return out


def ids_of(entry: dict) -> set[str]:
    ids = set()
    for k in ("unit_id", "result_id"):
        if entry.get(k):
            ids.add(entry[k])
    for c in entry.get("covers", []) or []:
        ids.add(c)
    return ids


def matches(entry_ids: set[str], unit_ids: list[str]) -> bool:
    for uid in unit_ids:
        stem = uid.split("@")[0]
        if uid in entry_ids or stem in entry_ids:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--base-rev", default="HEAD")
    ap.add_argument("--ledger", type=Path)
    ap.add_argument("--threshold", type=float, default=0.45)
    args = ap.parse_args()
    if not args.config.is_file():
        print(f"ERROR: 配置不存在: {args.config}", file=sys.stderr); return 2
    cfg = ls.load_config(args.config)
    # 默认账本跟稿件目录走（sections 的上一级），不跟配置文件走——配置可以放在稿件目录之外
    paper_dir = cfg.sections[0].parent if cfg.sections else cfg.root
    ledger_path = args.ledger or cfg.ledger or (paper_dir / "edits" / "units.jsonl")

    new_units = cfg.units()
    old_units = ls.units_from_git(cfg.section_files(), args.base_rev, cfg.roles)
    if old_units is None:
        print("ERROR: sections 不在 git 仓库内，无法取基线版本", file=sys.stderr); return 2
    pairs, added, removed = ls.pair_units(old_units, new_units, args.threshold)
    changed = [(o, n) for o, n, _ in pairs if ls._norm_ws(o.raw) != ls._norm_ws(n.raw)]

    entries = load_ledger(ledger_path) if ledger_path.is_file() else []
    accepted = [e for e in entries if e.get("decision") in ("accept", "manual")]
    rejected = [e for e in entries if e.get("decision") == "reject"]

    unaccounted: list[str] = []
    accounted = 0
    for o, n in changed:
        if any(matches(ids_of(e), [o.unit_id, n.unit_id]) for e in accepted):
            accounted += 1
        else:
            unaccounted.append(f"{o.unit_id} → {n.unit_id}  [{o.role}] {n.prose[:56]}")
    for u in added:
        if any(matches(ids_of(e), [u.unit_id]) for e in accepted):
            accounted += 1
        else:
            unaccounted.append(f"(新增) {u.unit_id}  [{u.role}] {u.prose[:56]}")
    for u in removed:
        if any(matches(ids_of(e), [u.unit_id]) for e in accepted):
            accounted += 1
        else:
            unaccounted.append(f"(删除) {u.unit_id}  [{u.role}] {u.prose[:56]}")

    review: list[str] = []
    changed_ids = {x.unit_id for o, n in changed for x in (o, n)} | {u.unit_id for u in added} | {u.unit_id for u in removed}
    for e in rejected:
        if any(uid in changed_ids or uid.split("@")[0] in {c.split("@")[0] for c in changed_ids} for uid in ids_of(e)):
            review.append(f"账本判 reject 的单元仍发生了改动：{sorted(ids_of(e))}")
    for e in accepted:
        if not e.get("reason_code"):
            review.append(f"账本条目缺 reason_code：{sorted(ids_of(e))}")
    if not entries and (changed or added or removed):
        review.append(f"账本文件不存在或为空：{ledger_path}")

    print(f"基线：{args.base_rev}；旧版单元 {len(old_units)}，新版单元 {len(new_units)}；配对 {len(pairs)}，其中改动 {len(changed)}；新增 {len(added)}；删除 {len(removed)}")
    print(f"账本：{ledger_path}（accept/manual {len(accepted)}，reject {len(rejected)}）")
    if unaccounted:
        print("\nUNACCOUNTED（未在账本申报的改动）")
        for x in unaccounted:
            print("  - " + x)
    verdict = "HARD_FAIL" if unaccounted else ("REVIEW_REQUIRED" if review else "PASS")
    code = 1 if unaccounted else (4 if review else 0)
    lines = [f"改动单元 {len(changed) + len(added) + len(removed)}；已归因 {accounted}；未归因 {len(unaccounted)}（残差必须为 0）"]
    if review:
        lines.append("待审项："); lines.extend("  - " + r for r in review)
    ls.print_proof("change_ledger", verdict, lines, code)
    return code


if __name__ == "__main__":
    sys.exit(main())
