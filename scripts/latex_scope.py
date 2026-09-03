#!/usr/bin/env python3
"""latex_scope.py — 门禁脚本共用的 LaTeX 作用域库（不单独作为门禁运行）。

职责：
  1. 把 sections 目录切成**稳定编号的段落单元**（unit）：
     unit_id = <文件名去扩展名>#<段落序号>@<内容哈希前 8 位>
     序号让人能在文件里定位，哈希让改动可被识别（改了内容 id 就变）。
  2. 遮罩不属于「散文」的区域：数学、\\cite/\\ref/\\eqref/\\label、\\input、
     \\includegraphics、algorithmic/equation/figure/table 等环境、生成宏名。
     遮罩后的文本用于防御句普查、术语扫描、风格诊断——这些门禁只该看读者
     会当作句子来读的部分。
  3. 识别每个文件的**章节角色**（abstract / introduction / … / conclusion），
     供「摘要必须提基线」「结论必须有适用范围句」这类位置规则使用。
  4. 读项目配置 paper.gates.json；调用 pdftotext / pdfinfo（**Windows 下必须
     `-enc UTF-8`，否则 CJK 全部丢失**——2026-09-02 实测两篇稿子在默认编码下
     抽出 0 个汉字）。

不依赖第三方包。被 run_gates.py / claim_ledger.py / hedge_budget.py /
term_variants.py / style_audit.py / semantic_diff.py / change_ledger.py 导入。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ----------------------------------------------------------------------------
# 章节角色
# ----------------------------------------------------------------------------

#: 文件名关键字 → 角色。项目配置里的 "roles" 可覆盖这张表。
DEFAULT_ROLE_HINTS: dict[str, str] = {
    "abstract": "abstract",
    "intro": "introduction",
    "related": "related_work",
    "problem": "model",
    "formulation": "model",
    "model": "model",
    "method": "method",
    "result": "results",
    "experiment": "results",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "declaration": "declarations",
}

ROLE_ORDER = ["abstract", "introduction", "related_work", "model", "method",
              "results", "discussion", "conclusion", "declarations", "other"]


def guess_role(path: Path, overrides: dict[str, str] | None = None) -> str:
    """按文件名猜章节角色。overrides: {文件名或文件名片段: 角色}。"""
    name = path.name.lower()
    if overrides:
        for key, role in overrides.items():
            if key.lower() in name:
                return role
    for key, role in DEFAULT_ROLE_HINTS.items():
        if key in name:
            return role
    return "other"


# ----------------------------------------------------------------------------
# 遮罩
# ----------------------------------------------------------------------------

#: 整体抹掉（内容替换为占位符）的环境。
NON_PROSE_ENVS = (
    "equation", "equation*", "align", "align*", "gather", "gather*",
    "multline", "multline*", "eqnarray", "eqnarray*", "displaymath",
    "algorithmic", "algorithm", "lstlisting", "verbatim", "tabular", "tabularx",
    "tikzpicture",
)

#: 浮动体外壳：其内部 \\caption{...} 是散文，保留；其余抹掉。
FLOAT_ENVS = ("figure", "figure*", "table", "table*")

_MATH_PLACEHOLDER = "〈式〉"
_REF_PLACEHOLDER = "〈引〉"
_MACRO_PLACEHOLDER = "〈宏〉"


def strip_comments(text: str) -> str:
    """逐行截断未转义 % 之后的内容，保持行号不变（与 jargon_scan 同实现）。"""
    out = []
    for line in text.split("\n"):
        i, n, cut = 0, len(line), None
        while i < n:
            c = line[i]
            if c == "\\":
                i += 2
                continue
            if c == "%":
                cut = i
                break
            i += 1
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def _blank_keep_lines(s: str) -> str:
    return "\n" * s.count("\n")


def _env_regex(env: str) -> re.Pattern[str]:
    e = re.escape(env.rstrip("*"))
    return re.compile(r"\\begin\{" + e + r"\*?\}.*?\\end\{" + e + r"\*?\}", re.S)


def extract_captions(text: str) -> list[str]:
    """取出所有 \\caption{...}（支持一层嵌套花括号）。"""
    caps = []
    for m in re.finditer(r"\\caption\s*(\[[^\]]*\])?\s*\{", text):
        i = m.end()
        depth = 1
        j = i
        while j < len(text) and depth:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        caps.append(text[i:j - 1])
    return caps


def mask_non_prose(text: str, keep_captions: bool = True) -> str:
    """把公式、引用命令、非散文环境替换成占位符；保留行数。

    keep_captions=True 时，浮动体被抹掉但其 caption 文本以独立段落形式保留在
    原位置（图注是读者可见散文，防御句预算与术语扫描都要覆盖它）。
    """
    text = strip_comments(text)

    # 1) 浮动体：保留 caption
    for env in FLOAT_ENVS:
        rx = _env_regex(env)

        def _float_sub(m: re.Match[str]) -> str:
            body = m.group(0)
            caps = extract_captions(body) if keep_captions else []
            nl = body.count("\n")
            if caps:
                joined = "\n\n".join(caps)
                pad = max(0, nl - joined.count("\n"))
                return "\n" + joined + "\n" * pad
            return _blank_keep_lines(body)

        text = rx.sub(_float_sub, text)

    # 2) 非散文环境整体抹掉
    for env in NON_PROSE_ENVS:
        if env.endswith("*"):
            continue  # 已由不带 * 的正则覆盖
        text = _env_regex(env).sub(lambda m: _blank_keep_lines(m.group(0)), text)

    # 3) 行内/行间数学
    text = re.sub(r"\$\$.*?\$\$", _MATH_PLACEHOLDER, text, flags=re.S)
    text = re.sub(r"\\\[.*?\\\]", _MATH_PLACEHOLDER, text, flags=re.S)
    text = re.sub(r"\\\(.*?\\\)", _MATH_PLACEHOLDER, text, flags=re.S)
    text = re.sub(r"(?<!\\)\$[^$]*?\$", _MATH_PLACEHOLDER, text, flags=re.S)

    # 4) 引用/交叉引用/输入/图片
    text = re.sub(r"\\(?:cite[a-z]*|ref|eqref|autoref|cref|Cref|label|pageref)\*?\s*(\[[^\]]*\])?\s*\{[^}]*\}",
                  _REF_PLACEHOLDER, text)
    text = re.sub(r"\\(?:input|include|includegraphics|bibliography|printbibliography)\*?\s*(\[[^\]]*\])?\s*(\{[^}]*\})?",
                  "", text)

    # 5) 章节命令：保留标题文字（标题也是散文），去掉命令壳
    text = re.sub(r"\\(?:section|subsection|subsubsection|paragraph|chapter)\*?\s*(\[[^\]]*\])?\s*\{([^}]*)\}",
                  r"\2", text)

    # 6) 常见格式命令：\textbf{x} → x；\noindent 等删掉
    for _ in range(3):
        text = re.sub(r"\\(?:textbf|textit|emph|texttt|textsc|underline|mbox|text)\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:noindent|centering|small|footnotesize|par|clearpage|FloatBarrier|newpage|linebreak|newline|hfill|vspace\*?\{[^}]*\}|hspace\*?\{[^}]*\})",
                  "", text)

    # 7) 环境壳与列表标记不是散文也不是宏：直接删
    text = re.sub(r"\\(?:begin|end)\s*\{[^}]*\}(\[[^\]]*\])?", "", text)
    text = re.sub(r"\\item\b(\[[^\]]*\])?", "", text)

    # 8) 剩余宏（含项目生成宏 \ConfirmPrimaryMean 等）→ 占位符；反斜杠符号清理
    text = re.sub(r"\\[A-Za-z@]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", _MACRO_PLACEHOLDER, text)
    text = text.replace("~", " ").replace("\\\\", " ")
    text = re.sub(r"\\([%&_#$])", r"\1", text)
    text = re.sub(r"[{}]", "", text)
    return text


# ----------------------------------------------------------------------------
# 段落单元
# ----------------------------------------------------------------------------

@dataclass
class Unit:
    unit_id: str
    file: str
    role: str
    ordinal: int
    line_start: int
    line_end: int
    raw: str            # 原始 LaTeX 段落
    prose: str          # 遮罩后的散文
    kind: str = "paragraph"  # paragraph | caption | heading

    def sentences(self) -> list[str]:
        return split_sentences(self.prose)


_SENT_SPLIT = re.compile(r"(?<=[。！？；])\s*|(?<=[.!?])\s+(?=[A-Z\u4e00-\u9fff])")


def split_sentences(prose: str) -> list[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(prose) if p and p.strip()]
    return [p for p in parts if len(p) >= 2]


def content_hash(s: str) -> str:
    norm = re.sub(r"\s+", " ", s.strip())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:8]


def split_units(path: Path, role: str) -> list[Unit]:
    """把一个 .tex 文件切成段落单元。段落以空行分隔；浮动体的 caption 作为
    kind=caption 的独立单元；\\section 行作为 kind=heading。"""
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    no_comment = strip_comments(raw_text)
    lines = no_comment.split("\n")

    # 先把浮动体/非散文环境的行范围标出来，避免其内部空行被当成段落边界
    protected: list[tuple[int, int, str]] = []  # (start_line, end_line, env)
    for env in FLOAT_ENVS + NON_PROSE_ENVS:
        if env.endswith("*"):
            continue
        for m in _env_regex(env).finditer(no_comment):
            s = no_comment.count("\n", 0, m.start())
            e = no_comment.count("\n", 0, m.end())
            protected.append((s, e, env))
    protected.sort()

    def in_protected(i: int) -> tuple[int, int, str] | None:
        for s, e, env in protected:
            if s <= i <= e:
                return (s, e, env)
        return None

    units: list[Unit] = []
    ordinal = 0
    i = 0
    n = len(lines)
    stem = path.stem

    def push(kind: str, s: int, e: int, block_lines: list[str]) -> None:
        nonlocal ordinal
        raw = "\n".join(block_lines)
        if not raw.strip():
            return
        if kind == "caption":
            caps = extract_captions(raw)
            if not caps:
                return
            for c in caps:
                ordinal += 1
                prose = mask_non_prose(c, keep_captions=False).strip()
                if not prose:
                    continue
                units.append(Unit(f"{stem}#{ordinal}@{content_hash(c)}", path.name, role,
                                  ordinal, s + 1, e + 1, c, prose, "caption"))
            return
        prose = mask_non_prose(raw, keep_captions=False).strip()
        prose = re.sub(r"[ \t]+", " ", prose)
        prose = re.sub(r"\n{2,}", "\n", prose)
        if not prose or prose in (_MATH_PLACEHOLDER, _REF_PLACEHOLDER, _MACRO_PLACEHOLDER):
            return
        ordinal += 1
        units.append(Unit(f"{stem}#{ordinal}@{content_hash(raw)}", path.name, role,
                          ordinal, s + 1, e + 1, raw, prose, kind))

    while i < n:
        pr = in_protected(i)
        if pr:
            s, e, env = pr
            block = lines[s:e + 1]
            if env in FLOAT_ENVS:
                push("caption", s, e, block)
            i = e + 1
            continue
        if not lines[i].strip():
            i += 1
            continue
        if re.match(r"\s*\\(?:section|subsection|subsubsection)\*?", lines[i]):
            push("heading", i, i, [lines[i]])
            i += 1
            continue
        s = i
        block = []
        while i < n and lines[i].strip() and not in_protected(i) \
                and not re.match(r"\s*\\(?:section|subsection|subsubsection)\*?", lines[i]):
            block.append(lines[i])
            i += 1
        push("paragraph", s, i - 1, block)
    return units


# ----------------------------------------------------------------------------
# 两版之间的段落配对（semantic_diff / change_ledger 共用）
# ----------------------------------------------------------------------------

def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def pair_units(old: list[Unit], new: list[Unit], threshold: float = 0.45):
    """按文件分组，用 difflib 相似度做贪心一对一配对。
    返回 (pairs, added, removed)：pairs = [(old_unit, new_unit, ratio)]。
    段落被改写得面目全非（ratio < threshold）时视为「删 + 增」，由调用方转人工。"""
    import difflib
    pairs, added, removed = [], [], []
    by_file_old: dict[str, list[Unit]] = {}
    by_file_new: dict[str, list[Unit]] = {}
    for u in old:
        by_file_old.setdefault(u.file, []).append(u)
    for u in new:
        by_file_new.setdefault(u.file, []).append(u)
    for f in sorted(set(by_file_old) | set(by_file_new)):
        ol, nl = by_file_old.get(f, []), by_file_new.get(f, [])
        # 1) 内容哈希相同直接配对
        used_o, used_n = set(), set()
        h_old = {}
        for i, u in enumerate(ol):
            h_old.setdefault(content_hash(u.raw), []).append(i)
        for j, v in enumerate(nl):
            cands = h_old.get(content_hash(v.raw), [])
            for i in cands:
                if i not in used_o:
                    pairs.append((ol[i], v, 1.0)); used_o.add(i); used_n.add(j); break
        # 2) 其余按相似度贪心
        scored = []
        for i, u in enumerate(ol):
            if i in used_o:
                continue
            for j, v in enumerate(nl):
                if j in used_n:
                    continue
                r = difflib.SequenceMatcher(None, _norm_ws(u.prose), _norm_ws(v.prose)).ratio()
                if r >= threshold:
                    scored.append((r, i, j))
        for r, i, j in sorted(scored, reverse=True):
            if i in used_o or j in used_n:
                continue
            pairs.append((ol[i], nl[j], r)); used_o.add(i); used_n.add(j)
        removed.extend(u for i, u in enumerate(ol) if i not in used_o)
        added.extend(v for j, v in enumerate(nl) if j not in used_n)
    return pairs, added, removed


def git_root(path: Path) -> Path | None:
    r = subprocess.run(["git", "-C", str(path if path.is_dir() else path.parent), "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        return None
    return Path(r.stdout.strip())


def git_show(root: Path, rev: str, file: Path) -> str | None:
    rel = file.resolve().relative_to(root.resolve()).as_posix()
    r = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{rel}"], capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def units_from_git(files: list[Path], rev: str, roles: dict[str, str] | None = None) -> list[Unit] | None:
    """把 sections 文件在指定 git 版本的内容切成单元；文件在该版本不存在则跳过。
    仓库不存在返回 None。"""
    if not files:
        return []
    root = git_root(files[0])
    if root is None:
        return None
    out: list[Unit] = []
    for f in files:
        txt = git_show(root, rev, f)
        if txt is None:
            continue
        with tempfile.NamedTemporaryFile("w", suffix=f.suffix, delete=False, encoding="utf-8") as tf:
            tf.write(txt)
            tmp = Path(tf.name)
        try:
            us = split_units(tmp, guess_role(f, roles))
            for u in us:
                u.file = f.name
                u.unit_id = f"{f.stem}#{u.ordinal}@{u.unit_id.split('@')[1]}"
            out.extend(us)
        finally:
            tmp.unlink(missing_ok=True)
    return out


# ----------------------------------------------------------------------------
# 项目配置
# ----------------------------------------------------------------------------

@dataclass
class PaperConfig:
    root: Path
    sections: list[Path]
    pdf: Path | None
    main: Path | None
    macros: list[Path]
    outline: Path | None
    glossary: Path | None
    exemptions: Path | None
    ledger: Path | None
    roles: dict[str, str] = field(default_factory=dict)
    glob: str = "*.tex"
    raw: dict = field(default_factory=dict)

    def section_files(self) -> list[Path]:
        files: list[Path] = []
        for p in self.sections:
            if p.is_dir():
                files.extend(sorted(p.rglob(self.glob)))
            elif p.is_file():
                files.append(p)
        return list(dict.fromkeys(files))

    def units(self) -> list[Unit]:
        out: list[Unit] = []
        for f in self.section_files():
            out.extend(split_units(f, guess_role(f, self.roles)))
        return out

    def text_macros(self) -> dict[str, str]:
        """主文件里 \\newcommand{\\method}{STR-FCM-TBD} 这类**文字宏**（不含参数）。
        基线名常被封成宏，扫描原文时要先展开，否则 grep 不到。"""
        out: dict[str, str] = {}
        srcs = [self.main] if self.main and self.main.is_file() else []
        for p in srcs:
            txt = strip_comments(p.read_text(encoding="utf-8", errors="replace"))
            for m in re.finditer(r"\\(?:newcommand|renewcommand|providecommand)\*?\s*\{\\([A-Za-z@]+)\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}", txt):
                body = m.group(2)
                body = re.sub(r"\\xspace", "", body)
                if "#" in body:
                    continue
                out[m.group(1)] = body
        return out

    def expand_text_macros(self, text: str) -> str:
        macros = self.text_macros()
        if not macros:
            return text
        names = sorted(macros, key=len, reverse=True)
        rx = re.compile(r"\\(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z@])\s*(\{\})?")
        return rx.sub(lambda m: macros[m.group(1)], text)


def load_config(path: Path) -> PaperConfig:
    """读 paper.gates.json。相对路径相对于配置文件所在目录。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    root = path.parent

    def _p(v) -> Path | None:
        if not v:
            return None
        q = Path(v)
        return q if q.is_absolute() else (root / q)

    def _plist(v) -> list[Path]:
        if not v:
            return []
        if isinstance(v, str):
            v = [v]
        return [p for p in (_p(x) for x in v) if p is not None]

    return PaperConfig(
        root=root,
        sections=_plist(data.get("sections")),
        pdf=_p(data.get("pdf")),
        main=_p(data.get("main")),
        macros=_plist(data.get("macros")),
        outline=_p(data.get("outline")),
        glossary=_p(data.get("glossary")),
        exemptions=_p(data.get("exemptions")),
        ledger=_p(data.get("ledger")),
        roles=dict(data.get("roles") or {}),
        glob=data.get("glob", "*.tex"),
        raw=data,
    )


def load_exemptions(path: Path | None) -> dict[str, list[dict]]:
    """豁免文件：{"<gate_id>": [{"match": "...", "tag": "...", "reason": "..."}]}。
    match 是子串（不是正则），为的是让作者能把稿件原句直接贴进来。"""
    if not path or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[dict]] = {}
    for gate, items in data.items():
        out[gate] = [it for it in items if isinstance(it, dict) and it.get("match")]
    return out


def exempted(sentence: str, items: list[dict]) -> dict | None:
    for it in items:
        if it["match"] in sentence:
            return it
    return None


# ----------------------------------------------------------------------------
# poppler
# ----------------------------------------------------------------------------

def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        print(f"ERROR: 找不到 {name}，请安装 poppler-utils（Windows 可用 scoop/choco）", file=sys.stderr)
        raise SystemExit(2)


def pdf_to_text(pdf: Path, layout: bool = False) -> str:
    """pdftotext -enc UTF-8（Windows 下不带 -enc 会丢掉全部 CJK）。"""
    require_tool("pdftotext")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
        out = Path(tf.name)
    try:
        cmd = ["pdftotext", "-enc", "UTF-8"] + (["-layout"] if layout else []) + [str(pdf), str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"ERROR: pdftotext 失败 ({pdf}): {r.stderr.strip()}", file=sys.stderr)
            raise SystemExit(2)
        return out.read_text(encoding="utf-8", errors="replace")
    finally:
        out.unlink(missing_ok=True)


def pdf_pages_text(pdf: Path) -> list[str]:
    pages = pdf_to_text(pdf).split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def pdf_page_count(pdf: Path) -> int:
    require_tool("pdfinfo")
    r = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, errors="replace")
    m = re.search(r"Pages:\s+(\d+)", r.stdout)
    if not m:
        print(f"ERROR: pdfinfo 无法读取页数 ({pdf})", file=sys.stderr)
        raise SystemExit(2)
    return int(m.group(1))


# ----------------------------------------------------------------------------
# 输出约定
# ----------------------------------------------------------------------------

def print_proof(gate: str, verdict: str, lines: list[str], exit_code: int) -> None:
    """所有门禁统一的 PROOF 尾块，可直接粘进交付说明。"""
    print("=" * 60)
    print("PROOF")
    print(f"  门禁：{gate}")
    for ln in lines:
        print(f"  {ln}")
    print(f"  判定：{verdict}")
    print(f"  退出码：{exit_code}")
    print("=" * 60)


if __name__ == "__main__":
    # 自检：python latex_scope.py <paper.gates.json>  → 列出单元数与角色分布
    if len(sys.argv) != 2:
        print("用法: python latex_scope.py <paper.gates.json>", file=sys.stderr)
        sys.exit(2)
    cfg = load_config(Path(sys.argv[1]))
    units = cfg.units()
    by_role: dict[str, int] = {}
    for u in units:
        by_role[u.role] = by_role.get(u.role, 0) + 1
    print(f"sections: {[str(p) for p in cfg.sections]}")
    print(f"units: {len(units)}")
    for r in ROLE_ORDER:
        if r in by_role:
            print(f"  {r:<14} {by_role[r]}")
    for u in units[:5]:
        print(f"--- {u.unit_id} [{u.kind}] L{u.line_start}-{u.line_end}")
        print("    " + u.prose[:120].replace("\n", " ⏎ "))
    sys.exit(0)
