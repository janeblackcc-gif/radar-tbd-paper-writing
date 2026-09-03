#!/usr/bin/env python3
"""hedge_budget.py — 防御性表述预算门禁（硬门 + 成对的下限规则）。

把 references/04-hedging.md §二 的四条规则做成可执行检查：
  1. 全稿上限：ceil(10 × 页数 / 20) 句（按 PDF 抽取文本计数，宏展开后的口径）
  2. 位置白名单：引言、相关工作 0 句；允许出现在 model/method/results/conclusion
  3. 同一条边界最多 2 次：防御句按最长公共子串（≥ --lcs 字）聚类，簇 > 2 即违规
  4. **下限（成对规则）**：结果章与结论章各至少 1 句适用范围句——
     删光边界句和堆砌边界句一样是缺陷，本脚本两头都拦。

豁免（带标签）不计入上限与位置规则，但计入下限：
  {"hedge_budget": [{"match": "原句子串", "tag": "statistical_boundary", "reason": "..."}]}
  合法标签：statistical_boundary baseline_identity information_contract model_assumption
            evaluation_condition submission_compliance evaluator_disclosure pointwise_declaration

用法:
    python hedge_budget.py --config paper.gates.json [--per20 10] [--lcs 12]
退出码: 0 = PASS, 1 = HARD_FAIL, 4 = REVIEW_REQUIRED, 2 = 用法/环境错误
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latex_scope as ls  # noqa: E402

DEFENSIVE = re.compile(
    r"不等同于|并不(?:表示|意味|证明|构成|代表|说明)|不(?:应|能|得|宜)(?:据此|被理解为|被解释为|解释为|视为|理解为|外推|推广|简单地|单独)"
    r"|尚不能|不作为|不足以(?:判定|证明|支持|说明|区分)|不排除|不构成|不代表|不证明|不外推|不主张|不声称"
    r"|无法(?:判定|区分|确定|外推|归因)|不区分[^，。；]{0,12}(?:贡献|影响|作用)|不(?:能|应)(?:单独|简单)(?:确定|解释|归因)"
    r"|仅(?:作为|用于)[^，。；]{0,10}(?:补充|参考|描述)|不(?:把|将)[^，。；]{0,16}(?:外推|推广|归因)"
    r"|\b(?:cannot be (?:interpreted|read|taken)|does not (?:imply|prove|establish|guarantee)|should not be (?:interpreted|read)"
    r"|is not (?:intended|meant) to|not (?:necessarily|equivalent)|beyond the scope|we do not (?:claim|extrapolate))\b",
    re.I,
)

BOUNDARY = re.compile(
    r"(?:在|于)[^。；]{2,60}(?:条件|场景|构型|设置|假设|范围|前提)(?:下|内|中)[^。；]{0,30}(?:建立|验证|成立|得到|获得|覆盖|适用|报告)"
    r"|限定于|只覆盖|仅覆盖|适用范围|适用于|覆盖[^。；]{0,30}(?:条件|范围|构型)|不外推|(?:尚未|未)纳入|结论(?:建立|成立)在"
    r"|\b(?:limited to|restricted to|applies? (?:only )?to|under the .{0,40}conditions?|within the .{0,30}(?:range|regime)|do not extrapolate)\b",
    re.I,
)

ALLOWED_TAGS = {"statistical_boundary", "baseline_identity", "information_contract", "model_assumption",
                "evaluation_condition", "submission_compliance", "evaluator_disclosure", "pointwise_declaration"}
FORBIDDEN_ROLES = {"introduction", "related_work"}


def lcs_len(a: str, b: str) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for ca in a:
        cur = [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            if ca == cb:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def cluster(sents: list[str], min_lcs: int) -> list[list[int]]:
    n = len(sents)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    norm = [re.sub(r"[\s〈〉《》「」“”‘’,，。；;:：()（）\[\]【】]+", "", s) for s in sents]
    for i in range(n):
        for j in range(i + 1, n):
            if lcs_len(norm[i], norm[j]) >= min_lcs:
                parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--per20", type=int, default=10, help="每 20 页允许的防御句上限")
    ap.add_argument("--lcs", type=int, default=12, help="同边界聚类的最长公共子串阈值（字）")
    ap.add_argument("--no-pdf", action="store_true", help="只按源码计数（PDF 缺失时）")
    ap.add_argument("--floor-review", action="store_true", help="下限不足记 REVIEW 而非 HARD_FAIL")
    args = ap.parse_args()

    if not args.config.is_file():
        print(f"ERROR: 配置不存在: {args.config}", file=sys.stderr)
        return 2
    cfg = ls.load_config(args.config)
    ex = ls.load_exemptions(cfg.exemptions).get("hedge_budget", [])
    bad_tags = [e for e in ex if e.get("tag") not in ALLOWED_TAGS]
    if bad_tags:
        for e in bad_tags:
            print(f"ERROR: 豁免标签不合法: {e.get('tag')!r}（{e['match'][:30]}）", file=sys.stderr)
        return 2

    units = cfg.units()
    if not units:
        print("ERROR: 没有切出任何段落单元", file=sys.stderr)
        return 2

    # --- 源码侧：按角色归属 ---
    hits: list[tuple[str, str, str, dict | None]] = []   # (role, unit_id, sentence, exemption)
    boundary_by_role: dict[str, int] = {}
    for u in units:
        for s in u.sentences():
            if BOUNDARY.search(s):
                boundary_by_role[u.role] = boundary_by_role.get(u.role, 0) + 1
            if DEFENSIVE.search(s):
                hits.append((u.role, u.unit_id, s, ls.exempted(s, ex)))

    counted = [h for h in hits if h[3] is None and h[0] != "abstract"]
    position_viol = [h for h in counted if h[0] in FORBIDDEN_ROLES]
    review_items: list[str] = []
    fail_items: list[str] = []

    # --- PDF 侧：上限按可见文本计 ---
    pages = None
    pdf_count = None
    if cfg.pdf and cfg.pdf.is_file() and not args.no_pdf:
        pages = ls.pdf_page_count(cfg.pdf)
        text = ls.pdf_to_text(cfg.pdf)
        # 去掉摘要段（摘要不计入额度）：取「摘要」到第一个「引言/Introduction」之间
        text_wo_abs = re.sub(r"摘要.*?(?=1\s*引言|引言|1\s+Introduction)", "", text, count=1, flags=re.S)
        sents = ls.split_sentences(re.sub(r"\s+", "", text_wo_abs)) if False else re.split(r"(?<=[。；！？])", re.sub(r"[ \t]*\n[ \t]*", "", text_wo_abs))
        pdf_hits = [s for s in sents if DEFENSIVE.search(s) and ls.exempted(s, ex) is None]
        pdf_count = len(pdf_hits)
    else:
        if not args.no_pdf:
            review_items.append("配置未给 PDF 或文件缺失：上限按源码计数，正式验收须在 PDF 上复核")
    budget = math.ceil(args.per20 * (pages or 20) / 20)
    effective = pdf_count if pdf_count is not None else len(counted)

    # --- 同边界 ≤ 2 ---
    sent_list = [h[2] for h in counted]
    groups = cluster(sent_list, args.lcs)
    dup_viol = [g for g in groups if len(g) > 2]

    # --- 下限 ---
    floor_missing = [r for r in ("results", "conclusion") if boundary_by_role.get(r, 0) < 1]

    # --- 汇总 ---
    print("DEFENSIVE SENTENCES（源码侧，按角色）")
    for role in ls.ROLE_ORDER:
        rs = [h for h in hits if h[0] == role]
        if not rs:
            continue
        print(f"  [{role}] {len(rs)} 句" + ("（摘要不计入额度）" if role == "abstract" else ""))
        for _, uid, s, e in rs:
            tag = f"  ⟵ 豁免[{e['tag']}]" if e else ""
            print(f"     {uid}: {s[:70]}{tag}")
    print()
    print("BOUNDARY SENTENCES（适用范围句，按角色）: " +
          ", ".join(f"{r}={boundary_by_role.get(r, 0)}" for r in ("results", "conclusion", "model", "method")))
    print()

    if effective > budget:
        fail_items.append(f"上限：实测 {effective} 句 > 允许 {budget} 句（{pages or 20} 页 × {args.per20}/20）")
    if position_viol:
        fail_items.append("位置：引言/相关工作出现防御句 " + "; ".join(f"{h[1]}" for h in position_viol))
    for g in dup_viol:
        fail_items.append("同边界 > 2 次：\n" + "\n".join(f"       - {sent_list[i][:60]}" for i in g))
    if floor_missing:
        msg = "下限：以下章节缺适用范围句 " + "/".join(floor_missing) + "（成对规则：删光边界=夸大）"
        (review_items if args.floor_review else fail_items).append(msg)
    roles_of = [h[0] for h in counted]
    for g in groups:
        if len(g) == 2:
            rs = {roles_of[i] for i in g}
            if rs == {"results", "conclusion"}:
                continue  # 04-hedging §二 明文允许：主张处 1 次 + 结论呼应 1 次
            review_items.append("同边界在同一章出现 2 次（允许上限，确认后一处不加码）：" + " | ".join(sent_list[i][:40] for i in g))

    verdict = "HARD_FAIL" if fail_items else ("REVIEW_REQUIRED" if review_items else "PASS")
    code = 1 if fail_items else (4 if review_items else 0)
    lines = [
        f"页数：{pages if pages else '未知(按20)'}；上限：{budget}；PDF 侧计数：{pdf_count if pdf_count is not None else '—'}；源码侧计数：{len(counted)}（豁免 {sum(1 for h in hits if h[3])}）",
        f"位置违规：{len(position_viol)}；同边界簇：{len(groups)}（>2 的 {len(dup_viol)}）；下限缺失：{floor_missing or '无'}",
    ]
    if fail_items:
        lines.append("失败项：")
        lines.extend("  - " + x.replace("\n", "\n    ") for x in fail_items)
    if review_items:
        lines.append("待审项：")
        lines.extend("  - " + x for x in review_items)
    ls.print_proof("hedge_budget", verdict, lines, code)
    return code


if __name__ == "__main__":
    sys.exit(main())
