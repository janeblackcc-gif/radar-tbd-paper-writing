#!/usr/bin/env python3
"""style_audit.py — 表层自然度软诊断（第 4 层）。只出热区，永不因风格判失败。

它回答的是「哪几段最像模板 / 最不像人写的」，不回答「稿子合不合格」——合格与否由硬门决定。
所以：退出码 0 = 已诊断；只有 --review-at N 且高优先级热区 ≥ N 时退出 4（REVIEW_REQUIRED）；
永不退出 1。风格热区不能覆盖任何硬门失败，也不构成改动事实、方向、术语的理由（11-naturalness.md）。

段落信号（每段可触发多项；severity = 触发信号数；≥ 3 为高优先级热区）：
    template_phrase      模板句 / 套话（值得注意的是、具有重要意义、为…提供了…基础 …）
    connector_density    句首连接词占句数 ≥ 50%（且 ≥ 3 句）
    repeated_opening     同一两字起句在段内 ≥ 3 次
    uniform_rhythm       ≥ 4 句且句长变异系数 < 0.20（每句一样长）
    long_sentence        单句 > 90 字（中文）/ > 45 词（英文）
    paragraph_too_long   > 8 句（10-chinese §九）
    four_char_hype       四字格空评价（显著提升、大幅改善、充分验证 …）
    adverbial_padding    「××地 + 动词」≥ 2 处
    passive_marker       「被」字句占句数 ≥ 50%
    generic_closing      末句是泛化收束（为…奠定了基础、具有…意义 …）
    figure_first_opening 段首是「图 X 给出 / 如图所示」而不是现象（02-narrative 结果章 §段首）
    noun_chain           无助词连续汉字 ≥ 12 字（10-chinese §五 名词链）
    triple_de            「…的…的…的」三重「的」
    claim_far_from_evidence  结果章里含比较/断言线索的句子，本句与相邻句都没有图表 / 数字 / 区间钩子

文档级指标（--json 落盘后可作 --baseline 对比）：
    句长均值 / 变异系数、连接词密度、模板句每千字、全文重复起句 top、图表空转起句数、
    结果先行比（结果章段首含结论或数字的段落占比）、名词链段数、孤儿缩写（从未在括号里定义）、
    术语首用无定义线索（需 glossary）、项目方言命中（需 banned_terms）、各文件段长整齐度

用法:
    python style_audit.py --config paper.gates.json [--top 10] [--review-at 0] [--json out.json] [--baseline prev.json]
    python style_audit.py --tex sections_zh [...]
退出码: 0 = 已诊断, 4 = 高优先级热区 ≥ --review-at, 2 = 用法/环境错误
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latex_scope as ls  # noqa: E402

# ---------------------------------------------------------------- 词典（自行整理；不来自任何外部仓库）
TEMPLATE_ZH = re.compile(
    r"值得注意的是|需要指出的是|不难看出|不难发现|可以看出|由此可见|综上所述|总的来说|总而言之|在很大程度上|一定程度上|某种程度上|"
    r"具有[^，。；]{0,6}意义|起到了[^，。；]{0,8}作用|发挥了[^，。；]{0,8}作用|"
    r"为[^，。；]{2,14}(?:提供了|奠定了|打下了)[^，。；]{0,10}(?:基础|参考|依据|支撑|思路|保障|视角|途径)|"
    r"随着[^，。；]{2,16}(?:发展|进步|提高|深入)|近年来|受到(?:了)?(?:广泛|越来越多的)关注|众所周知|毋庸置疑|显而易见|"
    r"从根本上|全方位|多角度|深入(?:地)?(?:分析|探讨|研究)|旨在|致力于|与此同时|不容忽视|不可或缺|至关重要|尤为重要|"
    r"具有(?:良好|较好|较强|优异|出色)的|表现出(?:良好|较好|较强|优异|出色)的")
TEMPLATE_EN = re.compile(
    r"\b(?:it is worth noting|it should be noted|in recent years|has attracted (?:considerable|significant|much|wide) attention|"
    r"plays? an? (?:crucial|vital|key|important) role|paves? the way|sheds? light|it is well known|to the best of our knowledge|"
    r"in summary|in conclusion|comprehensive(?:ly)?|holistic|novel)\b", re.I)
FOUR_CHAR = re.compile(r"显著(?:提升|提高|改善|增强)|大幅(?:度)?(?:提升|提高|改善|降低)|充分(?:验证|证明|说明)|极大(?:地)?(?:提高|提升|改善)|"
                       r"有效(?:地)?(?:提升|提高|改善|解决)|明显(?:改善|提升|提高)|全面(?:提升|提高|改善)")
ADVERB_DI = re.compile(r"[一-鿿]{2}地(?=[一-鿿])")
CONNECTOR_ZH = re.compile(r"^(?:然而|因此|此外|同时|另外|首先|其次|再次|最后|总之|综上|换言之|也就是说|与此同时|进一步|更重要的是|一方面|另一方面|"
                          r"不难看出|可以看出|由此可见|值得注意的是|需要指出的是|因而|所以|但是|不过|于是|从而|同样|此时|据此|由此)")
CONNECTOR_EN = re.compile(r"^(?:however|therefore|moreover|furthermore|in addition|additionally|consequently|thus|hence|finally|"
                          r"first(?:ly)?|second(?:ly)?|third(?:ly)?|meanwhile|nevertheless|nonetheless|overall|in summary|besides)\b", re.I)
GENERIC_CLOSING = re.compile(r"(?:奠定了|打下了)[^，。；]{0,10}基础|具有[^，。；]{0,8}(?:意义|价值)|提供了[^，。；]{0,10}(?:参考|依据|支撑|思路|保障)|"
                             r"发挥[^，。；]{0,8}作用|(?:开辟|拓展)了[^，。；]{0,8}(?:空间|方向)|具有(?:广阔|良好)的?应用前景")
FIGURE_FIRST = re.compile(r"^(?:如|由|从|在)?\s*(?:图|表)\s*(?:〈引〉|\d)|^(?:如图|如表)所示|^\s*(?:Fig(?:ure)?|Table)\s*(?:〈引〉|\d)", re.I)
#: 名词链在这些字处断开：助词、连词、介词、常见虚词。校准记录见 13-style-audit.md——
#: 定稿上 12 字阈值命中 37/87 段（「通过成功判据但覆盖率略降」也算），16 字才只剩真正的堆叠。
PARTICLES = set("的了是在与和对为将把被由用从到及或并而则即等其该此这那不无有以所之也就更很较均已"
                "但且因故若如使让令经向随自至于比按据沿同当仅只各另某")
NOUN_CHAIN_MIN = 16
LONG_SENT_ZH = 110   # 去掉括号内的英文术语后计
LATIN_PAREN = re.compile(r"[（(][^（）()]*[A-Za-z][^（）()]*[）)]")
TRIPLE_DE = re.compile(r"的[^，。；：]{1,8}的[^，。；：]{1,8}的")
CLAIM = re.compile(r"高于|低于|优于|劣于|降低|提高|减少|增加|改善|恶化|表明|说明|显示|证实|支持|超过|不及|一致|接近|"
                   r"\b(?:higher|lower|outperform|better|worse|improve|reduce|increase|decrease|indicate|show|confirm|support)", re.I)
EVIDENCE = re.compile(r"(?:图|表|Fig\.?|Figure|Table)\s*(?:〈引〉|\d)|〈式〉|〈宏〉|\d+(?:\.\d+)?\s*(?:m|%|dB|ms|s|km)\b|区间|置信|\d{2,}")
ACRO = re.compile(r"(?<![A-Za-z])([A-Z][A-Z0-9]{1,}(?:[-+][A-Z0-9]+)*)(?![a-z])")
ACRO_WHITELIST = {"PDF", "ID", "GPU", "CPU", "IEEE", "IET", "DOI", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "OK", "US", "UK", "URL", "PC"}
DEF_CUE = re.compile(r"称为|记为|定义为|定义|是指|所谓|即|简称|指的是|\bdenote|\bdefine|\brefer(?:s|red)? to as|\bcalled\b", re.I)


def lang_of(t: str) -> str:
    return "zh" if re.search(r"[一-鿿]", t) else "en"


def sentences(prose: str, lang: str) -> list[str]:
    if lang == "zh":
        parts = re.split(r"(?<=[。！？；])", prose)
    else:
        parts = re.split(r"(?<=[.!?;])\s+", prose)
    return [s.strip() for s in parts if s and len(s.strip()) >= 2]


def slen(s: str, lang: str) -> int:
    if lang == "zh":
        return len(re.sub(r"\s+", "", LATIN_PAREN.sub("", s)))
    return len(s.split())


def opening(s: str, lang: str) -> str:
    s = s.lstrip("「“（(")
    return s[:2] if lang == "zh" else " ".join(s.split()[:1]).lower()


def noun_chains(prose: str, min_len: int) -> list[str]:
    out, run = [], []
    for ch in prose:
        if "一" <= ch <= "鿿" and ch not in PARTICLES:
            run.append(ch)
        else:
            if len(run) >= min_len:
                out.append("".join(run))
            run = []
    if len(run) >= min_len:
        out.append("".join(run))
    return out


def audit_paragraph(u: ls.Unit, lang: str) -> tuple[dict[str, str], dict]:
    """返回 (信号 → 说明, 数值明细)。"""
    p = u.prose
    sents = sentences(p, lang)
    n = len(sents)
    sig: dict[str, str] = {}
    lens = [slen(s, lang) for s in sents]
    cv = (statistics.pstdev(lens) / statistics.mean(lens)) if n >= 2 and statistics.mean(lens) > 0 else 0.0
    tmpl = (TEMPLATE_ZH if lang == "zh" else TEMPLATE_EN).findall(p)
    if tmpl:
        sig["template_phrase"] = "、".join(dict.fromkeys(tmpl))[:60]
    conn_rx = CONNECTOR_ZH if lang == "zh" else CONNECTOR_EN
    n_conn = sum(1 for s in sents if conn_rx.search(s))
    if n >= 3 and n_conn / n >= 0.5:
        sig["connector_density"] = f"{n_conn}/{n} 句以连接词起"
    ops = Counter(opening(s, lang) for s in sents)
    rep = [(o, c) for o, c in ops.items() if c >= 3 and o.strip()]
    if rep:
        sig["repeated_opening"] = "、".join(f"「{o}」×{c}" for o, c in rep)
    if n >= 4 and cv < 0.20:
        sig["uniform_rhythm"] = f"{n} 句，句长 CV={cv:.2f}"
    long_lim = LONG_SENT_ZH if lang == "zh" else 45
    longs = [L for L in lens if L > long_lim]
    if longs:
        sig["long_sentence"] = f"最长 {max(longs)}" + ("字" if lang == "zh" else " 词")
    if n > 8:
        sig["paragraph_too_long"] = f"{n} 句"
    if lang == "zh":
        fc = FOUR_CHAR.findall(p)
        if fc:
            sig["four_char_hype"] = "、".join(dict.fromkeys(fc))
        n_di = len(ADVERB_DI.findall(p))
        if n_di >= 2:
            sig["adverbial_padding"] = f"「××地」{n_di} 处"
        n_bei = sum(1 for s in sents if "被" in s)
        if n >= 2 and n_bei / n >= 0.5:
            sig["passive_marker"] = f"{n_bei}/{n} 句含「被」"
        if sents and GENERIC_CLOSING.search(sents[-1]):
            sig["generic_closing"] = sents[-1][:40]
        chains = noun_chains(p, NOUN_CHAIN_MIN)
        if chains:
            sig["noun_chain"] = "、".join(f"{len(c)}:{c}" for c in chains[:2])
        if TRIPLE_DE.search(p):
            sig["triple_de"] = TRIPLE_DE.search(p).group(0)[:30]
    if FIGURE_FIRST.search(p):
        sig["figure_first_opening"] = sents[0][:30] if sents else ""
    far = 0
    if u.role == "results":
        for i, s in enumerate(sents):
            if CLAIM.search(s):
                window = " ".join(sents[max(0, i - 1): i + 2])
                if not EVIDENCE.search(window):
                    far += 1
        if far:
            sig["claim_far_from_evidence"] = f"{far} 句"
    detail = {"n_sent": n, "lens": lens, "cv": cv, "n_conn": n_conn, "n_tmpl": len(tmpl),
              "openings": ops, "result_first": bool(sents) and bool(CLAIM.search(sents[0]) or EVIDENCE.search(sents[0]))}
    return sig, detail


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path)
    ap.add_argument("--tex", type=Path, help="不用配置时：sections 目录或单个 .tex")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--review-at", type=int, default=0, help="高优先级热区（≥3 信号）达到该数即退出 4；0 = 从不")
    ap.add_argument("--min-chars", type=int, default=40)
    ap.add_argument("--json", type=Path, help="把指标与热区写成 JSON（可作下次 --baseline）")
    ap.add_argument("--baseline", type=Path, help="上一次 --json 的输出；打印指标 delta")
    args = ap.parse_args()

    cfg = None
    if args.config:
        if not args.config.is_file():
            print(f"ERROR: 配置不存在: {args.config}", file=sys.stderr); return 2
        cfg = ls.load_config(args.config)
        units = cfg.units()
        raw_cfg = cfg.raw
        ex = ls.load_exemptions(cfg.exemptions).get("style_audit", [])
    elif args.tex:
        files = sorted(args.tex.rglob("*.tex")) if args.tex.is_dir() else [args.tex]
        units = [u for f in files for u in ls.split_units(f, ls.guess_role(f))]
        raw_cfg, ex = {}, []
    else:
        print("ERROR: 需要 --config 或 --tex", file=sys.stderr); return 2

    protected = set(raw_cfg.get("protected_units") or [])
    paras = [u for u in units if len(u.prose) >= args.min_chars and not u.raw.lstrip().startswith(("\\section", "\\subsection", "\\subsubsection"))]
    if not paras:
        print("ERROR: 没有可诊断的段落", file=sys.stderr); return 2
    lang = "zh" if sum(1 for u in paras if lang_of(u.prose) == "zh") >= len(paras) / 2 else "en"

    hot = []          # (severity, unit, sig)
    all_lens: list[int] = []
    n_conn = n_sent = n_tmpl = 0
    openings: Counter = Counter()
    fig_first = 0
    res_total = res_first = 0
    chain_paras = 0
    para_lens_by_file: dict[str, list[int]] = {}
    for u in paras:
        sig, d = audit_paragraph(u, lang)
        all_lens += d["lens"]; n_sent += d["n_sent"]; n_conn += d["n_conn"]; n_tmpl += d["n_tmpl"]
        openings.update(d["openings"])
        fig_first += 1 if "figure_first_opening" in sig else 0
        chain_paras += 1 if "noun_chain" in sig else 0
        if u.role == "results" and d["n_sent"] >= 2:
            res_total += 1; res_first += 1 if d["result_first"] else 0
        para_lens_by_file.setdefault(u.file, []).append(len(u.prose))
        if sig:
            stem = u.unit_id.split("@")[0]
            is_prot = stem in protected or u.unit_id in protected
            e = ls.exempted(u.prose, ex)
            hot.append((len(sig), u, sig, is_prot, e))

    # ---- 文档级：孤儿缩写 / 术语首用 / 项目方言 / 段长整齐度 ----
    prose_all = "\n".join(u.prose for u in units)
    prose_body = "\n".join(u.prose for u in units if u.role not in ("abstract",))
    known = set(raw_cfg.get("defined_acronyms") or []) | set(raw_cfg.get("method_names") or []) | \
        set(raw_cfg.get("external_baselines") or []) | set(raw_cfg.get("internal_baselines") or [])
    acros = Counter(m.group(1) for m in ACRO.finditer(prose_all))
    orphan = []
    for a, c in acros.items():
        if a in ACRO_WHITELIST or a in known or re.fullmatch(r"[IVX]+", a):
            continue
        defined = re.search(r"[（(][^（）()]*" + re.escape(a) + r"[）)]", prose_all) or re.search(re.escape(a) + r"\s*[（(]", prose_all)
        if not defined and c >= 2:
            orphan.append(f"{a}({c})")
    term_no_cue = []
    if cfg and cfg.glossary and cfg.glossary.is_file():
        try:
            import term_variants as tv  # noqa: WPS433
            for r in tv.parse_glossary(cfg.glossary.read_text(encoding="utf-8", errors="replace")):
                term = r["term"].strip("`* ")
                if not term or len(term) < 2 or not re.search(r"[一-鿿]", term):
                    continue
                first = next((u for u in units if u.role != "abstract" and term in u.prose), None)
                if first is not None and not DEF_CUE.search(first.prose) and r["foreign"].strip() not in first.prose:
                    term_no_cue.append(f"{term}@{first.unit_id.split('@')[0]}")
        except Exception as exc:  # 术语表解析失败不影响诊断
            term_no_cue.append(f"(术语表解析失败：{exc})")
    dialect = None
    bt = raw_cfg.get("banned_terms")
    if bt:
        btp = Path(bt) if Path(bt).is_absolute() else (cfg.root / bt if cfg else Path(bt))
        if btp.is_file():
            pats = [ln.strip() for ln in btp.read_text(encoding="utf-8", errors="replace").splitlines()
                    if ln.strip() and not ln.startswith("#")]
            dialect = 0
            for pat in pats:
                try:
                    dialect += len(re.findall(pat, prose_all))
                except re.error:
                    dialect += prose_all.count(pat)
    uniform_files = []
    for f, L in para_lens_by_file.items():
        if len(L) >= 4:
            cvf = statistics.pstdev(L) / statistics.mean(L)
            if cvf < 0.25:
                uniform_files.append(f"{f}(CV={cvf:.2f})")

    metrics = {
        "paragraphs": len(paras),
        "sentences": n_sent,
        "sent_len_mean": round(statistics.mean(all_lens), 1) if all_lens else 0,
        "sent_len_cv": round(statistics.pstdev(all_lens) / statistics.mean(all_lens), 3) if len(all_lens) > 1 and statistics.mean(all_lens) else 0,
        "connector_ratio": round(n_conn / n_sent, 3) if n_sent else 0,
        "template_per_1k": round(1000 * n_tmpl / max(1, len(prose_all)), 2),
        "figure_first_opening_count": fig_first,
        "result_first_ratio": round(res_first / res_total, 2) if res_total else None,
        "noun_chain_paragraphs": chain_paras,
        "orphan_acronym_count": len(orphan),
        "term_first_use_no_cue": len(term_no_cue),
        "project_dialect_count": dialect,
        "uniform_paragraph_files": len(uniform_files),
        "hotspots": len(hot),
        "hotspots_high": sum(1 for h in hot if h[0] >= 3 and not h[3] and not h[4]),
    }
    hot.sort(key=lambda h: (-h[0], h[1].file, h[1].ordinal))

    # ---- 输出 ----
    print("METRICS")
    for k, v in metrics.items():
        print(f"  {k:<28} {v}")
    top_open = [f"「{o}」×{c}" for o, c in openings.most_common(5) if c >= 4]
    if top_open:
        print("  全文重复起句 top:", "、".join(top_open))
    if orphan:
        print("  孤儿缩写（未在括号内定义）:", "、".join(sorted(orphan)))
    if term_no_cue:
        print("  术语首用无定义线索:", "、".join(term_no_cue[:12]))
    if uniform_files:
        print("  段长过于整齐的文件:", "、".join(uniform_files))
    if args.baseline and args.baseline.is_file():
        base = json.loads(args.baseline.read_text(encoding="utf-8")).get("metrics", {})
        print("DELTA vs baseline")
        for k, v in metrics.items():
            b = base.get(k)
            if isinstance(v, (int, float)) and isinstance(b, (int, float)) and v != b:
                print(f"  {k:<28} {b} → {v} ({v - b:+.3g})")
    print(f"HOTSPOTS（top {args.top}，severity = 信号数；≥3 为高优先级）")
    for sev, u, sig, prot, e in hot[:args.top]:
        tag = "  [保护段，不改]" if prot else (f"  [豁免：{e['reason']}]" if e else "")
        print(f"  [{sev}] {u.unit_id} [{u.role}]{tag}")
        for k, v in sig.items():
            print(f"        {k}: {v}")
        print(f"        » {u.prose[:48]}")

    verdict, code = "PASS", 0
    if args.review_at and metrics["hotspots_high"] >= args.review_at:
        verdict, code = "REVIEW_REQUIRED", 4
    if args.json:
        args.json.write_text(json.dumps({"metrics": metrics,
                                         "hotspots": [{"unit_id": u.unit_id, "role": u.role, "severity": s, "signals": sig, "protected": p}
                                                      for s, u, sig, p, _ in hot]}, ensure_ascii=False, indent=1), encoding="utf-8")
    ls.print_proof("style_audit", verdict,
                   [f"段落 {metrics['paragraphs']}；热区 {metrics['hotspots']}（高优先级 {metrics['hotspots_high']}）；"
                    f"模板句/千字 {metrics['template_per_1k']}；连接词起句比 {metrics['connector_ratio']}；图表空转起句 {metrics['figure_first_opening_count']}",
                    "口径：软诊断，只出热区；不因风格退出 1；高优先级热区不覆盖任何硬门。"], code)
    return code


if __name__ == "__main__":
    sys.exit(main())
