# 15 · 回归语料：每一次真实失败都变成一条用例

> 配套：`scripts/run_regressions.py`、`tests/make_fixtures.py`、`tests/fixtures/`、`tests/golden/`。门禁的校准规则见 [14-routing-and-stop.md](14-routing-and-stop.md) §二。

## 一、两层语料，边界不能混

| 层 | 位置 | 内容 | 入库 |
|---|---|---|---|
| 合成用例 | `tests/fixtures/<gate>/<case>/case.json` | 由 `tests/make_fixtures.py` 生成的最小 LaTeX / 大纲 / 术语表 / 账本片段，**不含任何真稿文字** | 是 |
| 真稿端到端 | `tests/golden/local_paths.json` + `tests/golden/local/` | 本地路径、历史快照导出、期望判定 | **否**（gitignored） |

真稿只能以路径引用，历史快照只能导出到 `tests/golden/local/hist/<rev>/`。任何含真稿句子的东西不进仓库——这是版权与保密边界，不是整洁问题。

## 二、合成用例 schema

```json
{
  "kind": "must_change | must_preserve | manual_review",
  "gate": "hedge_budget",
  "args": ["--config", "{dir}/paper.gates.json", "--no-pdf"],
  "expect_exit": 1,
  "expect_contains": ["下限", "conclusion"],
  "expect_not_contains": ["HARD_FAIL"],
  "synth_pgm": [{"fill": 1.0, "two_col": true}, {"fill": 0.4, "two_col": true}],
  "git_case": {"base": "base", "new": "new"}
}
```

- `kind` 只作分组显示，但它是写用例时的**第一问**：这条用例是要门禁拦住什么（must_change）、放过什么（must_preserve），还是只能转人工（manual_review）。
- `{dir}` 展开为用例目录；`git_case` 时展开为临时仓库（`base/` 提交为 HEAD，`new/` 覆盖工作区），跑完即删。
- `synth_pgm` 只给 `page_fill`：按 `fill` / `two_col` / `right_fill` 画合成灰度页，不依赖任何 PDF。
- 期望片段用脚本 PROOF 块里的原文（「超阈页：[2]」「摘要未提及」），不要用泛词「FAIL」——泛词让用例在脚本改输出格式时误绿。

## 三、真稿端到端 schema

```json
{"cases": [
  {"name": "paper1_final", "config": "C:/…/paper1.gates.json",
   "only": ["claim_ledger", "hedge_budget", "page_fill", "term_variants", "style_audit"], "expect_verdict": "REVIEW"},
  {"name": "paper1_hist_semdiff_49d22ff_to_bec818b", "script": "semantic_diff",
   "args": ["--config", "C:/…/paper1.gates.json", "--old-rev", "49d22ff", "--new-rev", "bec818b", "--quiet-pass"],
   "expect_exit": 1, "expect_contains": ["GT-ML-PDA", "00_abstract"]}
]}
```

- `config` 型：跑 `run_gates.py`，比四态判定；`only` 限定门，避免在改草稿上被无关的门（如没账本的 `change_ledger`）遮住要验证的那一条。
- `script` 型：直接跑单个门禁脚本，比退出码与片段；用于 git 历史回放（`--old-rev` / `--new-rev`）。
- 历史快照：`git archive <rev> sections_zh main_zh.tex draft_zh generated | tar -x -C tests/golden/local/hist/<rev>/`，再写一份指向该目录的配置。快照是只读语料，不是工作副本。

**真稿判定是快照。** 在改的草稿会变：另一位作者补了摘要、加了账本，`paper2_draft` 的期望就要从 TARGETED 改成别的。改期望时在提交说明里写明是稿件状态变了还是门禁变了——两者混在一起，回归就失去意义。

## 四、把一次真实失败变成用例的流程

1. **复现**：在真稿上跑出失败（或漏报），记下门禁 id、unit id、PROOF 原文。
2. **抽象**：用合成片段重写最小复现——保留触发结构（哪一章、哪种句式、哪列缺失），删掉一切真稿措辞与数字。
3. **先红**：加 `must_change` 用例，确认现门禁拦不住（或误拦）。
4. **改门禁**：让它红 / 让它绿。
5. **配对**：补一条 `must_preserve`，证明相邻的合法写法没被误伤（成对规则在测试层的形式）。
6. **真稿校准**：在定稿与草稿上各跑一遍，结果写进本文件 §八 的校准记录。
7. `run_regressions.py` 全绿后才动注册表的 `severity`。

漏掉第 5 步是最常见的错误：`claim_ledger` 第一版就是只做了 1–4，在定稿上误报 10 条。

## 五、真实历史语料（第一篇，r10 → r22）

第一篇 `sections_zh` 的六个提交构成一条现成的回归链。已经进 golden 的：

| 版本对 / 快照 | 事实 | 用例 | 门禁 |
|---|---|---|---|
| 快照 `f8836ab`（r10，导师认可的中文母稿） | 结果章已比较四类外部基线，摘要不提；结果章没有一句适用范围 | must_change ×2 | `claim_ledger` 基线镜像 HARD；`hedge_budget` 下限 HARD |
| 快照 `49d22ff`（方法章重写后） | 摘要仍不提基线（这个缺口从 r10 一直活到下一个提交） | must_change | `claim_ledger` HARD |
| `49d22ff → bec818b`（「emit baseline macros, state the baseline comparison in abstract」） | 摘要段新增 GT-ML-PDA / CFAR+GNN / GM-PHD / GM-CPHD 四个方法名、新增基线宏 | must_change（改动必须被列出） | `semantic_diff` 缩写 + 宏名 HARD |
| `915ffff → 2a04f86`（r12 新增算法框、槽位几何图、双输入流程图） | 只有新增段，无改动段 | must_preserve（纯新增永不判硬） | `semantic_diff` 只 REVIEW |
| `bec818b → 58959fe`（「inline algorithm parameters」） | 方法章内联 0.7 / 20 / 5 / 75 / 15 五个参数值 | must_change | `semantic_diff` 数值 HARD |
| `f8836ab → 915ffff`（r11 换低门限工作点 P_fa = 0.1） | 数字大面积变动；删去硬件型号缩写；新增 GM-PHD / GM-CPHD | 校准记录（未做 golden：变动太多，期望片段不稳定） | `semantic_diff` |

这些都是**门禁在事故发生之后才写出来**的。r10 那两条硬失败当时靠导师读出来（三次打回中的第二次），现在 0.3 秒。

## 六、A/B 协议：怎么判断这套东西有没有用

比较对象：同一份稿、同一轮意见，A = 按 SKILL 主线人工执行，B = 门禁 + 卡片路由。六个指标，全部从 `gate_report.json` 与 `edits/units.jsonl` 机器统计，不问感受：

| 指标 | 取法 | 方向 |
|---|---|---|
| 硬门违反数（交付时） | 交付版 `run_gates` 的 HARD_FAIL 计数 | 低 |
| 首轮未检出的 P0 | 导师 / 审稿意见里属硬门范围却在交付时为绿的条数 | 低；每条都要变成新用例 |
| 合格段被改比例 | 账本里 `decision=accept` 且改前该段无任何硬门失败、无高优先级热区的条数 / 总改动段 | 低（11-naturalness §三） |
| 每千字人工修改量 | 导师批注后人工再改的字符数 / 全文字数 | 低 |
| 每章冻结轮数 | 该章从第一次 TARGETED 到 FROZEN_OK 经过的 `round` 数 | 低 |
| 同段重复改写次数 | 账本里同一 `unit_id` 同一 `dimension` 的 `attempts` 最大值 | ≤ 2（停止规则 1） |

没有总分。任何一项变差都要单独解释，不能用别的项抵。

## 七、维护规则

- 改任何门禁脚本：前后各跑一次 `run_regressions.py`，两次都要全绿；新增行为必须带用例。
- 改 `gates.json` 阈值：在本文件 §八 更新校准记录，写明两篇真稿的前后数字。
- 删用例只允许一种理由：它测的行为已被更严格的用例覆盖；不允许因为「现在过不了」删。
- `tests/golden/local_paths.example.json` 与真实 `local_paths.json` 的字段保持同步，示例里只放假路径。

## 八、门禁校准记录（单一家：改阈值只更新这里）

新门或新阈值进注册表前，在两篇真稿上各跑一遍（14 §二）。记录按门排：

### claim_ledger

第一版在第一篇定稿上误报 10 条——闭环表里合法的「bootstrap 区间」「三臂消融」「评价合同」都不是图表引用；放宽证据钩子（接受统计与协议类钩子、中文数字「七类图」）、样本量缺失降 REVIEW、结论镜像降 REVIEW（定稿结论也不点名基线）之后才标 hard。

### hedge_budget

结果 + 结论各 1 句同一边界的两句簇是成对规则允许的镜像，静默放行；PDF 侧计数为准，摘要剥离；下限缺失为硬。

### page_fill

双栏识别从 4% 中缝改成 1.2% 且 ≥ 60% 正文行中缝空白后，两篇都判双栏；阈值 0.35。

### semantic_diff

第一版把段落拆分造成的数字「移动」判硬失败、把 `\Omega` 当数据宏；改成文件级核对并加非数据宏黑名单后，第二篇工作区对 HEAD 的硬失败从 27 段降到 24 段，剩下全是真改动（加引用、内联参数、数字入宏）。定位为词汇轮 / 自然度轮的门。

### term_variants

后缀词族启发式在定稿上列出 8 个词族（过门限 / 低门限本就是不同概念），降为纯信息；同义关系只认 `concept_groups`。「率条件初态」是 rate-conditioned 构造，不是「转弯率假设」的同义词。

### style_audit

新信号或新阈值进注册表前，在两篇真稿上跑一遍：已过审定稿不得出现高优先级热区堆积，在改草稿的已知问题段必须进热区。当前记录（2026-09-03，第一篇 r22 定稿 / 第二篇 v0.4 工作区）：

| 指标 | 第一篇（定稿） | 第二篇（草稿） |
|---|---|---|
| 段落数 | 87 | 75 |
| 句长均值 / CV | 40.8 / 0.62 | 38.1 / 0.53 |
| 连接词起句比 | 0.044 | 0.025 |
| 模板句 / 千字 | 0.0 | 0.08 |
| 图表空转起句 | 9 | 2 |
| 结果先行比 | 0.65 | 0.62 |
| 名词链段数（≥ 16 字） | 9 | 11 |
| 孤儿缩写 | 9（SNR、RMSE、GOSPA … 正文未在括号内展开） | 9 |
| 热区 / 高优先级 | 30 / 0 | 21 / 0 |

两处按定稿回调的阈值：`noun_chain` 从 12 字放宽到 16 字并把「但 / 且 / 使 / 若 / 经 …」加入断字（12 字时定稿 37/87 段命中，「通过成功判据但覆盖率略降」也算名词链）；`long_sentence` 从 90 字放宽到 110 字并先去掉括号内英文术语（定稿引言的「最大似然概率数据关联（maximum-likelihood probabilistic data association, ML-PDA）」一句 134 字，去括号后 90 字以内）。`--review-at` 取 3：两篇当前都是 0，留出两段的余量。

定稿的 9 处「图表空转起句」全部是结果章证据链的展示段（「图 X 在相同仿真条件下对比各算法的跟踪结果」），符合 `result-first-repair` 卡片的「展示段可保留」——它是信号不是错误，所以只作 severity 的一票。

### 环境

Windows 下 `pdftotext` 不带 `-enc UTF-8` 会静默丢掉全部中文（两篇实测抽出 0 个汉字）；早先归因为字体缺 ToUnicode 是错的。
