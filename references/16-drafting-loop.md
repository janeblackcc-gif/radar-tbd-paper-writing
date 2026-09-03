# 16 · 写稿循环：门禁在动笔前和逐章写作中怎么用

> 这份文件回答的是「skill 只能改烂稿，还是能从第一天就管住写稿」。答案是后者，但前提是按这里的顺序做。配套：`scripts/run_gates.py --stage`、`gates/gates.json` 的 `stages` 键、`cards/section-rules/*.md` 的「动笔前」段。

## 一、与事后修稿的根本区别

事后修稿工具（FYADR 一类）的假设是：文章已经存在，任务是把它改得不像机器写的。本方法的假设相反：**烂稿的成本在写它的那一刻就付掉了**——挂不上因果链的段落、没进摘要的最强结果、四个词形的同一概念，写出来之后再修，每修一处都是一次引入事实错误的机会（11-naturalness §三）。所以门禁的第一用途不是修稿，是**在每一章写完的当天就告诉你它缺什么**，第二用途才是改稿轮的归因与冻结。

同一套门，两种用法，差别只在阶段档案：

| 阶段 | `--stage` | 跑哪些门 | 缺输入的硬门 | 全过判 |
|---|---|---|---|---|
| 骨架 | `skeleton` | `claim_ledger`（闭环表三列）、`term_variants`（术语表格式） | 跳过、不降级 | `STAGE_OK` |
| 逐章草稿 | `chapter` | `claim_ledger`、`hedge_budget`（下限只对已写章节）、`term_variants`、`jargon_scan`（源码侧）、`style_audit` | 跳过、不降级 | `STAGE_OK` |
| 冻结 / 改稿 | `freeze`（或不带 `--stage`） | 全部，含契约门 | 跳过即不得 `FROZEN_OK` | `FROZEN_OK` |

`STAGE_OK` 的含义是「这一章可以交样张了」，不是「这一章冻结了」。冻结只由 `freeze` 给出。

## 二、第 0 天：先配，再写

正文一个字没写之前，稿件目录里要有四样东西，它们是所有门禁的输入：

1. `paper.gates.json`——`sections`、`main`、`outline`、`glossary`、`roles`、`method_names`、`external_baselines` / `internal_baselines`（14 §七）。基线名在第 0 天就写进去：**摘要必须提基线**这条硬规则从此对每一版都生效，而不是等结果章写完才发现。
2. 大纲与逻辑链文件（01-skeleton）——含主张—证据闭环表三列。`claim_ledger` 在骨架阶段只看这张表：每行有证据钩子、样本量、边界。表填不满的那一行，就是实验还没设计好的那一条，**别开始写它对应的章节**。
3. 术语表四列（03-diction §四）——冻结词、外文、语境、避免用法。第四列写了，`term_variants` 从第一章起就拦误用；`concept_groups` 在第一次发现自己换词时补。
4. 禁用词文件（`scripts/banned-terms-template.txt` 复制后替换 B/C 节）——项目内部标识、流程方言。第一章写完跑 `jargon_scan` 就用它。

然后跑：

```bash
python scripts/run_gates.py --config paper.gates.json --stage skeleton
```

`STAGE_OK` 才动笔。这一步通常十几秒，省的是后面整轮结构返工。

## 三、逐章循环

```
读该章卡片的「动笔前」段 → 写这一章 → run_gates --stage chapter → 定点修（每 unit 一张卡片，≤2 次）
→ STAGE_OK → 编译该章样张（新文件名）→ 交付样张 + 改动说明 → 停，等回复 → 下一章
```

- **写前读卡片**：`cards/section-rules/<章>.md` 的「动笔前（写作契约）」段是这一章的必备项清单，来自 02-narrative；它和「允许改 / 禁止改」段共用一张卡片，写与改看的是同一份约束。
- **写的时候不看门禁**：门禁是写完跑的，不是边写边跑。边写边跑会把注意力从因果链拉到指标上，结果就是为指标写句子。
- **`chapter` 阶段的门只对已写章节生效**：`hedge_budget --floor-present-only` 只要求已存在的结果 / 结论章各有一句适用范围；`claim_ledger` 在结果章还没内容时跳过基线镜像，只查闭环表；`style_audit` 永远只出热区。
- **章节顺序**：按 09-mechanics §一，第一章是定调之作，先过第一章再写第二章；结果章写完当天就跑 `chapter`，最强结果没进摘要的问题在这一天暴露，而不是在导师那里。
- **样张交付**是硬停点（09-mechanics §一），门禁不替代它：叙事连贯、范文对标仍是人读。

## 四、从写稿切到改稿

全文各章都 `STAGE_OK` 之后：

1. 第一次编译全文 PDF，配置补 `pdf`；跑 `--stage freeze`。`page_fill`、`jargon_scan` 的 PDF 侧、`hedge_budget` 的 PDF 计数这时才第一次生效。
2. 提交这一版作为冻结基线，配置补 `base_rev`（提交号或标签）；从此每一处改动记 `edits/units.jsonl`，`change_ledger` / `semantic_diff` 开始工作。
3. 之后的每一轮改稿都是 12-edit-contract 与 14-routing-and-stop 描述的循环：诊断 → 一张卡片 → 改 → 重跑相关门 → 停止或转人工。

写稿阶段没有 `base_rev` 和账本是正常的——那时每一章都是新增，归因对象还不存在。**冻结那一刻是账本的起点。**

## 五、这套循环管不住的东西

- 因果链本身对不对：`claim_ledger` 查的是表填没填满，不查主张是否成立。
- 叙事是否连贯：逐章复述因果链、范文量表自比（05-calibration）仍是人做。
- 实验设计：08-experiment 的预承诺收窄规则在写大纲时执行，门禁只在闭环表层面看到它的结果。
- 英文译稿：翻译轮走 10-chinese §八，`semantic_diff --mode ze` 只查事实不查语气。

## 六、最小示例：一篇稿从零到冻结的命令序列

```bash
# 第 0 天
python scripts/run_gates.py --config paper.gates.json --stage skeleton
# 每写完一章
python scripts/run_gates.py --config paper.gates.json --stage chapter --report ch03_gates.md
# 全文写完、首次编译
python scripts/run_gates.py --config paper.gates.json --stage freeze --report r01_gates.md
# 冻结提交后，配置写入 base_rev；此后每轮改稿
python scripts/run_gates.py --config paper.gates.json --report r02_gates.md
```
