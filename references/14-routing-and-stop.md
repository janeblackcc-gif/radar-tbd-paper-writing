# 14 · 路由与停止机制

> 适用语言：通用。配套：`gates/gates.json`、`scripts/run_gates.py`、`scripts/run_regressions.py`

本方法最贵的一类浪费不是某次改错，而是**没有一个可执行的「什么时候不再改」判据**：每轮都能找到「还可以再润色」的句子，于是同一段被改第三遍、第四遍，每遍都可能把已经自然的句子换成同义词，把必要的边界句当模板清掉。

本文件把改稿过程写成一台状态机，让停止成为默认，继续成为需要理由的例外。

## 一、四态判定，没有总分

`run_gates.py` 跑完注册表里的门禁后只输出四态之一：

| 判定 | 触发条件 | 下一步 |
|---|---|---|
| **BLOCKED** | 契约门失败（宏漂移、改动未归因）或任一门禁因工具/用法错误没跑成 | **禁止改稿**。先修契约或环境。工具没跑成不能出具任何合格证 |
| **TARGETED** | 至少一个硬门 `HARD_FAIL` | 按报告里的 unit / 失败项定点修。每 unit 只套一张卡片（见 §四），同维度最多 2 次 |
| **REVIEW** | 硬门全过，但有 `REVIEW_REQUIRED` 项、软热区超阈，或硬门因缺输入被跳过 | 人工逐条判定：写豁免（带标签与理由）或改。判定完重跑 |
| **FROZEN_OK** | 硬门全过、无待审项、无硬门跳过 | **停止**。再改只能由 §三 的触发条件启动 |
| **STAGE_OK** | 仅写稿阶段 `--stage skeleton\|chapter`：该阶段所选门全过（缺输入的门跳过不降级） | 交该章样张、写下一章。**不是冻结**——冻结只由 `--stage freeze` 的 FROZEN_OK 给出（16-drafting-loop） |

三条硬约束：

1. **硬门不可补偿。** 一个硬门失败不会被别的门的好结果抵消——「句法自然 10 分」不能补「比较方向改错」。
2. **软门只产生热区，永不失败。** 风格类指标（连接词密度、句长变异、段长整齐度）只回答「哪些段落值得人再看一眼」，不回答「这段是不是 AI 写的」，更不驱动自动改写。
3. **工具错误 = BLOCKED，不是 PASS。** 路径打错、`pdftotext` 缺失、注册表解析失败，都不能静默降级成「该门未运行」然后放行。`jargon_scan.py` 的 `collect_tex()` 对不存在的路径硬失败，就是这个原则。

## 二、什么算硬门、什么算软门

| 层 | 门禁 | 硬/软 | 失败即 |
|---|---|---|---|
| 0 契约 | `macro_zero_change`（宏零变化）、`page_delta`（页级改动归因残差）、`change_ledger`（段落级改动归因：账本残差 = 0） | 硬 | BLOCKED |
| 0 契约 | `semantic_diff`（语义不变量：数值/单位/引用键/宏名/图表号/「分别」序列逐段一致；方向词、范围限定、否定计数只待审） | 硬 | TARGETED |
| 1 骨架 | `claim_ledger`（闭环表完整、基线进摘要） | 硬 | TARGETED |
| 3 词汇 | `hedge_budget`（防御句上限/位置/同边界≤2/**下限**）、`term_variants`（术语表避免用法；`concept_groups` 非规范形态）、`jargon_scan`（禁用词双范围） | 硬 | TARGETED（jargon 命中需与豁免数比对，脚本本身只给 REVIEW；concept_groups 默认待审，`--enforce` 后硬） |
| 5 验收 | `page_fill`（半空页） | 硬，可按页豁免 | TARGETED |
| 4 自然度 | `style_audit`（模板句 / 连接词密度 / 名词链 / 句法节奏 / 结果段首 / 断言—证据距离） | **软** | 只出热区；高优先级热区 ≥ `--review-at`（注册表取 3）才判 REVIEW |

判据：**门禁检查的是否是「稿子说了什么」。** 数字、方向、边界、术语、结构、版面是硬门；「读起来顺不顺」是软门。硬门的阈值只放 `gates.json`，不散落在脚本默认值里。

新门禁进注册表前必须先在两份真稿上跑过：一份是已过审的定稿（不得被它拦），一份是在改的草稿（它必须拦住已知缺陷）。本仓库的记录：`claim_ledger` 第一版在定稿上误报 10 条——闭环表里合法的「bootstrap 区间」「三臂消融」「评价合同」都不是图表引用；放宽证据钩子、样本量缺失降 REVIEW 之后才标硬。`semantic_diff` 第一版把段落拆分造成的数字「移动」判硬失败、把 `\Omega` 当数据宏，改成文件级核对并加非数据宏黑名单后，第二篇工作区对 HEAD 的硬失败从 27 段降到 24 段，剩下的全是真改动（加引用、内联参数、数字入宏）；`term_variants` 的后缀词族启发式在定稿上列出 8 个词族（过门限 / 低门限本就是不同概念），因此降为纯信息，同义关系只认 `concept_groups`。**没做过这一步的门不许标 hard。**

## 三、六条停止规则

1. **同一 unit 同一维度最多自动尝试 2 次。** 第二次没有明确改善，转人工；不做第三次同类改写。
2. **「可以进一步润色」不是继续修改的理由。** 继续改必须能指名：哪个 unit、哪个 reason_code、预期消除什么。指不出来就停。
3. **导师或金标准标记「自然」的段落进入保护名单**（`paper.gates.json` 的 `protected_units`），任何自动改写不得触碰；改它只能由导师意见触发。
4. **软热区下降不能覆盖任何硬门失败。** 风格改善后硬门仍红，判定仍是 TARGETED。
5. **无高优先级热区时停止自动改写。** REVIEW 状态下的软热区由人决定要不要理会；不理会就写一条豁免，不要「顺手润色」。
6. **FROZEN_OK 之后继续修改只能由两类事件触发：具体的导师/审稿意见，或新检测到的事实问题（数据换工作点、代码修正、引用核验失败）。** 触发事件要写进 `edits/units.jsonl` 的 `trigger` 字段。没有触发记录的改动，`change_ledger` 视为未归因。

## 四、路由：每 unit 一张卡片

TARGETED 报告里的每个失败项带一个 reason_code。agent 按下表只取**一张**卡片处理该 unit，不跑全套：

| reason_code（来源门禁） | 卡片 | 允许改 | 禁止改 |
|---|---|---|---|
| `abstract_missing_baseline`（claim_ledger） | `cards/section-rules/abstract.md` | 摘要补一句带限定的比较结论 | 结果章数字、比较方向 |
| `claim_dangling` / `claim_no_boundary`（claim_ledger） | `cards/dimensions/hedging-balance.md` | 大纲闭环表该行；正文对应主张句 | 其他主张 |
| `hedge_over_budget` / `hedge_position`（hedge_budget） | `cards/dimensions/hedging-balance.md` | 删或合并该句 | 两问都答「是」的真实唯一边界 |
| `hedge_floor_missing`（hedge_budget） | `cards/section-rules/conclusion.md` | 结论/结果补一句适用范围 | 引入正文没铺垫过的新 caveat |
| `page_blank`（page_fill） | `cards/section-rules/results.md` §浮动体 | 去 `\FloatBarrier`、改浮动位置、拆大浮动体 | 正文文字 |
| `jargon_hit`（jargon_scan） | `cards/dimensions/final-copyedit.md` | 正名表替换；图内标签改绘图脚本 | 术语定义句、算法框英文 |
| `term_variant`（term_variants） | `cards/dimensions/final-copyedit.md` | 统一到术语表冻结词 | 公式符号 |
| `template_phrase` / `four_char_hype` / `adverbial_padding` / `connector_density` / `generic_closing`（style_audit） | `cards/dimensions/template-repair.md` | 删模板框架、四字格换已有数字、删空连接词 | 术语、带标签防御句、摘要、缺口句 |
| `noun_chain` / `triple_de`（style_audit） | `cards/dimensions/noun-chain-unpack.md` | 用显式因果拆句、范围另起一句 | 冻结术语字面、因果方向、数字 |
| `uniform_rhythm` / `repeated_opening` / `long_sentence` / `paragraph_too_long` / `passive_marker`（style_audit） | `cards/dimensions/syntax-rhythm.md` | 拆并句、换起句、被动改主动、按焦点切段 | 限定范围、图表与解读的同段关系、术语 |
| `figure_first_opening` / `claim_far_from_evidence`（style_audit） | `cards/dimensions/result-first-repair.md` | 把段内已有的现象句移到段首、补已有钩子 | 新造结论或数字、图注、浮动体 |
| 章节级人工判定（第一句立技术设定、逐篇罗列、小节无动机句、讨论重复结果章） | `cards/section-rules/{introduction,related-work,method,discussion}.md` | 见各卡片 | 见各卡片 |

卡片是给 agent 自己执行的，不是发给 LLM 改写服务的提示词——所以叫 `cards/` 不叫 `prompts/`。每张卡片固定五段：触发 → 允许改 → 禁止改 → 必保留 → 自检与停止条件。

默认流程不是「预润色 → 句法轮 → 终稿轮」三轮全跑，而是：

```
诊断 → 只路由到一张最相关的卡片 → 改 → 重跑相关门禁 → 停止 或 转人工
```

## 五、并行与合并

- 章节未经批准（09-mechanics §一 逐章硬停点），不跨章并行。
- 章节结构批准后，可在该章内按自然段并行生成候选。
- 合并后必须做一次**章级全局扫描**：重复段首、术语一致性、连接关系。每段独立自然化后直接拼接不是交付稿。

## 六、与既有机制的关系

| 既有机制（09-mechanics） | 状态机里的位置 |
|---|---|
| 逐章硬停点（§一） | 章级 FROZEN_OK 才能进下一章 |
| 三列对照单（§四） | 由 `edits/units.jsonl` 承担，`change_ledger` 机器核对 |
| PLAN_DISCREPANCY（§五） | 范围外问题登记 → 不改；对应 REVIEW 里「写豁免」那条路 |
| 逐页 delta 残差 = 0（§六） | 契约门 `page_delta`，失败即 BLOCKED |
| 阶段依赖硬门（§十四） | 骨架层 FROZEN_OK 之前，结构/词汇/自然度门禁不执行 |

## 七、项目配置 `paper.gates.json`

放在稿件目录（或任何本地位置，路径不入 skill 仓库）：

```json
{
  "sections": ["sections_zh"],
  "main": "main_zh.tex",
  "pdf": "main_zh.pdf",
  "macros": ["generated/results_macros.tex"],
  "outline": "notes/大纲与逻辑链.md",
  "glossary": "notes/术语表.md",
  "exemptions": "paper.exemptions.json",
  "banned_terms": "paper.banned.txt",
  "roles": {"05_experiments_results": "results", "06_conclusion": "conclusion"},
  "method_names": ["STR-FCM-TBD"],
  "internal_baselines": ["NCV-FCM-TBD", "已知率参考"],
  "external_baselines": ["GT-ML-PDA"],
  "baseline_aliases": {"GT-ML-PDA": ["GT 基线", "适配 GT-ML-PDA"]},
  "pdf_base": "archive/renders/r12.pdf",
  "macro_base": "archive/generated/results_macros_r12.tex",
  "attributions": {"abstract": 40, "section 5.4": 123},
  "base_rev": "r12-frozen",
  "concept_groups": {"转弯率假设": ["率切片", "转弯率切片"]},
  "ledger": "edits/units.jsonl",
  "protected_units": ["05_experiments_results#12"]
}
```

`base_rev` 是上一冻结版的 git 提交号或标签，`change_ledger` / `semantic_diff` 拿它取旧版；缺失时这两门被跳过。`ledger` 缺省为稿件目录下的 `edits/units.jsonl`。`concept_groups` 见 03-diction §六。

`pdf_base` / `macro_base` 缺失时契约门被跳过，整体最多判 REVIEW，不判 FROZEN_OK——第一次跑没有基线是正常的，但**冻结前必须补齐**。写稿阶段用 `--stage skeleton|chapter`（注册表 `stages` 键，16-drafting-loop）：只跑该阶段的门，缺输入的门跳过不降级，全过判 STAGE_OK。

豁免文件 `paper.exemptions.json` 按门禁分键，每条带 `match`（原句子串，不是正则）、`tag`、`reason`：

```json
{
  "hedge_budget": [{"match": "算法可见信息仅为位置与幅度", "tag": "information_contract", "reason": "已知/未知信息合同，07-code-consistency §十"}],
  "page_fill": [{"page": 12, "reason": "章末 clearpage，导师认可"}]
}
```

`tag` 只能取：`statistical_boundary` `baseline_identity` `information_contract` `model_assumption` `evaluation_condition` `submission_compliance` `evaluator_disclosure` `pointwise_declaration`。带这些标签的句子不进普通模板清理；要动它只能走 `hedging-balance` 卡片并同步核对闭环表。

## 八、回归：每一次真实失败都变成一条用例

`tests/fixtures/<gate>/<case>/case.json` 三类：

- `must_change`：门禁必须拦住的合成缺陷（引言出现防御句；结果章比较了 GT 而摘要不提；半空页）
- `must_preserve`：门禁不得误伤的合法写法（结果 1 次 + 结论呼应 1 次的同一边界；末页短页；合法的定义式对照句）
- `manual_review`：只能转人工的情形（非法豁免标签、按页豁免）

`scripts/run_regressions.py` 全绿是改任何门禁脚本的前置条件。真稿端到端放 `tests/golden/local_paths.json`（gitignored，只有本地路径与期望判定）。

新增规则的流程：先写 `must_change` 用例复现事故 → 改门禁让它红 → 补 `must_preserve` 用例证明没误伤 → 在两份真稿上跑 → 再标 hard。用例 schema、`git_case` / `synth_pgm` 字段、golden 的 config 型与 script 型（git 历史回放）、第一篇 r10→r22 历史语料与 A/B 六指标见 [15-regression-corpus.md](15-regression-corpus.md)。
