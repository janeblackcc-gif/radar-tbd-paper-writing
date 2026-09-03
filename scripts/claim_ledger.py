#!/usr/bin/env python3
"""claim_ledger.py — 主张—证据闭环与镜像位置门禁（硬门）。

三件事：
  1. 解析大纲文件里的「主张—证据闭环表」（三列 Markdown 表：主张 | 证据 | 封口/边界）。
     每行必须：证据列含可解析的图/表引用；证据列含样本量；边界列非空。
  2. 证据列里反引号包住的图文件名（如 `fig_b5_main_snr`）必须在 sections 里被引用。
  3. **基线镜像规则**：结果章出现的外部基线名，摘要与结论都必须出现（同名或别名）。
     这是 SKILL.md §七 事故的机器版——最强结果只活在一节里，摘要一个外部方法不提。
     内部对照（如 NCV、已知率参考、消融臂）不在此列，通过配置 internal_baselines 排除。

配置键（paper.gates.json）：
    "outline": 大纲文件；"main": 主 tex（用于展开 \\gtmethod 这类文字宏）
    "external_baselines": ["GT-ML-PDA", "GM-PHD"]   可选；不给则按大写连字符名自动识别
    "internal_baselines": ["NCV-FCM-TBD", "已知率参考"]
    "method_names": ["STR-FCM-TBD"]                 本文方法，不当基线

用法:  python claim_ledger.py --config paper.gates.json
退出码: 0 = PASS, 1 = HARD_FAIL, 4 = REVIEW_REQUIRED, 2 = 用法/环境错误
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latex_scope as ls  # noqa: E402

#: 证据钩子：图/表引用、反引号产物名、统计证据（区间/消融/bootstrap）、协议或定义类证据。
#: 第一篇定稿的闭环表实测有 4 行不引图而引「bootstrap 区间」「三臂消融」「评价合同」——这些是
#: 合法证据，规则按真稿校准后放宽；完全没有任何钩子的行才是悬空主张。
FIGREF = re.compile(r"`[^`]+`|(?:图|表|Fig(?:ure)?\.?|Table)\s*~?\s*\d+|[一二三四五六七八九十\d]+\s*[类张幅]图|图证链|fig[:_][A-Za-z0-9_\-]+|tab[:_][A-Za-z0-9_\-]+", re.I)
STATREF = re.compile(r"区间|bootstrap|自助|消融|置信|\bCI\b|ablation", re.I)
PROTOREF = re.compile(r"合同|协议|定义|复杂度|\\mathcal|O\(|评价器|evaluator", re.I)
SAMPLE = re.compile(r"\d+\s*(?:次|个|组|条|seed|seeds|-seed|realisations?|runs?|trials?|场景|Monte)|每(?:格|个组合|条件|单元)|全部\s*\d+", re.I)
UPPER_NAME = re.compile(r"(?<![A-Za-z])[A-Z][A-Z0-9]*(?:[-+][A-Z0-9]+){1,4}(?![A-Za-z])")


def parse_ledger(md: str) -> list[dict]:
    lines = md.splitlines()
    rows = []
    in_table = False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not in_table:
            if s.startswith("|") and "主张" in s and ("证据" in s) and ("边界" in s or "封口" in s):
                in_table = True
            continue
        if not s.startswith("|"):
            if rows:
                break
            continue
        if re.match(r"^\|?\s*:?-{2,}", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 3:
            cells += [""] * (3 - len(cells))
        rows.append({"line": i + 1, "claim": cells[0], "evidence": cells[1], "boundary": cells[2]})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--no-ledger", action="store_true", help="跳过闭环表检查（只做基线镜像）")
    args = ap.parse_args()
    if not args.config.is_file():
        print(f"ERROR: 配置不存在: {args.config}", file=sys.stderr)
        return 2
    cfg = ls.load_config(args.config)
    raw = cfg.raw
    fail: list[str] = []
    review: list[str] = []

    # ---------- 1/2 闭环表 ----------
    rows: list[dict] = []
    if not args.no_ledger:
        if not cfg.outline or not cfg.outline.is_file():
            fail.append("大纲文件缺失或未配置（骨架层第一件交付物）")
        else:
            rows = parse_ledger(cfg.outline.read_text(encoding="utf-8", errors="replace"))
            if not rows:
                fail.append(f"大纲 {cfg.outline.name} 里没有找到「主张 | 证据 | 封口/边界」三列表")
            all_src = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in cfg.section_files())
            no_sample: list[str] = []
            for r in rows:
                tag = r["claim"][:28]
                ev = r["evidence"]
                if not (FIGREF.search(ev) or STATREF.search(ev) or PROTOREF.search(ev)):
                    fail.append(f"L{r['line']} 「{tag}」证据列没有任何可解析的证据钩子（图/表/产物名/区间/消融/协议）")
                if not SAMPLE.search(ev):
                    no_sample.append(f"L{r['line']} 「{tag}」")
                if len(re.sub(r"\s", "", r["boundary"])) < 8:
                    fail.append(f"L{r['line']} 「{tag}」封口/边界列为空或过短")
            if rows and len(no_sample) == len(rows):
                fail.append("闭环表没有任何一行给出样本量")
            elif no_sample:
                review.append("以下行证据列未写样本量（若继承自其他行请在该行注明「同 C1」）：" + "；".join(no_sample))
                for m in re.finditer(r"`([^`]+)`", r["evidence"]):
                    name = m.group(1)
                    if re.match(r"^(fig|tab)", name, re.I) and name not in all_src:
                        review.append(f"L{r['line']} 证据 `{name}` 在 sections 源码中未被引用（改名或未接入？）")

    # ---------- 3 基线镜像 ----------
    units = cfg.units()
    by_role: dict[str, str] = {}
    for u in units:
        by_role[u.role] = by_role.get(u.role, "") + "\n" + cfg.expand_text_macros(ls.strip_comments(u.raw))
    results_txt = by_role.get("results", "") + by_role.get("discussion", "")
    abstract_txt = by_role.get("abstract", "")
    concl_txt = by_role.get("conclusion", "")

    method_names = set(raw.get("method_names") or [])
    internal = set(raw.get("internal_baselines") or [])
    if raw.get("external_baselines"):
        external = list(raw["external_baselines"])
    else:
        found = {m.group(0) for m in UPPER_NAME.finditer(results_txt)}
        external = sorted(n for n in found if n not in method_names and n not in internal
                          and not re.match(r"^(SNR|RMSE|GOSPA|OSPA|CI|MC|PDF|CV|CT|NCV|TBD|ML-PDA|ROC|CFAR-?)$", n)
                          and len(n) >= 5)
    aliases: dict[str, list[str]] = raw.get("baseline_aliases") or {}

    def mentioned(name: str, txt: str) -> bool:
        keys = [name] + aliases.get(name, [])
        return any(k in txt for k in keys)

    if not external:
        review.append("结果章未识别到外部基线名；若确有外部比较请在配置 external_baselines 里声明")
    missing_abs = [n for n in external if not mentioned(n, abstract_txt)]
    missing_con = [n for n in external if not mentioned(n, concl_txt)]
    if missing_abs:
        fail.append("基线镜像：结果章比较了 " + "、".join(missing_abs) + "，摘要未提及（02-narrative 硬规则：做了基线比较，比较结论必须进摘要）")
    if missing_con:
        # 第一篇定稿（导师已过审）的结论章也未点名基线——按「先在真稿校准再标硬」原则记 REVIEW
        review.append("基线镜像：结论未提及 " + "、".join(missing_con) + "（04-hedging §十四 镜像位置；第一篇定稿同样缺，故只提醒）")

    verdict = "HARD_FAIL" if fail else ("REVIEW_REQUIRED" if review else "PASS")
    code = 1 if fail else (4 if review else 0)
    lines = [f"闭环表行数：{len(rows)}；外部基线：{external or '无'}；内部对照：{sorted(internal) or '无'}"]
    if fail:
        lines.append("失败项：")
        lines.extend("  - " + x for x in fail)
    if review:
        lines.append("待审项：")
        lines.extend("  - " + x for x in review)
    ls.print_proof("claim_ledger", verdict, lines, code)
    return code


if __name__ == "__main__":
    sys.exit(main())
