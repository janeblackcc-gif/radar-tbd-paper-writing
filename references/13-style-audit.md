# 13 · style_audit：软诊断的信号定义、热区语义与校准记录

> 配套：`scripts/style_audit.py`；职责与边界见 [11-naturalness.md](11-naturalness.md)；路由见 [14-routing-and-stop.md](14-routing-and-stop.md) §四。

## 一、它是什么、不是什么

`style_audit` 是第 4 层（表层自然度）的**唯一**机器手段，输出三样东西：文档级指标、段落热区、与上一版的指标差。它**不是**门：退出码永远是 0，除非注册表给了 `--review-at N` 且高优先级热区 ≥ N，那时退出 4（REVIEW_REQUIRED）。它永远不退出 1。

原因写在 11-naturalness §三：风格是相对的、可争议的，而且每次改写都是引入事实错误的机会。软热区只回答「先看哪几段」，不回答「合不合格」。

## 二、段落信号

每段可同时触发多项；`severity` = 触发信号数；**≥ 3 为高优先级热区**。阈值只在脚本顶部常量与 `gates.json` 里，不散落。

| 信号 | 定义 | 阈值 | 卡片 |
|---|---|---|---|
| `template_phrase` | 模板句 / 套话词典命中（值得注意的是、具有…意义、为…提供了…基础、近年来、受到广泛关注 …） | ≥ 1 | template-repair |
| `four_char_hype` | 四字格空评价（显著提升、大幅改善、充分验证、有效解决 …） | ≥ 1 | template-repair |
| `adverbial_padding` | 「××地 + 动词」 | ≥ 2 | template-repair |
| `connector_density` | 句首连接词 / 句数 | ≥ 50% 且 ≥ 3 句 | template-repair |
| `generic_closing` | 末句是泛化收束（奠定了基础、具有…意义、提供了…参考 …） | 命中 | template-repair |
| `noun_chain` | 无助词、连词、介词的连续汉字 | ≥ 16 字 | noun-chain-unpack |
| `triple_de` | 「…的…的…的」 | 命中 | noun-chain-unpack |
| `uniform_rhythm` | 句长变异系数 | < 0.20 且 ≥ 4 句 | syntax-rhythm |
| `long_sentence` | 单句长度（去掉括号内英文术语后） | > 110 字（英文 > 45 词） | syntax-rhythm |
| `paragraph_too_long` | 句数 | > 8 | syntax-rhythm |
| `repeated_opening` | 同一两字起句在段内出现次数 | ≥ 3 | syntax-rhythm |
| `passive_marker` | 含「被」的句子占比 | ≥ 50% 且 ≥ 2 句 | syntax-rhythm |
| `figure_first_opening` | 段首「图 X 给出 / 如图所示」 | 命中 | result-first-repair |
| `claim_far_from_evidence` | 结果章里含比较 / 断言线索的句子，本句与相邻句都没有图表、数字、区间、宏钩子 | ≥ 1 句 | result-first-repair |

词典全部自行整理（`TEMPLATE_ZH` / `TEMPLATE_EN` / `FOUR_CHAR` / `CONNECTOR_*` / `GENERIC_CLOSING`），来源是 03-diction §十四、10-chinese §十 与两篇真稿的实测；不来自任何外部仓库。

## 三、文档级指标

| 指标 | 含义 | 用途 |
|---|---|---|
| `sent_len_mean` / `sent_len_cv` | 句长均值与变异系数 | 与上一版比；CV 掉到 0.3 以下要警惕「改整齐了」 |
| `connector_ratio` | 连接词起句占比 | 反向护栏：升高即 AI 腔 |
| `template_per_1k` | 模板句每千字 | 目标接近 0 |
| `figure_first_opening_count` | 图表空转起句段数 | 结果章证据链展示段可豁免 |
| `result_first_ratio` | 结果章段首含结论或数字的段落占比 | 02-narrative §段首 |
| `noun_chain_paragraphs` | 含 ≥ 16 字名词链的段数 | 10-chinese §五 |
| `orphan_acronym_count` | 出现 ≥ 2 次却从未在括号里定义的缩写 | 10-chinese §二 缩写首现 |
| `term_first_use_no_cue` | 术语表冻结词首次使用处无定义线索（称为 / 记为 / 定义 / 即 / 外文名） | 03-diction §五 定义桥；需配置 `glossary` |
| `project_dialect_count` | `banned_terms` 模式在散文里的命中数 | 03-diction §十四 第一优先级；需配置 `banned_terms` |
| `uniform_paragraph_files` | 段长变异系数 < 0.25 的文件数（≥ 4 段） | 段落整齐度 |
| `hotspots` / `hotspots_high` | 有信号的段数 / severity ≥ 3 且未保护、未豁免的段数 | `--review-at` 用后者 |

`--json out.json` 落盘后，下一轮用 `--baseline out.json` 打印 `DELTA`。**只比方向，不设目标值**：模板句降、连接词不升、句长 CV 不降到 0.3 以下、`result_first_ratio` 不降，就是没改坏。

## 四、热区语义与处理

- 热区列表按 severity 排序，`--top N` 截断。每条给 unit id、角色、各信号的证据片段和段首 48 字。
- `protected_units` 里的段带「保护段，不改」标记，不计入 `hotspots_high`。
- `paper.exemptions.json` 的 `style_audit` 键按 `match` 子串豁免，同样不计入。
- 处理顺序：先高优先级、先结果章、再引言；每段只套一张卡片（14 §四 路由表），同段同维度 ≤ 2 次。
- **软不覆盖硬**：热区清零不能改变任何硬门判定；硬门失败时先修硬门，风格热区留到 TARGETED 解除之后。

## 五、校准记录

全部门禁的校准记录只记在 [15-regression-corpus.md](15-regression-corpus.md) §八（含 style_audit 两篇真稿的指标表与两处阈值回调）。

## 六、已知盲区

- 中文分句只认 。！？；：以顿号或逗号串起的超长句会被当一句，`long_sentence` 会高估。
- 名词链检测是字级启发式：术语表里的长复合词（「已知几何刚性编队」）会被算进去，遇到就写豁免而不是改术语。
- `orphan_acronym` 只认括号内定义；用「简称 / 记为」定义的缩写要靠 `defined_acronyms` 配置列出。
- 它读的是 `.tex` 散文（含图注），不读 PDF；图内文字的风格问题由页级目检负责。
