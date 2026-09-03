#!/usr/bin/env python3
"""make_fixtures.py — 生成 tests/fixtures 下的合成用例（幂等，可重复运行）。

用例只含合成片段，不含任何真稿文字。每个用例目录：case.json + 最小 LaTeX/大纲。
新增一条真实事故 → 在这里加一个用例，再跑 scripts/run_regressions.py。
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIX = ROOT / "fixtures"


def w(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


def cfg(d: Path, **extra) -> None:
    base = {"sections": ["sections"], "outline": "outline.md", "main": "main.tex",
            "roles": {"05_results": "results", "06_conclusion": "conclusion"}}
    base.update(extra)
    w(d / "paper.gates.json", j(base))


MAIN = r"""\documentclass{article}
\newcommand{\method}{STR-FCM-TBD}
\newcommand{\gtmethod}{适配 GT-ML-PDA}
\begin{document}
\input{sections/00_abstract}
\end{document}
"""
ABS_NO_GT = r"""\begin{abstract}
本文提出 \method 方法。在 900 个非零转弯场景中，\method 相对近似恒速基线的 GOSPA 平均降低 \PrimaryMean m。
\end{abstract}
"""
ABS_GT = r"""\begin{abstract}
本文提出 \method 方法。在 900 个非零转弯场景中，\method 相对近似恒速基线的 GOSPA 平均降低 \PrimaryMean m；与 \gtmethod 的补充比较中平均 GOSPA 低 56.00 m。
\end{abstract}
"""
INTRO_CLEAN = r"""\section{引言}
群目标由多个空间邻近的成员构成。同一量测不能被多个成员重复使用，因此需要在同一评分过程中处理关联。
"""
INTRO_DEF = r"""\section{引言}
群目标由多个空间邻近的成员构成。本文结果不应据此外推到任意构型。
"""
RESULTS = r"""\section{仿真结果}
\subsection{与适配 GT-ML-PDA 的补充比较}
在同一批阈后观测上，\gtmethod 的平均 GOSPA 比 \method 高 56.00 m（表~\ref{tab:gt}）。该结论在二维、已知五成员刚性槽位条件下建立。

消融结果尚不能区分幅度标记与关联边缘化各自的独立贡献，本文将性能归因于整体机制。
"""
CONCL_OK = r"""\section{结论}
本文提出 \method。该结论覆盖两种五成员刚性构型、有限 SNR 和转弯率条件。消融结果尚不能区分幅度标记与关联边缘化各自的独立贡献，本文将性能归因于整体机制。
"""
CONCL_NOBOUND = r"""\section{结论}
本文提出 \method，为机动低可观测刚性编队提供了统一的组级运动建模方法。
"""
OUTLINE_OK = """# 大纲

## 4. 主张—证据闭环表

| 主张 | 证据挂接 | 封口结论与边界 |
|---|---|---|
| 共享率搜索改善机动场景 | 图 3、表 2；900 个非零率场景 | 支持受测条件下的正平均收益，不表示每次仿真都改善 |
| 适配 GT 补充比较 | 表 4；1050 次配对仿真 | 只描述适配实现下的整体系统差异 |
"""
OUTLINE_BAD = """# 大纲

## 4. 主张—证据闭环表

| 主张 | 证据挂接 | 封口结论与边界 |
|---|---|---|
| 共享率搜索改善机动场景 | 效果很好 | |
"""

GT_CFG = dict(external_baselines=["GT-ML-PDA"], method_names=["STR-FCM-TBD"],
              baseline_aliases={"GT-ML-PDA": ["适配 GT-ML-PDA"]})


def std_sections(d: Path, abstract=ABS_GT, intro=None, results=RESULTS, concl=CONCL_OK, outline=OUTLINE_OK):
    w(d / "main.tex", MAIN)
    w(d / "outline.md", outline)
    w(d / "sections/00_abstract.tex", abstract)
    if intro is not None:
        w(d / "sections/01_introduction.tex", intro)
    w(d / "sections/05_results.tex", results)
    w(d / "sections/06_conclusion.tex", concl)

# ---------- M2：semantic_diff / change_ledger / term_variants ----------
RES_OLD = r"""\section{仿真结果}
在 900 个非零转弯场景中，\method 的 GOSPA 平均降低 61.92 m（图~\ref{fig:gospa}），95\% 配对自助区间不包含零。

与 \gtmethod 的补充比较在同一批阈后观测上进行，样本量为 1050 次配对仿真。
"""
RES_NUM_CHANGED = RES_OLD.replace("61.92", "62.19")
RES_REWORDED = r"""\section{仿真结果}
\method 在 900 个非零转弯场景中使 GOSPA 平均降低 61.92 m（图~\ref{fig:gospa}），且 95\% 配对自助区间不包含零。

与 \gtmethod 的补充比较在同一批阈后观测上进行，样本量为 1050 次配对仿真。
"""
RES_FLIPPED = RES_OLD.replace("区间不包含零", "区间包含零")
RES_MOVED = r"""\section{仿真结果}
在 900 个非零转弯场景中，\method 的 GOSPA 平均降低（图~\ref{fig:gospa}），95\% 配对自助区间不包含零。

与 \gtmethod 的补充比较在同一批阈后观测上进行，样本量为 1050 次配对仿真，平均降低 61.92 m。
"""
GLOSSARY_OK = """# 术语表

| 冻结词 | 首选外文 | 使用语境 | 避免用法 |
|---|---|---|---|
| 过门限量测 | thresholded measurement | 全文 | 不写 thresholded detection；不称 `过阈点` |
| 刚性编队 | rigid formation | 全文 | `fixed-slot group` |
"""
LEDGER_ACCEPT = """{"unit_id": "05_results#2", "covers": ["05_results#2"], "decision": "accept", "reason_code": "number_to_macro", "round": 2}
"""
LEDGER_REJECT = """{"unit_id": "05_results#2", "covers": ["05_results#2"], "decision": "reject", "reason_code": "number_to_macro", "round": 2}
"""


def m2_fixtures() -> None:
    # semantic_diff：目录对
    def two_dirs(d: Path, old: str, new: str) -> None:
        w(d / "old" / "05_results.tex", old); w(d / "new" / "05_results.tex", new)

    d = FIX / "semantic_diff" / "number_changed"
    two_dirs(d, RES_OLD, RES_NUM_CHANGED)
    w(d / "case.json", j({"kind": "must_change", "gate": "semantic_diff",
                          "args": ["--old", "{dir}/old", "--new", "{dir}/new"],
                          "expect_exit": 1, "expect_contains": ["数值变化：-{'61.92': 1} +{'62.19': 1}"]}))
    d = FIX / "semantic_diff" / "equal_length_reword"
    two_dirs(d, RES_OLD, RES_REWORDED)
    w(d / "case.json", j({"kind": "must_preserve", "gate": "semantic_diff",
                          "args": ["--old", "{dir}/old", "--new", "{dir}/new"],
                          "expect_exit": 0, "expect_contains": ["判定：PASS"]}))
    d = FIX / "semantic_diff" / "direction_flip"
    two_dirs(d, RES_OLD, RES_FLIPPED)
    w(d / "case.json", j({"kind": "manual_review", "gate": "semantic_diff",
                          "args": ["--old", "{dir}/old", "--new", "{dir}/new"],
                          "expect_exit": 4, "expect_contains": ["方向翻转：ci_excl0 → ci_incl0"],
                          "expect_not_contains": ["HARD_FAIL"]}))
    d = FIX / "semantic_diff" / "number_moved_between_paragraphs"
    two_dirs(d, RES_OLD, RES_MOVED)
    w(d / "case.json", j({"kind": "manual_review", "gate": "semantic_diff",
                          "args": ["--old", "{dir}/old", "--new", "{dir}/new"],
                          "expect_exit": 4, "expect_contains": ["在同文件段落间移动"],
                          "expect_not_contains": ["HARD_FAIL"]}))
    # semantic_diff：中→英段落对
    d = FIX / "semantic_diff" / "zh_en_pairs_ok"
    w(d / "pairs.json", j([{"id": "05#1",
                            "old": "在 900 个非零转弯场景中，GOSPA 平均降低 61.92 m，95\\% 配对自助区间不包含零。",
                            "new": "Across 900 non-zero-turn scenes, the GOSPA decreases by 61.92 m on average; the 95\\% paired bootstrap interval excludes zero."}]))
    w(d / "case.json", j({"kind": "must_preserve", "gate": "semantic_diff",
                          "args": ["--pairs", "{dir}/pairs.json", "--mode", "ze"],
                          "expect_exit": 0, "expect_contains": ["判定：PASS"]}))
    d = FIX / "semantic_diff" / "zh_en_number_mismatch"
    w(d / "pairs.json", j([{"id": "05#1",
                            "old": "在 900 个非零转弯场景中，GOSPA 平均降低 61.92 m。",
                            "new": "Across 900 non-zero-turn scenes, the GOSPA decreases by 61.29 m on average."}]))
    w(d / "case.json", j({"kind": "must_change", "gate": "semantic_diff",
                          "args": ["--pairs", "{dir}/pairs.json", "--mode", "ze"],
                          "expect_exit": 1, "expect_contains": ["数值变化"]}))

    # change_ledger：临时 git 仓库（run_regressions 的 git_case）
    def git_pair(d: Path, ledger) -> None:
        for sub in ("base", "new"):
            cfg(d / sub); std_sections(d / sub, results=RES_OLD if sub == "base" else RES_NUM_CHANGED)
        if ledger is not None:
            w(d / "new" / "edits" / "units.jsonl", ledger)

    d = FIX / "change_ledger" / "unaccounted_edit"
    git_pair(d, None)
    w(d / "case.json", j({"kind": "must_change", "gate": "change_ledger", "git_case": {"base": "base", "new": "new"},
                          "args": ["--config", "{dir}/paper.gates.json", "--base-rev", "HEAD"],
                          "expect_exit": 1, "expect_contains": ["未归因 1", "05_results#2"]}))
    d = FIX / "change_ledger" / "accounted_edit"
    git_pair(d, LEDGER_ACCEPT)
    w(d / "case.json", j({"kind": "must_preserve", "gate": "change_ledger", "git_case": {"base": "base", "new": "new"},
                          "args": ["--config", "{dir}/paper.gates.json", "--base-rev", "HEAD"],
                          "expect_exit": 0, "expect_contains": ["已归因 1；未归因 0"]}))
    d = FIX / "change_ledger" / "rejected_but_changed"
    git_pair(d, LEDGER_REJECT)
    w(d / "case.json", j({"kind": "must_change", "gate": "change_ledger", "git_case": {"base": "base", "new": "new"},
                          "args": ["--config", "{dir}/paper.gates.json", "--base-rev", "HEAD"],
                          "expect_exit": 1, "expect_contains": ["未归因 1", "账本判 reject 的单元仍发生了改动"]}))

    # term_variants
    d = FIX / "term_variants" / "avoided_form_hit"
    cfg(d, glossary="glossary.md"); std_sections(d, results=RES_OLD.replace("阈后观测", "thresholded detection"))
    w(d / "glossary.md", GLOSSARY_OK)
    w(d / "case.json", j({"kind": "must_change", "gate": "term_variants",
                          "args": ["--config", "{dir}/paper.gates.json", "--no-pdf"],
                          "expect_exit": 1, "expect_contains": ["避免用法「thresholded detection」"]}))
    d = FIX / "term_variants" / "clean_glossary"
    cfg(d, glossary="glossary.md"); std_sections(d, results=RES_OLD); w(d / "glossary.md", GLOSSARY_OK)
    w(d / "case.json", j({"kind": "must_preserve", "gate": "term_variants",
                          "args": ["--config", "{dir}/paper.gates.json", "--no-pdf"],
                          "expect_exit": 0, "expect_contains": ["判定：PASS"]}))
    grp = RES_OLD.replace("非零转弯场景", "转弯率假设覆盖的场景") + "\n每个率切片各自搜索一次；率切片之间不共享候选。\n"
    d = FIX / "term_variants" / "concept_group_review"
    cfg(d, glossary="glossary.md", concept_groups={"转弯率假设": ["率切片", "率假设"]}); std_sections(d, results=grp); w(d / "glossary.md", GLOSSARY_OK)
    w(d / "case.json", j({"kind": "manual_review", "gate": "term_variants",
                          "args": ["--config", "{dir}/paper.gates.json", "--no-pdf"],
                          "expect_exit": 4, "expect_contains": ["非规范形态「率切片」：源码 2 处"],
                          "expect_not_contains": ["非规范形态「率假设」"]}))
    d = FIX / "term_variants" / "concept_group_enforce"
    cfg(d, glossary="glossary.md", concept_groups={"转弯率假设": ["率切片"]}); std_sections(d, results=grp); w(d / "glossary.md", GLOSSARY_OK)
    w(d / "case.json", j({"kind": "must_change", "gate": "term_variants",
                          "args": ["--config", "{dir}/paper.gates.json", "--no-pdf", "--enforce"],
                          "expect_exit": 1, "expect_contains": ["非规范形态「率切片」"]}))

# ---------- M3：style_audit（软诊断：永不退出 1） ----------
STYLE_TEMPLATE_HEAVY = r"""\section{仿真结果}
值得注意的是，所提方法在各种场景下均显著提升了跟踪精度。然而，传统方法难以有效解决这一问题。因此，本文方法具有重要意义。此外，实验充分验证了方法的有效性。总之，该方法为后续研究奠定了坚实基础。

图~\ref{fig:a} 给出了各方法的对比结果。所提方法优于基线方法。该方法有效地改善了低信噪比条件下幅度证据不足导致的关联歧义增加问题。
"""
STYLE_CLEAN = r"""\section{仿真结果}
在 900 个非零转弯场景中，\method 的 GOSPA 平均降低 61.92 m（图~\ref{fig:gospa}），95\% 配对自助区间不包含零。收益集中在转弯率较大的场景：率越大，恒速近似的预测偏差越大，共享率搜索的补偿也越明显。

与 \gtmethod 的补充比较在同一批阈后观测上进行，样本量为 1050 次配对仿真。
"""


def m3_fixtures() -> None:
    d = FIX / "style_audit" / "template_heavy_never_fails"
    w(d / "sections/05_results.tex", STYLE_TEMPLATE_HEAVY)
    w(d / "case.json", j({"kind": "manual_review", "gate": "style_audit",
                          "args": ["--tex", "{dir}/sections", "--top", "5"],
                          "expect_exit": 0,
                          "expect_contains": ["template_phrase", "generic_closing", "figure_first_opening", "connector_density", "判定：PASS"],
                          "expect_not_contains": ["HARD_FAIL"]}))
    d = FIX / "style_audit" / "review_at_threshold"
    w(d / "sections/05_results.tex", STYLE_TEMPLATE_HEAVY)
    w(d / "case.json", j({"kind": "manual_review", "gate": "style_audit",
                          "args": ["--tex", "{dir}/sections", "--review-at", "1"],
                          "expect_exit": 4, "expect_contains": ["REVIEW_REQUIRED"], "expect_not_contains": ["HARD_FAIL"]}))
    d = FIX / "style_audit" / "clean_results_paragraphs"
    cfg(d); std_sections(d, results=STYLE_CLEAN)
    w(d / "case.json", j({"kind": "must_preserve", "gate": "style_audit",
                          "args": ["--config", "{dir}/paper.gates.json", "--review-at", "1"],
                          "expect_exit": 0, "expect_contains": ["高优先级 0", "判定：PASS"]}))
    d = FIX / "style_audit" / "protected_unit_not_counted"
    cfg(d, protected_units=["05_results#2", "05_results#3"]); std_sections(d, results=STYLE_TEMPLATE_HEAVY)
    w(d / "case.json", j({"kind": "must_preserve", "gate": "style_audit",
                          "args": ["--config", "{dir}/paper.gates.json", "--review-at", "1"],
                          "expect_exit": 0, "expect_contains": ["保护段，不改", "高优先级 0"]}))

# ---------- M5：写稿阶段（半成品稿 / 只有骨架） ----------
def m5_fixtures() -> None:
    def half_draft(d: Path) -> None:
        cfg(d, glossary="glossary.md", **GT_CFG)
        w(d / "main.tex", MAIN); w(d / "outline.md", OUTLINE_OK); w(d / "glossary.md", GLOSSARY_OK)
        w(d / "sections/00_abstract.tex", ABS_GT); w(d / "sections/01_introduction.tex", INTRO_CLEAN)

    d = FIX / "hedge_budget" / "floor_present_only_half_draft"
    half_draft(d)
    w(d / "case.json", j({"kind": "must_preserve", "gate": "hedge_budget",
                          "args": ["--config", "{dir}/paper.gates.json", "--no-pdf", "--floor-present-only"],
                          "expect_exit": 0, "expect_contains": ["下限跳过尚未写出的章节", "下限缺失：无"]}))
    d = FIX / "hedge_budget" / "floor_default_half_draft"
    half_draft(d)
    w(d / "case.json", j({"kind": "must_change", "gate": "hedge_budget",
                          "args": ["--config", "{dir}/paper.gates.json", "--no-pdf"],
                          "expect_exit": 1, "expect_contains": ["下限：以下章节缺适用范围句 results/conclusion"]}))
    d = FIX / "claim_ledger" / "skeleton_no_results_yet"
    half_draft(d)
    w(d / "case.json", j({"kind": "must_preserve", "gate": "claim_ledger",
                          "args": ["--config", "{dir}/paper.gates.json"],
                          "expect_exit": 0, "expect_contains": ["基线镜像跳过"], "expect_not_contains": ["摘要未提及"]}))
    d = FIX / "run_gates" / "stage_chapter_half_draft"
    half_draft(d)
    w(d / "case.json", j({"kind": "must_preserve", "gate": "run_gates",
                          "args": ["--config", "{dir}/paper.gates.json", "--stage", "chapter"],
                          "expect_exit": 0, "expect_contains": ["VERDICT: STAGE_OK"], "expect_not_contains": ["FROZEN_OK"]}))
    d = FIX / "run_gates" / "stage_freeze_half_draft"
    half_draft(d)
    w(d / "case.json", j({"kind": "must_change", "gate": "run_gates",
                          "args": ["--config", "{dir}/paper.gates.json", "--stage", "freeze"],
                          "expect_exit": 1, "expect_contains": ["VERDICT: TARGETED"], "expect_not_contains": ["STAGE_OK"]}))
    d = FIX / "run_gates" / "stage_skeleton_outline_only"
    cfg(d, glossary="glossary.md", **GT_CFG)
    w(d / "main.tex", MAIN); w(d / "outline.md", OUTLINE_OK); w(d / "glossary.md", GLOSSARY_OK); w(d / "sections/.gitkeep", "")
    w(d / "case.json", j({"kind": "must_preserve", "gate": "run_gates",
                          "args": ["--config", "{dir}/paper.gates.json", "--stage", "skeleton"],
                          "expect_exit": 0, "expect_contains": ["VERDICT: STAGE_OK"]}))
    d = FIX / "run_gates" / "stage_skeleton_dangling_claim"
    cfg(d, glossary="glossary.md", **GT_CFG)
    w(d / "main.tex", MAIN); w(d / "outline.md", OUTLINE_BAD); w(d / "glossary.md", GLOSSARY_OK); w(d / "sections/.gitkeep", "")
    w(d / "case.json", j({"kind": "must_change", "gate": "run_gates",
                          "args": ["--config", "{dir}/paper.gates.json", "--stage", "skeleton"],
                          "expect_exit": 1, "expect_contains": ["VERDICT: TARGETED"]}))


def main() -> None:
    # ---------- claim_ledger ----------
    d = FIX / "claim_ledger" / "abstract_missing_baseline"
    cfg(d, **GT_CFG); std_sections(d, abstract=ABS_NO_GT)
    w(d / "case.json", j({"kind": "must_change", "gate": "claim_ledger",
                          "args": ["--config", "{dir}/paper.gates.json"],
                          "expect_exit": 1, "expect_contains": ["摘要未提及"]}))

    d = FIX / "claim_ledger" / "abstract_mirrored"
    cfg(d, **GT_CFG); std_sections(d)
    w(d / "case.json", j({"kind": "must_preserve", "gate": "claim_ledger",
                          "args": ["--config", "{dir}/paper.gates.json"],
                          "expect_exit": 4, "expect_not_contains": ["摘要未提及", "HARD_FAIL"],
                          "expect_contains": ["结论未提及"]}))

    d = FIX / "claim_ledger" / "ledger_dangling_claim"
    cfg(d, **GT_CFG); std_sections(d, outline=OUTLINE_BAD)
    w(d / "case.json", j({"kind": "must_change", "gate": "claim_ledger",
                          "args": ["--config", "{dir}/paper.gates.json"],
                          "expect_exit": 1, "expect_contains": ["证据钩子", "封口/边界列为空"]}))

    # ---------- hedge_budget ----------
    d = FIX / "hedge_budget" / "intro_defensive"
    cfg(d); std_sections(d, intro=INTRO_DEF)
    w(d / "case.json", j({"kind": "must_change", "gate": "hedge_budget",
                          "args": ["--config", "{dir}/paper.gates.json", "--no-pdf"],
                          "expect_exit": 1, "expect_contains": ["位置：引言/相关工作出现防御句"]}))

    d = FIX / "hedge_budget" / "sanctioned_pair"
    cfg(d); std_sections(d, intro=INTRO_CLEAN)
    w(d / "case.json", j({"kind": "must_preserve", "gate": "hedge_budget",
                          "args": ["--config", "{dir}/paper.gates.json", "--no-pdf"],
                          "expect_exit": 0, "expect_not_contains": ["同边界在同一章出现 2 次"]}))

    d = FIX / "hedge_budget" / "conclusion_no_boundary"
    cfg(d); std_sections(d, intro=INTRO_CLEAN, concl=CONCL_NOBOUND)
    w(d / "case.json", j({"kind": "must_change", "gate": "hedge_budget",
                          "args": ["--config", "{dir}/paper.gates.json", "--no-pdf"],
                          "expect_exit": 1, "expect_contains": ["下限", "conclusion"]}))

    d = FIX / "hedge_budget" / "bad_exemption_tag"
    cfg(d, exemptions="paper.exemptions.json")
    many = "\\section{仿真结果}\n" + "\n\n".join(f"该指标并不表示第{i}项结论成立。" for i in range(1, 13)) \
        + "\n\n该结论在二维条件下建立。\n"
    std_sections(d, intro=INTRO_CLEAN, results=many)
    w(d / "paper.exemptions.json", j({"hedge_budget": [{"match": "第1项", "tag": "not_a_tag", "reason": "x"}]}))
    w(d / "case.json", j({"kind": "manual_review", "gate": "hedge_budget",
                          "args": ["--config", "{dir}/paper.gates.json", "--no-pdf"],
                          "expect_exit": 2, "expect_contains": ["豁免标签不合法"]}))

    d = FIX / "hedge_budget" / "over_budget"
    cfg(d); std_sections(d, intro=INTRO_CLEAN, results=many)
    w(d / "case.json", j({"kind": "must_change", "gate": "hedge_budget",
                          "args": ["--config", "{dir}/paper.gates.json", "--no-pdf"],
                          "expect_exit": 1, "expect_contains": ["上限：实测"]}))

    # ---------- page_fill ----------
    two = {"two_col": True}
    d = FIX / "page_fill" / "half_page_before_float"
    w(d / "case.json", j({"kind": "must_change", "gate": "page_fill", "args": ["--pgm-dir", "{dir}/pgm"],
                          "synth_pgm": [{"fill": 1.0, **two}, {"fill": 0.4, **two}, {"fill": 1.0, **two}, {"fill": 0.3, **two}],
                          "expect_exit": 1, "expect_contains": ["超阈页：[2]"]}))
    d = FIX / "page_fill" / "right_column_empty"
    w(d / "case.json", j({"kind": "must_change", "gate": "page_fill", "args": ["--pgm-dir", "{dir}/pgm"],
                          "synth_pgm": [{"fill": 1.0, **two}, {"fill": 1.0, "right_fill": 0.2, **two}, {"fill": 0.5, **two}],
                          "expect_exit": 1, "expect_contains": ["超阈页：[2]"]}))
    d = FIX / "page_fill" / "full_pages_last_short"
    w(d / "case.json", j({"kind": "must_preserve", "gate": "page_fill", "args": ["--pgm-dir", "{dir}/pgm"],
                          "synth_pgm": [{"fill": 1.0, **two}, {"fill": 0.95, **two}, {"fill": 0.2, **two}],
                          "expect_exit": 0, "expect_contains": ["末页，不计"]}))
    d = FIX / "page_fill" / "exempted_page"
    w(d / "paper.exemptions.json", j({"page_fill": [{"page": 2, "reason": "章末 clearpage，导师认可"}]}))
    w(d / "case.json", j({"kind": "manual_review", "gate": "page_fill",
                          "args": ["--pgm-dir", "{dir}/pgm", "--exemptions", "{dir}/paper.exemptions.json"],
                          "synth_pgm": [{"fill": 1.0}, {"fill": 0.4}, {"fill": 1.0}],
                          "expect_exit": 0, "expect_contains": ["已豁免页：[2]"]}))

    # ---------- latex_scope ----------
    d = FIX / "latex_scope" / "units_and_roles"
    cfg(d); std_sections(d)
    w(d / "case.json", j({"kind": "must_preserve", "gate": "latex_scope", "args": ["{dir}/paper.gates.json"],
                          "expect_exit": 0, "expect_contains": ["abstract       1", "results        4", "conclusion     2"]}))

    m2_fixtures()
    m3_fixtures()
    m5_fixtures()

    # ---------- golden 模板 ----------
    w(ROOT / "golden" / "local_paths.example.json", j({"cases": [
        {"name": "paper1_final", "config": "C:/path/to/paper1.gates.json",
         "only": ["claim_ledger", "hedge_budget", "page_fill", "term_variants", "style_audit"], "expect_verdict": "REVIEW"},
        {"name": "paper1_final_contract_gates_clean_tree", "config": "C:/path/to/paper1.gates.json",
         "only": ["change_ledger", "semantic_diff"], "expect_verdict": "FROZEN_OK"},
        {"name": "paper2_draft", "config": "C:/path/to/paper2.gates.json",
         "only": ["claim_ledger", "hedge_budget", "page_fill", "term_variants", "style_audit"], "expect_verdict": "TARGETED"},
        {"name": "paper1_hist_snapshot_abstract_missing_baseline", "config": "C:/path/to/paper1_<rev>.gates.json",
         "only": ["claim_ledger"], "expect_verdict": "TARGETED"},
        {"name": "paper1_hist_semdiff_replay", "script": "semantic_diff",
         "args": ["--config", "C:/path/to/paper1.gates.json", "--old-rev", "<old>", "--new-rev", "<new>", "--quiet-pass"],
         "expect_exit": 1, "expect_contains": ["数值变化"]}]}))
    print("fixtures:", len(list(FIX.glob("*/*/case.json"))))


if __name__ == "__main__":
    main()
