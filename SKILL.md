---
name: radar-tbd-paper-writing
description: 面向雷达检测前跟踪（TBD）、群目标/编队跟踪、多目标数据关联方向的期刊论文写作方法。适用于：从代码仓库与实验结果起草论文、中文母稿写作与逐轮改稿、导师或审稿意见的落实、论文术语与行话治理、防御性表述治理、论文与代码一致性核查、中文母稿转英文投稿稿。当任务涉及"写论文/改稿/审稿/摘要引言重写/术语统一/行文不像期刊论文/读不下去/去 AI 味"时使用。默认目标期刊为 IET Radar Sonar & Navigation 一类的传统雷达工程期刊。
---

# 雷达 TBD 论文写作

本方法来自一篇 IET RSN 投稿从"读不下去"到定稿的完整改稿周期（25 天、22 个渲染版本、三次被打回）。每条规则都有真实失败作依据，不是风格偏好。本文件是摘要层：规则的完整条款、配对条件与例外都在 references 里，动手前必读对应文件（§八）。

## 一、先接受这个事实：缺陷分三层，且相互正交

同一份稿子被否决三次，每次都是不同的层：

| 轮次 | 判词 | 缺陷层 | 当时状态 |
|---|---|---|---|
| 1 | "极其糟糕、读起来意义不明的黑话" | **词汇层** | 读第一章即停 |
| 2 | "臃肿、重点不突出、逻辑不通顺、非常跳跃、没有形成连贯的论文叙事" | **结构层** | 数字、claim、术语、统计口径**全部检查通过** |
| 3 | "major revisions，连我这关都过不了"（70 条批注） | **词汇层又犯** | 结构已重构完成 |

三条推论，违反任何一条都会重复上面的循环：**科学正确 ≠ 写作合格**（写作质量是独立验收维度）；**结构与词汇必须分两轮治理，先结构后词汇**；**结构治好不代表词汇合格**，骨架重构完必须单开一轮只做词汇清洗。

## 二、你的语感不可信

写了三个月的人，语感已经被项目内部词汇污染——**行话的定义就是写的人已经读不出它是行话**。判据必须锚在外部并机械执行：圈外同行一眼看不懂 → 黑话；目标期刊近年录用论文里不出现 → 黑话。手段是禁用词表 + 正名表 + `grep` 清零 + 退出码存证，不是"再读一遍改通顺"（[03-diction.md](references/03-diction.md)）。

## 三、范文对标：贯穿全程的质量锚

**动笔前先选定范文，不是写完了再对照。** 默认范文：Bu, Rao, Song, "A group target track-before-detect approach using two-stage strategy with maximum-likelihood probabilistic data association," *IET RSN* 18(8):1351–1363, 2024（DOI `10.1049/rsn2.12574`）——导师点名认可，同刊同题材；换方向时按同刊、近三年、同方法族、含实验章另选。

**照骨架，不照皮肤。** 可参考层：章节递进、图表出场次序、段落功能、讲解分层、术语语境；不可继承层：句子、实验参数、判定阈值、样本量、结论措辞。量化自比方法见 [05-calibration.md](references/05-calibration.md)。

## 四、工作流：第 0 层契约 + 四层 + 停止机制

**第 0 层 · 契约。** 任何一轮改稿开始前三条契约就绪，否则 **BLOCKED**、禁止改稿：科学真实性契约（闭环表 + 生成宏 + 术语表冻结了什么绝对不能变）、编辑范围契约（这一轮允许碰哪些文本；结构轮之后段落边界冻结）、策略契约（为什么还要改、改哪个 unit、改到哪停）。见 [12-edit-contract.md](references/12-edit-contract.md)。

**写稿循环。** 门禁从第 0 天起就用，不是等稿子写烂了再修：配置、闭环表、术语表、禁用词文件就位后跑 `--stage skeleton`；每写完一章跑 `--stage chapter`（只跑对已写章节有意义的门，全过判 `STAGE_OK`，可交样张）；全文首次编译后 `--stage freeze`，`FROZEN_OK` 才是冻结，冻结提交号写进 `base_rev`，账本从此开始。每张章节卡片的「动笔前（写作契约）」段是写该章前要读的清单。见 [16-drafting-loop.md](references/16-drafting-loop.md)。

**第 1 层 · 骨架。** 正文动笔前先落盘一份独立的大纲与逻辑链文件，含四件东西：全文核心问题（一句疑问句）；全文最短因果链（5–8 步，此后任何删改都必须仍能把链讲通）；逐节「本节要回答的问题」；主张—证据闭环表三列 `主张 | 证据挂接（图表与样本量）| 封口结论与边界`。执行规则：**挂不上因果链的内容不写入，旧稿现成段落也不迁移、不改写、直接弃用**——这替代的是"在旧稿上逐句润色"这个默认做法。见 [01-skeleton.md](references/01-skeleton.md)。

**第 2 层 · 结构。** 按章写，每章的固定写法在 [02-narrative.md](references/02-narrative.md)，写前清单在对应卡片的「动笔前」段：

| 章 | 一句话要求 | 卡片 |
|---|---|---|
| 摘要 | 第一条实质结论是正面结果；做了基线比较就必须进摘要 | [abstract](cards/section-rules/abstract.md) |
| 引言 | 第一句立研究对象；缺口句全文唯一且对应贡献第一条；方法名在缺口之后首现 | [introduction](cards/section-rules/introduction.md) |
| 相关工作 | 按方法族、先复述机制再单一维度差异；只给适用性判据，禁二分贬低 | [related-work](cards/section-rules/related-work.md) |
| 方法 | 每小节 动机句 → 对策 → 公式 → 算法框；实现细节移出、数值参数留下 | [method](cards/section-rules/method.md) |
| 结果 | 汇总统计之前先走同种子证据链；段首先现象后图号；每图 2–3 句现象 + 机制 | [results](cards/section-rules/results.md) |
| 讨论 / 结论 | 局限只说一次、正面在前；结论两段：成果段 → 边界段 | [discussion](cards/section-rules/discussion.md) / [conclusion](cards/section-rules/conclusion.md) |

**第 3 层 · 词汇。** 结构定稿后单开一轮，只做措辞：禁用词表 + 正名表；新词三关（同义重复 / 一词双义 / 英文直译）；术语表四列 `冻结词 | 首选外文 | 使用语境 | 避免用法`，第四列是关键。清零验收必须双范围——`.tex` 源码和 `pdftotext -enc UTF-8` 抽取的渲染文本，图内标签在源码里 grep 不到。见 [03-diction.md](references/03-diction.md)。

**第 4 层 · 验收。** 能机械化的都是门禁脚本，由 `scripts/run_gates.py` 按 `gates/gates.json` 统一执行；只输出 **BLOCKED / TARGETED / REVIEW / FROZEN_OK**（写稿阶段另有 STAGE_OK），没有可补偿的总分：

| 层 | 检查什么 | 门禁 | 硬/软 |
|---|---|---|---|
| claim 纪律 | 闭环表逐条销账；**结果章比较了外部基线，摘要必须提** | `claim_ledger` | 硬 |
| 叙事连贯 | 逐章复述因果链 + 范文量表自比 | —（人工） | — |
| 防御性表述 | 上限 / 位置白名单 / 同边界 ≤ 2 / **下限：结果与结论各 ≥ 1 句适用范围** | `hedge_budget` | 硬 |
| 词汇 | 禁用词双范围清零（命中数 = 已人工判定豁免数）；术语表避免用法零命中；同一概念一个词形 | `jargon_scan`、`term_variants` | 硬 |
| 排版 | 页级渲染目检；半空页机器抓 | `page_fill` + 目检 | 硬 |
| 改动可信度 | 宏零变化；逐页 delta 残差 = 0（必要条件）；段落级账本归因 + 语义不变量（充分条件） | `macro_diff`、`page_delta`、`change_ledger`、`semantic_diff` | 硬，契约门失败即 BLOCKED |
| 表层自然度 | 模板句 / 连接词密度 / 名词链 / 节奏 / 结果段首；只出热区 | `style_audit` | **软**，永不失败 |

词汇层的口径不是「退出码必须为 0」：有算法框的中文稿伪代码体写英文，PDF 侧必然有命中，拿 0 当唯一门槛会逼你删掉核心概念名。新门进注册表前必须在两份真稿上校准：定稿不得被拦，草稿的已知缺陷必须拦住。

**停止机制。** 改稿是一台默认停止的状态机（[14-routing-and-stop.md](references/14-routing-and-stop.md)）：同一 unit 同一维度最多 2 次；「可以进一步润色」不是理由；导师认可的段落进保护名单；软热区不覆盖硬门；FROZEN_OK 之后再改只能由导师意见或新事实触发。TARGETED 时每个 unit 只套一张卡片。

**阶段依赖不可交换。** `骨架 → 锁模型 → 重建实验 → 重构结构与图表 → 翻译`。母稿逻辑与实验未过审，不得进入翻译或排版——本项目的原始错误就是在英文稿上逐句润色，而问题在中文逻辑层（[09-mechanics.md](references/09-mechanics.md) §十四）。

## 五、成对规则：防止单向执行

**每一条禁止夸大的规则，旁边必须配一条禁止自我削弱的规则。** 否则规则会被单向执行到自我否定——这正是本项目第二次被否决的直接原因。

| 禁止夸大 | 配对的禁止削弱 |
|---|---|
| 不写未经实验支持的性能归因 | 做到的必须写进摘要；最强结果不得只活在图里 |
| 消融改了几个部件，结论只能覆盖几个部件 | 不因归因受限就用失败开头，正面结论仍排在最前 |
| 不外推到未验证的维度与规模 | 适用范围写一次即可，不反复致歉 |
| 不写"首次/据我们所知第一个" | 也不因此放弃陈述贡献，改用具体未解决问题 |
| 确定性步骤不加"近似/可能次优" | 真实近似照实写，不美化 |

防御性表述的定量预算（上限、位置白名单、同边界 ≤ 2、下限、摘要不计入额度）见 [04-hedging.md](references/04-hedging.md)。

## 六、三处反向护栏

1. **"段间用然而/因此承接" ⟷ "删除过密连接词"**：按因果关系真实需要加，连接词密度过高本身就是 AI 腔。
2. **"结果段禁用问句"是传统工程期刊的口味**：IET/TAES 适用；ML 会议把 "Does X help?" 当标准段首。按目标期刊定。
3. **批量清洗"不是 X 而是 Y"会误伤合法句式**：只删带假想反驳语气的；用于下定义或指定归属的对照句是正常中文。

外部佐证：一个独立的中文降 AI 率工具（FYADR）在实测后撤回了自己的句长比例、短句配额、被动句配额和检测平台对标——**风格指标只能定位问题，不能支配科学内容，更不能设配额。**

## 七、工具边界不得静默决定论文声称什么

"实验数字只走生成宏、禁止手抄"是对的纪律。但本项目出过：宏生成器只输出本方法的数字，正文在该纪律下**结构性地写不出与基线的对比**，最强结果只活在一张图里，摘要开头写的却是消融不能证明什么。**发现"这句话写不出来"时，先判断是不是工具缺陷**——是就扩生成器并核验既有输出零变化，不是绕过纪律手抄，更不是放弃陈述（[06-evidence.md](references/06-evidence.md)）。

## 八、references 导航

| 文件 | 何时读 |
|---|---|
| [01-skeleton.md](references/01-skeleton.md) | 动笔前搭骨架、写大纲与逻辑链文件 |
| [02-narrative.md](references/02-narrative.md) | 写或重写任一章节 |
| [03-diction.md](references/03-diction.md) | 词汇轮、术语统一、去行话、去 AI 味、禁用词模板三节说明 |
| [04-hedging.md](references/04-hedging.md) | 局限/边界/防御性表述的处理 |
| [05-calibration.md](references/05-calibration.md) | 选范文、拆范文、量化自比 |
| [06-evidence.md](references/06-evidence.md) | 数字宏机制、图证链、数据换工作点后的回扫 |
| [07-code-consistency.md](references/07-code-consistency.md) | 写伪代码、方法章、复杂度段 |
| [08-experiment.md](references/08-experiment.md) | 设计实验、seed 管理、统计口径、分析地位标注 |
| [09-mechanics.md](references/09-mechanics.md) | 逐章硬停点、PLAN_DISCREPANCY、删减去向、批注原件保护、**阶段依赖硬门（§十四）** |
| [10-chinese.md](references/10-chinese.md) | **中文特有**：量词歧义、中英混排、复合名词、伪代码语言、**中→英翻译轮（§八）** |
| [11-naturalness.md](references/11-naturalness.md) | 第 4 层表层自然度：十项职责、反向退化信号、「无明确问题不改」、优先级 |
| [12-edit-contract.md](references/12-edit-contract.md) | 任何改稿轮开始前：三契约、阶段→可改范围表、语义不变量、候选账本 schema 与核对命令 |
| [13-style-audit.md](references/13-style-audit.md) | style_audit 信号定义、文档级指标、热区处理 |
| [14-routing-and-stop.md](references/14-routing-and-stop.md) | 跑门禁、读判定、决定改还是停；硬/软门判据、停止规则、卡片路由、**项目配置与豁免格式（§七）** |
| [15-regression-corpus.md](references/15-regression-corpus.md) | 改门禁脚本或阈值前：用例 schema、真实失败→用例流程、历史语料、**全部门禁的校准记录**、A/B 六指标 |
| [16-drafting-loop.md](references/16-drafting-loop.md) | **动笔前与逐章写作**：第 0 天配置、三阶段、从写稿切到改稿的时点 |

## 九、scripts

```bash
scripts/run_gates.py --config <稿件目录>/paper.gates.json --stage skeleton|chapter|freeze --report gate_report.md
scripts/run_gates.py --config <稿件目录>/paper.gates.json --report gate_report.md      # 改稿轮：全部门禁
scripts/run_regressions.py                                                           # 改任何门禁脚本前后必须全绿
```

单个门禁脚本的参数以各脚本 `--help` 与 `gates/gates.json` 的 args 为准；项目配置与豁免文件格式见 14 §七；校准记录见 15。Windows 下 `pdftotext` 必须带 `-enc UTF-8`，否则中文全部丢失且不报错——脚本已内置，手跑别漏。
