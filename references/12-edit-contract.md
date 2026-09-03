# 12 · 编辑契约：改之前先定「什么绝对不能变」

> 适用语言：通用。配套：`gates/gates.json` 第 0 层、`scripts/change_ledger.py`、`scripts/semantic_diff.py`

改稿的每一轮都在三条契约之下进行。三条全部就绪，agent 才允许生成候选修改；任何一条失效，判定为 BLOCKED（见 [14-routing-and-stop.md](14-routing-and-stop.md)）。

```
科学真实性契约  +  编辑范围契约  +  策略契约  =  允许生成候选修改
```

## 一、科学真实性契约：改写后什么科学含义绝对不能变

由骨架层与证据层的既有产物构成，不另写文件：

| 来源 | 冻结内容 |
|---|---|
| 大纲文件的主张—证据闭环表（[01-skeleton.md](01-skeleton.md)） | 每条 claim 的陈述、证据挂接、允许范围、禁止外推 |
| 生成宏文件（[06-evidence.md](06-evidence.md)） | 全部实验聚合数值；`macro_zero_change` 门禁保证零漂移 |
| 术语表四列（[03-diction.md](03-diction.md) §四） | 冻结词、外文、语境、避免用法 |
| 配置参数表 | 手写的配置常数（门限、步长、上限） |

改写过程中必须逐项保持的语义不变量（`semantic_diff.py` 机器核对）：

**必须完全一致**：所有数值与正负号、单位、公式块、引用键、`\label/\ref/\eqref`、图表编号、列表编号、缩写、方法名、参数符号、样本量、置信区间端点。

**必须保持方向**：

| 不变量 | 例 |
|---|---|
| 谁减谁 | A−B 的正负方向；「GT 比 STR 高 56 m」不能变成「STR 比 GT 高」 |
| 区间与零的关系 | 「包含零」/「不包含零」 |
| 强弱限定 | 至少 / 至多 / 严格大于 / 不低于 |
| 信息合同 | 已知 / 未知；算法使用 / 不使用真值 |
| 证据强度 | 支持 / 未显示 / 不能区分 |
| 统计口径 | 平均结论 / 逐场景结论；逐点区间 / 族系区间 |
| 基线身份 | 内部对照 / 外部基线 / 适配实现 / 作者原代码 |

**需要人工确认**的漂移：因果变相关、能力变效果、「缓解」变「解决」、「补充比较」变「外部基线」、「在所设条件中」被删、必要 caveat 被模板清理器误删。

## 二、编辑范围契约：这一轮允许看见和修改哪些文本

范围随阶段变，不是永远固定成「正文段落」：

| 阶段 | 允许修改 | 必须保护 |
|---|---|---|
| 骨架轮 | 章节与段落次序、段落角色 | 数值、公式、实验身份 |
| 结构轮 | 正文段落、部分标题、图表出场次序 | 数学表达、引用键、生成宏 |
| 词汇轮 | 句内措辞、术语首次定义 | 段落次序、句间逻辑 |
| 自然度轮 | 句法、句界、指代、重复 | 段落角色、事实、术语、公式、**段落边界** |
| 终检轮 | 只读 | 全部 |

**结构轮结束即冻结段落边界**：此后不拆段、不并段、不移段。这是 FYADR 类保守编辑器「段落数量与角色不变」规则在本方法里的位置——它只在结构冻结之后启用，与骨架/结构轮允许大改不冲突。

LaTeX 自然度轮自动保护（`latex_scope.mask_non_prose` 已实现）：数学环境与行内公式、`\cite/\ref/\eqref/\label`、`\input/\includegraphics`、生成宏名、`algorithmic` 环境、表格数值单元、URL/DOI/文件名/代码标识。

## 三、策略契约：为什么还要改、改什么、改到哪停

`run_gates.py` 的判定就是策略契约的机器形式：

```
decision : BLOCKED | TARGETED | REVIEW | FROZEN_OK
targets  : [unit_id, reason_code, 卡片]
attempts : 每 unit 每维度 ≤ 2
stop     : 硬门全过 + 无待审 + 无高优先级热区
trigger  : FROZEN_OK 之后继续改的事件（导师意见 / 新事实）
```

没有 TARGETED 清单就没有改稿动作。

## 四、候选账本：模型输出只是候选，不直接成为正文

每个改动单元记一行到 `edits/units.jsonl`（默认位置：稿件目录下；`change_ledger.py` 核对）：

```json
{"unit_id": "05_experiments_results#12@af95d455",
 "section": "results",
 "round": 3,
 "dimension": "hedging",
 "reason_code": "hedge_over_budget",
 "source_text": "……",
 "candidate_text": "……",
 "gates": {"semantic_diff": "PASS", "hedge_budget": "PASS"},
 "decision": "accept",
 "attempts": 1,
 "covers": ["05_experiments_results#12@af95d455"],
 "trigger": "advisor_comment#7",
 "review_note": ""}
```

- `decision ∈ {accept, reject, manual}`；只有 `accept` 与 `manual` 进正文。
- `covers` 列出该条目解释的全部 unit（一次改动合并两段时写两个 id）。
- 两版之间 `git diff` 里每个变了的 unit 必须能在账本里找到 `accept|manual` 条目，否则 `change_ledger` 判 HARD_FAIL——这是 09-mechanics §六「逐页 delta 残差必须为 0」的段落级版本，且抓得住等长改写。

它替代的是三列对照单（09-mechanics §四）的手工形式，三列的信息（原文 → 新文 → 依据）全在字段里。

核对命令（`base_rev` 写在配置里时 `run_gates.py` 会自动跑这两门）：

```bash
python scripts/change_ledger.py --config paper.gates.json --base-rev <上一冻结版提交号>
python scripts/semantic_diff.py  --config paper.gates.json --old-rev  <上一冻结版提交号>
```

两门的分工：`change_ledger` 回答「每处改动有没有人负责」，`semantic_diff` 回答「负责的人有没有把事实改坏」。结构轮之间跑 `semantic_diff` 必然大片硬失败——段落拆并、手抄数字入宏、加引用都是它要拦的事——所以它是词汇轮与自然度轮的门，结构轮只用 `change_ledger` 归因，语义核对靠闭环表复述。段落在同一文件内移动的数字/引用只记待审（「在同文件段落间移动」），文件级也丢了才是硬失败。

三个它能防住的事故：模型为了改一处重复顺便重写整段；第二轮把第一轮改好的句子再换一遍同义词；后续发现问题时不知道是哪一轮引入的。

## 五、与三层验收的关系

| 09-mechanics §三 的层 | 契约 |
|---|---|
| claim 纪律 | 科学真实性契约 → `claim_ledger` |
| 词汇 | 科学真实性契约（术语表）→ `jargon_scan` / `term_variants` |
| 改动可信度 | 编辑范围契约 → `page_delta` / `change_ledger` |
| 排版 | — → `page_fill` + 页级目检 |
| 叙事连贯 | 仍是人工：逐章复述因果链 + 范文量表自比 |
