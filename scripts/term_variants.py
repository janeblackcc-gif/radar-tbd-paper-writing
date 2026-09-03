#!/usr/bin/env python3
"""term_variants.py — 术语一致性门禁（硬 + 待审两级）。

同一概念只用一个词形（03-diction §六）。三条检查：
  1. 术语表第四列「避免用法」里的形式出现在散文中 → HARD_FAIL（可豁免）
  2. 配置 concept_groups 里声明的非规范形态出现 → HARD_FAIL（enforce=true）或 REVIEW
     例：{"转弯率假设": ["率切片", "率假设", "率条件", "转弯率切片"]}
     这是正名表（03-diction §二）的可执行形式；机器猜不出「切片≈假设≈条件」是同义，人来声明。
  3. 无声明时的后缀词族提示（只作 INFO，不影响判定）：按领域后缀（假设/切片/条件/构型/单元/基线/
     参考/场景/模型/门限…）聚出的高频短词列出来供人判断；定稿上照样会有词族，所以不作待审。

术语表格式：Markdown 四列表，表头含「冻结词」「避免」。第四列里 `反引号`、英文短语、
「不写/不用/不称/不使用 X」后的 X 都视为避免形式；「不与/不把/不暗示/不声称」开头的是说明，不取。
扫描范围：sections 散文（含图注）+ PDF 抽取文本（图内标签在源码里 grep 不到）。

用法:  python term_variants.py --config paper.gates.json [--enforce]
退出码: 0 = PASS, 1 = HARD_FAIL, 4 = REVIEW_REQUIRED, 2 = 用法/环境错误
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latex_scope as ls  # noqa: E402

EN_PHRASE = re.compile(r"[A-Za-z][A-Za-z\-]+(?: [A-Za-z][A-Za-z\-]+){0,3}")
SUFFIXES = ["假设", "切片", "条件", "构型", "单元", "基线", "参考", "场景", "模型", "门限", "候选", "槽位", "编队", "量测", "关联"]
FUNCTION_CHARS = set("的个与和从用在对为按把被将该其此每仅只而及或是有并均各另某于以之所")
FUNCTION_WORDS = {"每个", "一个", "两个", "各个", "这个", "那个", "同一", "任一", "所有", "全部", "某个", "其中"}


def parse_glossary(md: str) -> list[dict]:
    rows, in_table, hdr = [], False, []
    for ln in md.splitlines():
        s = ln.strip()
        if not in_table:
            if s.startswith("|") and "冻结词" in s and "避免" in s:
                in_table = True
                hdr = [c.strip() for c in s.strip("|").split("|")]
            continue
        if not s.startswith("|"):
            in_table = False
            continue
        if re.match(r"^\|?\s*:?-{2,}", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 4:
            continue
        rows.append({"term": cells[0], "foreign": cells[1], "context": cells[2], "avoid": cells[3]})
    return rows


def avoided_forms(cell: str) -> list[str]:
    out = []
    for piece in re.split(r"[；;，,、。]", cell):
        p = piece.strip()
        if not p or re.match(r"^(不与|不把|不暗示|不声称|不直接|不预设|未建模|除非|不当|不再)", p):
            continue
        for m in re.finditer(r"`([^`]+)`", p):
            out.append(m.group(1).strip())
        p2 = re.sub(r"`[^`]+`", " ", p)
        m = re.match(r"^(?:标题)?(?:不写|不用|不称|不叫|不使用|不写成|避免写|避免)\s*([^\s，。；]+(?:\s+[A-Za-z\-]+)*)", p2)
        if m:
            out.append(m.group(1).strip())
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z\- ]{2,40}", p2.strip()):
            out.append(p2.strip())
        else:
            for em in EN_PHRASE.finditer(p2):
                ph = em.group(0).strip()
                if len(ph) >= 5 and ph.lower() not in ("stage", "true", "false"):
                    out.append(ph)
    seen = []
    for f in out:
        f = f.strip(" 。，；")
        if f and f not in seen:
            seen.append(f)
    return seen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--enforce", action="store_true", help="concept_groups 命中记 HARD_FAIL（默认 REVIEW）")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()
    if not args.config.is_file():
        print(f"ERROR: 配置不存在: {args.config}", file=sys.stderr); return 2
    cfg = ls.load_config(args.config)
    ex = ls.load_exemptions(cfg.exemptions).get("term_variants", [])
    units = cfg.units()
    prose_all = "\n".join(u.prose for u in units)
    pdf_text = ""
    if cfg.pdf and cfg.pdf.is_file() and not args.no_pdf:
        pdf_text = ls.pdf_to_text(cfg.pdf)
    hard, review, info = [], [], []

    # 1) 术语表避免用法
    rows = []
    if cfg.glossary and cfg.glossary.is_file():
        rows = parse_glossary(cfg.glossary.read_text(encoding="utf-8", errors="replace"))
        if not rows:
            review.append(f"术语表 {cfg.glossary.name} 里没有找到四列表（表头须含「冻结词」「避免」）")
    else:
        review.append("未配置术语表（glossary）：跳过避免用法检查；词汇轮必须先冻结术语表（03-diction §四）")
    for r in rows:
        for form in avoided_forms(r["avoid"]):
            rx = re.compile(re.escape(form), re.I if re.search(r"[A-Za-z]", form) else 0)
            n_src = len(rx.findall(prose_all))
            n_pdf = len(rx.findall(pdf_text)) if pdf_text else 0
            if n_src or n_pdf:
                e = ls.exempted(form, ex)
                msg = f"「{r['term']}」的避免用法「{form}」：源码 {n_src} 处，PDF {n_pdf} 处"
                (info if e else hard).append(msg + (f"  ⟵ 豁免：{e['reason']}" if e else ""))
        # 冻结词本身的出现次数（信息）
        if r["term"] and len(r["term"]) >= 2:
            info.append(f"冻结词「{r['term']}」出现 {len(re.findall(re.escape(r['term']), prose_all))} 次")

    # 2) concept_groups
    groups: dict[str, list[str]] = cfg.raw.get("concept_groups") or {}
    for canon, variants in groups.items():
        n_c = len(re.findall(re.escape(canon), prose_all))
        for v in variants:
            n_v = len(re.findall(re.escape(v), prose_all))
            n_p = len(re.findall(re.escape(v), pdf_text)) if pdf_text else 0
            # 变体是规范词的子串时（率假设 ⊂ 转弯率假设），扣掉被规范词覆盖的次数
            if v in canon:
                n_v -= n_c
                n_p -= len(re.findall(re.escape(canon), pdf_text)) if pdf_text else 0
            if n_v > 0 or n_p > 0:
                msg = f"概念「{canon}」（{n_c} 次）的非规范形态「{v}」：源码 {max(n_v, 0)} 处，PDF {max(n_p, 0)} 处"
                (hard if args.enforce else review).append(msg)

    # 3) 后缀词族启发式（只作 INFO，不影响判定）
    #    中文无分词：对每个后缀取 1–3 字前缀的最大重复串，并剔除功能字开头的伪前缀（的/个/与/和/从/用…）。
    #    它只能提示同后缀的形态差异（率假设 / 运动假设），发现不了跨后缀同义（切片≈假设）——那要靠 concept_groups。
    #    在定稿上它照样会列出 8 个词族（过门限/低门限 本就是不同概念），所以不能作待审项，只给人看。
    if not groups:
        for suf in SUFFIXES:
            cnt: Counter = Counter()
            for m in re.finditer(r"([一-鿿]{1,3})" + suf, prose_all):
                pre = m.group(1)
                for k in range(1, len(pre) + 1):
                    cnt[pre[-k:] + suf] += 1
            members = []
            for term, c in cnt.items():
                if c < 3 or term[0] in FUNCTION_CHARS or term[:2] in FUNCTION_WORDS:
                    continue
                longer = [t for t in cnt if t != term and t.endswith(term) and cnt[t] >= 3]
                own = c - sum(cnt[t] for t in longer if len(t) == len(term) + 1)
                if own >= 3:
                    members.append((term, own))
            if len(members) >= 2:
                info.append(f"后缀「{suf}」词族：" + "、".join(f"{t}({c})" for t, c in sorted(members, key=lambda x: -x[1])[:6]) + "（若指同一概念，在 concept_groups 声明规范词）")

    verdict = "HARD_FAIL" if hard else ("REVIEW_REQUIRED" if review else "PASS")
    code = 1 if hard else (4 if review else 0)
    if info:
        print("INFO"); [print("  " + x) for x in info]
    lines = [f"术语表行数：{len(rows)}；concept_groups：{len(groups)}；避免用法命中：{len(hard)}；待审：{len(review)}"]
    if hard:
        lines.append("失败项："); lines.extend("  - " + x for x in hard)
    if review:
        lines.append("待审项："); lines.extend("  - " + x for x in review)
    ls.print_proof("term_variants", verdict, lines, code)
    return code


if __name__ == "__main__":
    sys.exit(main())
