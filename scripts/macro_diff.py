#!/usr/bin/env python3
"""macro_diff.py — 论文数字宏的零变化三重校验。

用途：扩展宏生成器之后，证明既有宏一个都没变、只多出了预期的新宏。
这是「先扩生成器再改文字」流程的验收步骤（见 references/06-evidence.md）。

用法:
    python macro_diff.py <old.tex> <new.tex>
    python macro_diff.py <old.tex> <new.tex> --expect-added 36
    git show <rev>^:generated/x.tex > /tmp/old.tex && python macro_diff.py /tmp/old.tex generated/x.tex

输出:
    MISSING: [...]   旧文件有、新文件没有的宏  —— 任何一项都是回归
    CHANGED: [...]   两边都有但值不同的宏      —— 任何一项都是数据漂移
    ADDED:   N       新增的宏（正常扩展）
    VERDICT: PASS / FAIL

退出码: 0 = PASS, 1 = FAIL, 2 = 用法或读取错误
"""

import argparse
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK，会把中文提示打成乱码
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# \newcommand{\Name}{...} / \newcommand*\Name{...} / \renewcommand / \providecommand
# 两种名字写法：带花括号的 {\Name} 与裸写的 \Name
_MACRO_RE = re.compile(
    r"\\(?P<kind>newcommand|renewcommand|providecommand)\*?\s*"
    r"(?:\{\s*\\(?P<n1>[A-Za-z@]+)\s*\}|\\(?P<n2>[A-Za-z@]+))"
    r"\s*(?:\[\d+\])?\s*(?:\[[^\]]*\])?\s*\{",
)

# \def\Name{...} —— 单列，因为它绕过了 newcommand 的重复定义保护
_DEF_RE = re.compile(r"\\def\s*\\(?P<n1>[A-Za-z@]+)\s*\{")


def strip_comments(text: str) -> str:
    """逐行截断未转义 % 之后的内容，保持行数不变。

    被注释掉的宏定义如果参与比较，会让一次真实的数值漂移被判成 PASS。
    """
    out = []
    for line in text.split("\n"):
        i, n = 0, len(line)
        cut = None
        while i < n:
            c = line[i]
            if c == "\\":
                i += 2          # \% 或 \\ —— 整体跳过，转义反斜杠后的 % 仍是注释
                continue
            if c == "%":
                cut = i
                break
            i += 1
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def parse_macros(path: Path):
    """抽取 name -> value，并返回重复定义记录。

    返回 (macros, dup_newcommand)：dup_newcommand 是同名且两次都用 \\newcommand
    定义的名字列表——那在 LaTeX 里本身就是错误，且会静默掩盖值的变化。
    \\newcommand + \\renewcommand 是合法组合，不计入。
    """
    text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
    out = {}
    kinds = {}
    dup = []

    def read_value(start):
        i, depth, buf = start, 1, []
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "\\" and i + 1 < len(text):
                buf.append(text[i : i + 2])
                i += 2
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            buf.append(ch)
            i += 1
        return "".join(buf).strip()

    for m in _MACRO_RE.finditer(text):
        name = m.group("n1") or m.group("n2")
        kind = m.group("kind")
        if name in out and kinds.get(name) == "newcommand" and kind == "newcommand":
            dup.append(name)
        out[name] = read_value(m.end())
        kinds[name] = kind

    for m in _DEF_RE.finditer(text):
        name = m.group("n1")
        if name not in out:                 # \newcommand 已捕获的不重复计
            out[name] = read_value(m.end())
            kinds[name] = "def"

    return out, dup


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old", type=Path, help="旧版宏文件")
    ap.add_argument("new", type=Path, help="新版宏文件")
    ap.add_argument("--expect-added", type=int, default=None,
                    help="预期新增宏数；不符也判 FAIL")
    ap.add_argument("--show-added", action="store_true", help="列出新增宏名")
    ap.add_argument("--strict", action="store_true",
                    help="把无法解析的宏定义形式（\\def 等）升级为失败；用于纯生成宏文件")
    args = ap.parse_args()

    for p in (args.old, args.new):
        if not p.is_file():
            print(f"ERROR: 文件不存在: {p}", file=sys.stderr)
            return 2

    old, old_dup = parse_macros(args.old)
    new, new_dup = parse_macros(args.new)

    # 解析不到任何宏时绝不能判 PASS —— 那是一张空校验合格证
    if not old and not new:
        print("ERROR: 两个文件都没解析出宏定义。检查路径，或该文件用了本脚本不认识的定义形式。",
              file=sys.stderr)
        return 2
    if not old or not new:
        which = args.old if not old else args.new
        print(f"ERROR: {which} 解析出 0 个宏；不构成有效比较。", file=sys.stderr)
        return 2

    missing = sorted(k for k in old if k not in new)
    changed = sorted(k for k in old if k in new and old[k] != new[k])
    added = sorted(k for k in new if k not in old)

    print(f"OLD:     {len(old)} macros  ({args.old})")
    print(f"NEW:     {len(new)} macros  ({args.new})")
    print(f"MISSING: {missing}")
    if changed:
        print("CHANGED:")
        for k in changed:
            print(f"    \\{k}: {old[k]!r} -> {new[k]!r}")
    else:
        print("CHANGED: []")
    print(f"ADDED:   {len(added)}")
    if args.show_added and added:
        for k in added:
            print(f"    +\\{k} = {new[k]!r}")

    ok = not missing and not changed

    dups = sorted(set(old_dup) | set(new_dup))
    if dups:
        # 同名两次 \newcommand 在 LaTeX 里本身就是错误，且会静默掩盖值的变化
        print(f"DUPLICATE: {dups}   （同名重复 \\newcommand，后定义覆盖了前定义）")
        ok = False

    if args.expect_added is not None and len(added) != args.expect_added:
        ok = False
        print(f"ADDED-MISMATCH: expected {args.expect_added}, got {len(added)}")

    if args.strict:
        raw = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                        for p in (args.old, args.new))
        n_def = len(_DEF_RE.findall(strip_comments(raw)))
        if n_def:
            print(f"STRICT: 发现 {n_def} 处 \\def 定义；纯生成宏文件不应使用 \\def")
            ok = False

    print(f"VERDICT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
