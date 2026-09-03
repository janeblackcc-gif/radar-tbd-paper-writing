#!/usr/bin/env python3
"""semantic_diff.py — 两版散文之间的语义不变量检查（硬 + 待审两级）。

页级字符数 delta 抓不住等长改写；本脚本逐段配对两版，检查：

  必须完全一致（HARD_FAIL）：
    带符号数值、单位、引用键、\\ref/\\label/\\eqref 键、宏名、图表编号、
    「分别/respectively」句里数字的先后顺序
  必须保持方向（REVIEW_REQUIRED；方向词典是启发式，不自动判死）：
    高于/低于、优于/劣于、区间包含零/不包含零、至少/至多、已知/未知、
    支持/未显示、平均/逐场景、内部对照/外部基线
  其他待审：否定词计数变化、范围限定词（仅/只/全部/所有/均）增减、
    段落无法配对（大改）、数字被换成宏（合法但要人确认）

三种输入：
    --config paper.gates.json --old-rev HEAD          工作区 vs 某个 git 版本
    --old <dir|file> --new <dir|file>                 两个目录/文件
    --pairs pairs.json  [--mode ze]                    显式段落对（中→英翻译轮）
      pairs.json: [{"id":"05#12","old":"中文段","new":"English paragraph"}, ...]

--mode zz（默认，同语言）| ze（中→英：缩写差异只记待审，否定词计数不比）
退出码: 0 = PASS, 1 = HARD_FAIL, 4 = REVIEW_REQUIRED, 2 = 用法/环境错误
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latex_scope as ls  # noqa: E402

NUM = re.compile(r"(?<![A-Za-z0-9_\\:{])[-−+]?\d+(?:\.\d+)?(?![A-Za-z0-9_:}])")
UNIT = re.compile(r"(?<=\d)\s*(?:~|\\,)?\s*(dB|km/s|m/s|rad/s|km|m|s|ms|%|rad|Hz|GiB|MB)\b")
CITE = re.compile(r"\\cite[a-z]*\*?\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")
REFK = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref|label|pageref)\*?\s*\{([^}]*)\}")
MACRO = re.compile(r"\\([A-Z][A-Za-z]{3,})\b")
#: 不是数据宏的大写开头 LaTeX 命令：希腊字母、algorithmic 关键字、排版命令
NOT_DATA_MACRO = {"Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta", "Iota", "Kappa", "Lambda",
                  "Omega", "Sigma", "Upsilon", "Phi", "Chi", "Psi", "Xi", "Pi", "Rho", "Tau", "Nu", "Mu",
                  "Require", "Ensure", "State", "EndFor", "EndIf", "EndWhile", "Else", "ElsIf", "Return", "Call",
                  "Comment", "Function", "EndFunction", "Procedure", "EndProcedure", "Repeat", "Until",
                  "FloatBarrier", "Big", "Bigg", "Bigl", "Bigr", "Biggl", "Biggr", "Large", "LARGE", "Huge",
                  "Cref", "Cite", "Pr", "Re", "Im", "Vert", "Box", "Diamond"}
FIGNO = re.compile(r"(?:图|表|Fig\.?|Figure|Table)\s*~?\s*(\d+)")
ACRO = re.compile(r"(?<![A-Za-z])([A-Z][A-Z0-9]{1,}(?:[-+][A-Z0-9]+)*)(?![a-z])")
ORDER_CUE = re.compile(r"分别|依次|respectively", re.I)

CONCEPTS: dict[str, dict[str, list[str]]] = {
    "gt": {"zh": ["高于", "优于", "大于", "超过", "增至", "上升", "提高", "增加", "增大", "升高", "改善"],
           "en": ["higher", "greater", "exceed", "above", "outperform", "better", "increase", "improve", "rise", "gain"]},
    "lt": {"zh": ["低于", "劣于", "小于", "不及", "降至", "下降", "降低", "减少", "减小", "缩短"],
           "en": ["lower", "smaller", "below", "worse", "inferior", "decrease", "reduce", "reduction", "drop", "decline", "fall"]},
    "ci_excl0": {"zh": ["不包含零", "完全高于零", "完全低于零", "不覆盖零", "不跨越零"], "en": ["excludes zero", "entirely above zero", "entirely below zero", "does not include zero", "does not cover zero"]},
    "ci_incl0": {"zh": ["包含零", "覆盖零", "跨越零"], "en": ["includes zero", "contains zero", "covers zero", "crosses zero", "overlaps zero"]},
    "atleast": {"zh": ["至少", "不低于", "不少于"], "en": ["at least", "no less than", "not below", "no fewer than"]},
    "atmost": {"zh": ["至多", "不高于", "不超过", "不多于"], "en": ["at most", "no more than", "not exceed", "no greater than"]},
    "known": {"zh": ["已知"], "en": ["known"]},
    "unknown": {"zh": ["未知"], "en": ["unknown"]},
    "supports": {"zh": ["支持", "表明", "证实"], "en": ["support", "indicate", "confirm", "demonstrate"]},
    "notshown": {"zh": ["未显示", "不能区分", "无法判定", "尚不能判定", "不足以", "未能"], "en": ["does not show", "cannot distinguish", "cannot be determined", "insufficient to", "fails to"]},
    "avg": {"zh": ["平均"], "en": ["average", "mean"]},
    "perscene": {"zh": ["逐场景", "每个场景", "每次仿真", "逐次"], "en": ["per-scene", "per scene", "every run", "each scenario", "per run"]},
    "external": {"zh": ["外部基线", "外部参照", "外部方法"], "en": ["external baseline", "external reference"]},
    "internal": {"zh": ["内部对照", "内部基线"], "en": ["internal comparison", "internal baseline"]},
}
OPPOSITE = {"gt": "lt", "lt": "gt", "ci_excl0": "ci_incl0", "ci_incl0": "ci_excl0", "atleast": "atmost", "atmost": "atleast",
            "known": "unknown", "unknown": "known", "supports": "notshown", "notshown": "supports",
            "avg": "perscene", "perscene": "avg", "external": "internal", "internal": "external"}
SCOPE = {
    "only": {"zh": ["仅", "只", "唯一"], "en": ["only", "solely", "unique"]},
    "all": {"zh": ["全部", "所有", "均", "任意", "每个", "每次"], "en": ["all", "every", "each", "any"]},
}
#: 单字形式必须带上下文：「均」不能命中「平均」
ZH_SPECIAL = {"均": re.compile(r"(?<!平)均"), "只": re.compile(r"只(?!是|有|要|能|好)"), "仅": re.compile(r"仅(?!仅)")}
NEG_ZH = re.compile(r"不(?!同|仅|但|论|管|妨|少)|未(?!来|知)|无法|没有|并非|尚未")
NEG_EN = re.compile(r"\b(?:not|no|never|cannot|without|neither|nor)\b", re.I)


def lang_of(text: str) -> str:
    return "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en"


def concept_set(text: str, table: dict, lang: str) -> set[str]:
    out = set()
    low = text.lower()
    for cid, forms in table.items():
        for f in forms[lang]:
            if lang == "zh":
                # 「不包含零」含「包含零」：先排除带否定前缀的命中
                if cid == "ci_incl0" and re.search(r"不" + re.escape(f), text):
                    if not re.search(r"(?<!不)" + re.escape(f), text):
                        continue
                hit = ZH_SPECIAL[f].search(text) if f in ZH_SPECIAL else (f in text)
                if hit:
                    out.add(cid); break
            else:
                if re.search(r"\b" + re.escape(f), low):
                    out.add(cid); break
    return out


def facts(raw: str) -> dict[str, Counter]:
    t = ls.strip_comments(raw)
    return {
        "num": Counter(m.group(0).replace("−", "-") for m in NUM.finditer(t)),
        "unit": Counter(m.group(1) for m in UNIT.finditer(t)),
        "cite": Counter(k.strip() for m in CITE.finditer(t) for k in m.group(1).split(",")),
        "ref": Counter(m.group(1).strip() for m in REFK.finditer(t)),
        "macro": Counter(m.group(1) for m in MACRO.finditer(t) if m.group(1) not in NOT_DATA_MACRO),
        "figno": Counter(m.group(1) for m in FIGNO.finditer(t)),
        "acro": Counter(m.group(1) for m in ACRO.finditer(re.sub(r"\\[A-Za-z]+", " ", t))),
    }


def order_seqs(raw: str) -> list[list[str]]:
    out = []
    for s in re.split(r"(?<=[。；.;])", ls.strip_comments(raw)):
        if ORDER_CUE.search(s):
            nums = [m.group(0) for m in NUM.finditer(s)]
            if len(nums) >= 2:
                out.append(nums)
    return out


def compare(old_raw: str, new_raw: str, mode: str,
            file_old: dict[str, Counter] | None = None,
            file_new: dict[str, Counter] | None = None) -> tuple[list[str], list[str]]:
    """file_old/file_new：同一文件整体的事实多重集。段落拆并会让某个数字/引用从这一段
    「消失」却仍在同文件别的段里——这种只记待审（移动），文件级也丢了才是硬失败。"""
    hard, review = [], []
    fo, fn = facts(old_raw), facts(new_raw)
    lo, ln = lang_of(old_raw), lang_of(new_raw)

    def still_in_file(key: str, item: str, direction: str) -> bool:
        if file_old is None or file_new is None:
            return False
        if direction == "lost":   # 旧段有、新段无：新文件里还有同样多吗
            return file_new[key][item] >= file_old[key][item]
        return file_old[key][item] >= file_new[key][item]   # 新段多出来：旧文件里本来就有

    for key, label in (("num", "数值"), ("unit", "单位"), ("cite", "引用键"), ("ref", "ref/label 键"), ("macro", "宏名"), ("figno", "图表编号")):
        lost, gained = fo[key] - fn[key], fn[key] - fo[key]
        if not lost and not gained:
            continue
        moved_l = {k: v for k, v in lost.items() if still_in_file(key, k, "lost")}
        moved_g = {k: v for k, v in gained.items() if still_in_file(key, k, "gained")}
        real_l = {k: v for k, v in lost.items() if k not in moved_l}
        real_g = {k: v for k, v in gained.items() if k not in moved_g}
        if moved_l or moved_g:
            review.append(f"{label}在同文件段落间移动：-{moved_l or '{}'} +{moved_g or '{}'}")
        if not real_l and not real_g:
            continue
        msg = f"{label}变化：-{real_l or '{}'} +{real_g or '{}'}"
        if key == "num" and real_l and (fn["macro"] - fo["macro"]):
            review.append(msg + "（数字被换成宏？确认宏值等于原数）")
        elif key == "figno" and mode == "ze":
            review.append(msg)
        else:
            hard.append(msg)
    lost_a, gained_a = fo["acro"] - fn["acro"], fn["acro"] - fo["acro"]
    lost_a = Counter({k: v for k, v in lost_a.items() if not still_in_file("acro", k, "lost")})
    gained_a = Counter({k: v for k, v in gained_a.items() if not still_in_file("acro", k, "gained")})
    if lost_a or gained_a:
        (review if mode == "ze" else hard).append(f"缩写/方法名变化：-{dict(lost_a) or '{}'} +{dict(gained_a) or '{}'}")
    # 顺序敏感序列
    so, sn = order_seqs(old_raw), order_seqs(new_raw)
    if so and sn and mode == "zz":
        for seq in so:
            if seq not in sn and sorted(seq) in [sorted(x) for x in sn]:
                hard.append(f"「分别」序列顺序改变：{seq}")
    # 方向概念
    co, cn = concept_set(ls.mask_non_prose(old_raw), CONCEPTS, lo), concept_set(ls.mask_non_prose(new_raw), CONCEPTS, ln)
    for cid in co - cn:
        if OPPOSITE.get(cid) in cn:
            review.append(f"方向翻转：{cid} → {OPPOSITE[cid]}")
        else:
            review.append(f"方向词消失：{cid}")
    for cid in cn - co:
        if OPPOSITE.get(cid) not in co:
            review.append(f"新增方向词：{cid}")
    # 范围限定
    qo, qn = concept_set(ls.mask_non_prose(old_raw), SCOPE, lo), concept_set(ls.mask_non_prose(new_raw), SCOPE, ln)
    if qo != qn:
        review.append(f"范围限定词变化：{sorted(qo)} → {sorted(qn)}")
    # 否定计数（同语言）
    if mode == "zz" and lo == ln:
        rx = NEG_ZH if lo == "zh" else NEG_EN
        a, b = len(rx.findall(ls.mask_non_prose(old_raw))), len(rx.findall(ls.mask_non_prose(new_raw)))
        if a != b:
            review.append(f"否定词数量 {a} → {b}")
    return hard, review


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path)
    ap.add_argument("--old-rev", help="与 --config 连用：旧版 git 版本号")
    ap.add_argument("--new-rev", help="与 --old-rev 连用：新版也取 git 版本（默认工作区）；用于回放历史")
    ap.add_argument("--old", type=Path); ap.add_argument("--new", type=Path)
    ap.add_argument("--pairs", type=Path)
    ap.add_argument("--mode", choices=["zz", "ze"], default="zz")
    ap.add_argument("--threshold", type=float, default=0.45, help="段落配对相似度阈值")
    ap.add_argument("--quiet-pass", action="store_true")
    args = ap.parse_args()

    pairs: list[tuple[str, str, str, str]] = []   # (id, file, old_raw, new_raw)
    added: list[str] = []; removed: list[str] = []
    file_facts_old: dict[str, dict[str, Counter]] = {}
    file_facts_new: dict[str, dict[str, Counter]] = {}

    def file_level(units: list[ls.Unit]) -> dict[str, dict[str, Counter]]:
        out: dict[str, dict[str, Counter]] = {}
        for u in units:
            f = facts(u.raw)
            acc = out.setdefault(u.file, {k: Counter() for k in f})
            for k, c in f.items():
                acc[k].update(c)
        return out

    def from_units(old_units: list[ls.Unit], new_units: list[ls.Unit]):
        nonlocal pairs, added, removed, file_facts_old, file_facts_new
        ps, ad, rm = ls.pair_units(old_units, new_units, args.threshold)
        pairs = [(f"{o.unit_id} → {n.unit_id}", n.file, o.raw, n.raw) for o, n, _ in ps if ls._norm_ws(o.raw) != ls._norm_ws(n.raw)]
        added = [f"{u.unit_id}: {u.prose[:50]}" for u in ad]
        removed = [f"{u.unit_id}: {u.prose[:50]}" for u in rm]
        file_facts_old, file_facts_new = file_level(old_units), file_level(new_units)

    if args.pairs:
        if not args.pairs.is_file():
            print(f"ERROR: {args.pairs} 不存在", file=sys.stderr); return 2
        for it in json.loads(args.pairs.read_text(encoding="utf-8")):
            pairs.append((str(it.get("id", len(pairs))), "", it["old"], it["new"]))
    elif args.config and args.old_rev:
        cfg = ls.load_config(args.config)
        old_units = ls.units_from_git(cfg.section_files(), args.old_rev, cfg.roles)
        if old_units is None:
            print("ERROR: sections 不在 git 仓库内", file=sys.stderr); return 2
        if args.new_rev:
            new_units = ls.units_from_git(cfg.section_files(), args.new_rev, cfg.roles)
            if new_units is None:
                print("ERROR: --new-rev 取不到", file=sys.stderr); return 2
        else:
            new_units = cfg.units()
        from_units(old_units, new_units)
    elif args.old and args.new:
        def load(p: Path) -> list[ls.Unit]:
            files = sorted(p.rglob("*.tex")) if p.is_dir() else [p]
            out = []
            for f in files:
                out.extend(ls.split_units(f, ls.guess_role(f)))
            return out
        from_units(load(args.old), load(args.new))
    else:
        print("ERROR: 需要 --pairs，或 --config + --old-rev，或 --old + --new", file=sys.stderr); return 2

    n_hard = n_review = n_pass = 0
    for pid, fname, o, n in pairs:
        hard, review = compare(o, n, args.mode, file_facts_old.get(fname), file_facts_new.get(fname))
        if hard:
            n_hard += 1; tag = "HARD_FAIL"
        elif review:
            n_review += 1; tag = "REVIEW"
        else:
            n_pass += 1; tag = "PASS"
            if args.quiet_pass:
                continue
        print(f"[{tag}] {pid}")
        for h in hard:
            print(f"    ✗ {h}")
        for r in review:
            print(f"    ? {r}")
    for a in added:
        print(f"[REVIEW] 新增段落（无法与旧版配对）{a}")
    for r in removed:
        print(f"[REVIEW] 删除段落（无法与新版配对）{r}")
    n_review += len(added) + len(removed)

    verdict = "HARD_FAIL" if n_hard else ("REVIEW_REQUIRED" if n_review else "PASS")
    code = 1 if n_hard else (4 if n_review else 0)
    ls.print_proof("semantic_diff", verdict,
                   [f"模式：{args.mode}；改动段落：{len(pairs)}；硬失败 {n_hard}；待审 {n_review}（含新增/删除段 {len(added)}/{len(removed)}）；通过 {n_pass}",
                    "口径：数值/单位/引用/宏/图表号必须一致；方向词、范围限定、否定计数只提示。"],
                   code)
    return code


if __name__ == "__main__":
    sys.exit(main())
