# radar-tbd-paper-writing

适用于 Claude Code 等支持 Skill 的代理：雷达检测前跟踪（TBD）、群目标与编队跟踪方向的**期刊论文写作与复核方法**，中文母稿优先。包含人工审核规则、可执行诊断及合成回归用例；工具结果不替代科研协议、执行授权或作者验收。

沉淀自一篇 IET RSN 投稿从「读不下去」到定稿的完整改稿周期（25 天、22 个渲染版本、三次被打回），以及第二篇论文母稿的评审轮。每条规则和每个门禁都有真实失败作依据。

## 2026-10-08 更新

- 补齐全文与逐段逻辑递进、任务目标与中间手段区分、摘要的方法原理过渡。
- 按语义检查分号、冒号及英文显示公式的句末标点，不做全文件机械替换。
- 修正固定两段摘要、强制编号推导、删除论断却强留引用等旧要求，最新且适用的已采纳意见优先。
- 补充中英关系对齐、结果版本追溯、指标操作定义、基线先验披露与图表版面复核。
- 保持脚本接口、配置格式、退出码和默认阈值不变；新增规则由人工检查，适用性解释见 [项目适配原则](references/00-project-adaptation.md)。

更新只分发通用方法，不包含项目私有批注、会话或实验材料。项目复制安装不会自动升级，已有适配文件应保留并与通用规则合并。

## 为什么需要它

同一份稿子被否决三次，每次都是不同的缺陷层：

| 轮次 | 判词 | 缺陷层 | 当时状态 |
|---|---|---|---|
| 1 | 「极其糟糕、读起来意义不明的黑话」 | 词汇层 | 读第一章即停 |
| 2 | 「臃肿、重点不突出、逻辑不通顺、非常跳跃」 | 结构层 | 数字、claim、术语、统计口径**全部检查通过** |
| 3 | 「major revisions」（70 条批注） | 词汇层又犯 | 结构已重构完成 |

三条推论构成本 skill 的组织基础：

1. **科学正确 ≠ 写作合格**。写作质量是独立的验收维度。
2. **结构与词汇必须分两轮治理，先结构后词汇。**
3. **结构治好不代表词汇合格。**

第二篇论文又补了第四条：**规则写在文档里不等于会被执行。** 同一天里，最强结果被大纲文件主动关在一节里不进摘要、四个 `\FloatBarrier` 让 13 页变 15 页、结论章的适用范围句被整句删掉——三件事都有对应的规则，都没被人眼抓住。于是规则变成了门禁。

## 安装

```bash
git clone https://github.com/janeblackcc-gif/radar-tbd-paper-writing.git ~/.claude/skills/radar-tbd-paper-writing
```

依赖：Python 3.9+（无第三方包）；poppler 的 `pdftotext` / `pdfinfo` / `pdftoppm` 在 PATH 上。

已有 Git 克隆先确认工作区干净，再用 `git pull --ff-only` 更新；有本地定制或项目复制副本时先比较差异，保留项目 profile、现行术语和授权边界，不整目录覆盖。具体写作从 [SKILL.md](SKILL.md) 进入。

## 用法：跑门禁

项目允许接入时，在稿件目录配置 `paper.gates.json`（格式见 `references/14-routing-and-stop.md` §七）。既有稿件首次使用先 report-only 校准，再决定哪些诊断适合当前阶段：

```bash
python scripts/run_gates.py --config <稿件目录>/paper.gates.json --report gate_report.md
# 配置里给了 base_rev（上一冻结版提交号）才会跑 change_ledger / semantic_diff
python scripts/run_gates.py --config <稿件目录>/paper.gates.json --stage skeleton   # 动笔前：闭环表与术语表
python scripts/run_gates.py --config <稿件目录>/paper.gates.json --stage chapter    # 每写完一章：只对已写章节生效
```

输出以下工具诊断状态，没有可补偿的总分；它们不自动改写项目状态或授予执行权限：

| 判定 | 含义 |
|---|---|
| `BLOCKED` | 契约检查失败或工具未运行成功；核查具体原因、适用范围及当前项目要求 |
| `TARGETED` | 硬门失败 → 按报告定点修，每 unit 一张 `cards/` 卡片，同维度 ≤ 2 次 |
| `REVIEW` | 只剩待审项 / 软热区 / 硬门缺输入被跳过 → 人工判定，写豁免或改 |
| `FROZEN_OK` | 所配置检查通过，不代表作者验收或科学结论已确认 |
| `STAGE_OK` | 仅 `--stage skeleton\|chapter`：本阶段所选检查通过，不代表全稿冻结 |

## 结构

```
SKILL.md                     主线：四层缺陷 + 第 0 层契约 → 工作流 → 成对规则 → 反向护栏 → 停止机制
references/
  00-project-adaptation.md    意见优先级、工具适用性、项目定制及公开边界
  01-skeleton.md              骨架层：大纲与逻辑链文件、主张—证据闭环表
  02-narrative.md             结构层：逐章写法（含「基线比较必进摘要」硬规则）
  03-diction.md               词汇层：禁用词表、正名表、新词三关、定义桥、双范围清零
  04-hedging.md               防御性表述：定量预算、删除两问、成对规则、下限
  05-calibration.md           范文对标：可参考层 vs 不可继承层、量化自比量表
  06-evidence.md              证据治理：数字宏、二次舍入、图面核对、同种子图证链
  07-code-consistency.md      论文↔代码：追生产调用链、伪代码逐行核实现
  08-experiment.md            实验设计：预承诺收窄规则、指标矩阵、统计措辞
  09-mechanics.md             改稿流程：逐章硬停点、三列对照单、页级目检、阶段硬门
  10-chinese.md               中文特有：量词歧义、中英混排、伪代码语言、翻译轮
  11-naturalness.md           第 4 层表层自然度：十项职责、反向退化信号、无明确问题不改、优先级
  12-edit-contract.md         三契约：科学真实性 / 编辑范围 / 策略；语义不变量；候选账本
  13-style-audit.md           style_audit 信号定义、文档级指标、热区处理
  14-routing-and-stop.md      四态判定、硬/软门判据、六条停止规则、卡片路由、配置与豁免
  15-regression-corpus.md     用例 schema、真实失败→用例流程、第一篇历史语料、全部门禁校准记录、A/B 六指标
  16-drafting-loop.md         写稿循环：第 0 天配置、skeleton/chapter/freeze 三阶段、写稿切改稿的时点
  17-figures-tables-and-visual-qa.md  图表：尺寸由模板定、一个样式层、语义映射、按图类规范、导出、双重目检
  18-author-review-and-revision.md  后续意见、作者核对、删图与公式合并后的联动检查
gates/
  gates.json                  门禁注册表：id / 层 / 硬软 / 脚本 / 参数 / 失败即何态；阈值只在这里
cards/
  section-rules/              摘要 / 引言 / 相关工作 / 方法 / 结果 / 讨论 / 结论：触发 → 允许改 → 禁止改 → 必保留 → 自检与停止
  dimensions/                 hedging-balance / final-copyedit / template-repair / noun-chain-unpack / syntax-rhythm / result-first-repair / figure-visual-repair
scripts/
  run_gates.py                编排器：按注册表逐门执行 → 四态判定 + Markdown 报告
  run_regressions.py          回归总闸：合成用例 + 真稿端到端（本地路径，gitignored）
  latex_scope.py              共用库：段落单元切分（稳定 id）、非散文遮罩、章节角色、pdftotext -enc UTF-8
  claim_ledger.py             硬门：闭环表每行有证据钩子/样本量/边界；结果章外部基线摘要必提
  hedge_budget.py             硬门：防御句上限 / 位置白名单 / 同边界 ≤ 2 / 结果与结论各 ≥ 1 句适用范围
  page_fill.py                硬门：非末页尾部空白 > 35% 正文高度（双栏按半页）；纯 Python 解析 PGM
  change_ledger.py            契约门：两版之间每个改动段落须在 edits/units.jsonl 有 accept|manual 条目
  semantic_diff.py            硬门：数值/单位/引用/宏/图表号逐段一致；方向词只待审；支持中→英段落对
  term_variants.py            硬门：术语表第四列避免用法零命中；concept_groups 非规范形态待审
  style_audit.py              软诊断：模板句/连接词/名词链/节奏/结果段首热区 + 文档级指标 + baseline delta；永不失败
  macro_diff.py               契约门：宏零变化三重校验
  page_delta.py               契约门：逐页字符数 delta 归因，残差必须为 0
  jargon_scan.py              硬门：禁用词双范围扫描（源码 + PDF）
  banned-terms-template.txt   禁用词模式模板
tests/
  make_fixtures.py            生成合成用例（幂等）
  fixtures/<gate>/<case>/     must_change / must_preserve / manual_review 三类
  golden/local_paths.example.json   真稿端到端配置模板（真实路径不入库）；config 型比四态，script 型回放 git 历史
  golden/local/               （gitignored）真稿配置与历史快照导出 hist/<rev>/
```

## 门禁如何进注册表

新门禁必须先在**两份真稿**上校准：一份已过审的定稿（不得被它拦），一份在改的草稿（已知缺陷必须拦住）。每个门的校准记录只在 `references/15-regression-corpus.md` §八 维护。

每一次真实失败都转成 `tests/fixtures` 的一条用例；改任何门禁脚本前后 `run_regressions.py` 必须全绿。第一篇 r10→r22 的六个提交已作为历史语料进 golden：r10 母稿的「结果章比较四类基线而摘要不提」「结果章无适用范围句」两条硬失败，当时靠导师读出来，现在由 `claim_ledger` / `hedge_budget` 在快照上复现（references/15-regression-corpus.md §五）。

## 两条设计取向

**成对规则。** 每一条禁止夸大的规则，旁边必须配一条禁止自我削弱的规则。`hedge_budget` 同时有上限和下限，就是这条的机器形式。

**工具边界不得静默决定论文声称什么。** 「实验数字只走生成宏」是对的纪律，但当生成器只输出本方法的数字时，正文在该纪律下会结构性地写不出与基线的对比。`claim_ledger` 的基线镜像规则专门拦这一类。

## 不做什么

- 不以任何 AIGC 检测率为目标；风格指标只定位段落，不支配科学内容，不设句式配额。
- 不默认对每段跑多轮改写；先诊断，只路由到一张卡片，改完重跑门禁，停止或转人工。
- 不用可补偿总分：「句法自然 10 分」不能补「比较方向改错」。

## 致谢与许可

停止状态、来源锚点、候选而非覆盖、相对诊断、按页/按句豁免这些**执行层概念**，受 FYADR（`multi-zhangyang/fuck-your-ai-detection-rate`，AGPL-3.0）的架构启发；本仓库**未复制其任何源码、正则表或提示词**，全部按雷达 LaTeX 论文场景独立实现。FYADR 自己撤回句式配额与检测平台对标的记录，也被引作反向护栏的外部佐证。

范文对标默认绑定 Bu, Rao, Song, *IET RSN* 18(8):1351–1363, 2024（DOI `10.1049/rsn2.12574`）——该论文不包含在本仓库中，只使用其公开书目信息与结构层面的功能对标。

个人方法论沉淀，未设开源许可。
