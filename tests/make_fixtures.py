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
    p.write_text(text, encoding="utf-8")


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

    # ---------- golden 模板 ----------
    w(ROOT / "golden" / "local_paths.example.json", j({"cases": [
        {"name": "paper1_final", "config": "C:/path/to/paper1.gates.json",
         "only": ["claim_ledger", "hedge_budget", "page_fill"], "expect_verdict": "REVIEW"},
        {"name": "paper2_draft", "config": "C:/path/to/paper2.gates.json",
         "only": ["claim_ledger", "hedge_budget", "page_fill"], "expect_verdict": "TARGETED"}]}))
    print("fixtures:", len(list(FIX.glob("*/*/case.json"))))


if __name__ == "__main__":
    main()
