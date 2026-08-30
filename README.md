# radar-tbd-paper-writing

一个 Claude Code / Claude Agent Skill：雷达检测前跟踪（TBD）、群目标与编队跟踪方向的**期刊论文写作方法**，中文母稿优先。

沉淀自一篇 IET RSN 投稿从「读不下去」到定稿的完整改稿周期——25 天、22 个渲染版本、三次被打回。每条规则都有真实失败作依据，不是风格偏好。

## 为什么需要它

同一份稿子被否决三次，每次都是不同的缺陷层：

| 轮次 | 判词 | 缺陷层 | 当时状态 |
|---|---|---|---|
| 1 | 「极其糟糕、读起来意义不明的黑话」 | 词汇层 | 读第一章即停 |
| 2 | 「臃肿、重点不突出、逻辑不通顺、非常跳跃」 | 结构层 | 数字、claim、术语、统计口径**全部检查通过** |
| 3 | 「major revisions」（70 条批注） | 词汇层又犯 | 结构已重构完成 |

三条推论构成本 skill 的组织基础：

1. **科学正确 ≠ 写作合格**。写作质量是独立的验收维度。
2. **结构与词汇必须分两轮治理，先结构后词汇。** 混在一轮里改，两层都治不干净。
3. **结构治好不代表词汇合格。** 骨架重构完必须单开一轮只做词汇清洗。

## 安装

复制到 Claude Code 的 skills 目录即可：

```bash
git clone <this-repo> ~/.claude/skills/radar-tbd-paper-writing
```

Claude Code 会自动发现它。之后任务涉及「写论文 / 改稿 / 审稿 / 术语统一 / 行文不像期刊论文 / 去 AI 味」时会被触发，也可以显式调用。

## 结构

```
SKILL.md                  主线：三层缺陷模型 → 四层工作流 → 成对规则 → 反向护栏
references/
  01-skeleton.md           骨架层：大纲与逻辑链文件、主张—证据闭环表
  02-narrative.md          结构层：摘要/引言/相关工作/方法/结果/结论逐章写法
  03-diction.md            词汇层：禁用词表、正名表、新词三关、定义桥、双范围清零
  04-hedging.md            防御性表述：定量预算、删除两问、三段式重写、成对规则
  05-calibration.md        范文对标：可参考层 vs 不可继承层、量化自比量表
  06-evidence.md           证据治理：数字宏机制、图面事实核对、同种子图证链
  07-code-consistency.md   论文↔代码：追生产调用链、伪代码逐行核实现
  08-experiment.md         实验设计：预承诺收窄规则、指标矩阵、统计措辞
  09-mechanics.md          改稿流程：逐章硬停点、三列对照单、页级目检、阶段硬门
  10-chinese.md            中文特有：量词歧义、中英混排、伪代码语言、翻译轮
scripts/
  macro_diff.py            论文数字宏的零变化三重校验
  page_delta.py            逐页字符数 delta 归因（必要条件检查）
  jargon_scan.py           禁用词双范围扫描（源码 + PDF 渲染文本）
  banned-terms-template.txt 禁用词模式模板（三节：通用/项目专属/中文造词）
```

主线通用；中文特有条目单列在 `10-chinese.md` 并标注适用语言，不为了通用而删掉。

## 脚本

```bash
# 宏零变化三重校验 → MISSING/CHANGED/ADDED + VERDICT
python scripts/macro_diff.py <old.tex> <new.tex> [--expect-added N] [--strict]

# 逐页字符数 delta + 归因残差
python scripts/page_delta.py <base.pdf> <new.pdf> --strip-ws -a abstract=+40 -a "sec 5.3=+123"

# 禁用词双范围扫描
python scripts/jargon_scan.py --patterns scripts/banned-terms-template.txt \
    --tex sections_zh --exclude-env algorithmic --pdf dist/final.pdf
```

依赖：Python 3.9+，`page_delta.py` 与 `jargon_scan.py` 需要 `pdftotext`（poppler / xpdf）在 PATH 上。

三个脚本都在来源仓库的真实产物上验证过历史基准：`macro_diff` 复现「69→105 宏、`MISSING[] CHANGED[] ADDED 36`、PASS」；`page_delta` 复现「20 页、total +163、residual +0」；`jargon_scan` 在定稿源码上零残留，并在 PDF 侧抓出一处源码 `grep` 不到的图内轴标签。

另有 18 项加固回归测试覆盖这些边界：被注释掉的宏、解析出 0 个宏、同名重复 `\newcommand`、裸写 / `\providecommand` / 可选参数默认值、空扫描范围、不配平的 `\begin`。

## 两条设计取向

**成对规则。** 每一条禁止夸大的规则，旁边必须配一条禁止自我削弱的规则。上一代的写作框架把「不要过度声称」写成单向硬规则、没有配平衡条款，直接催生了「本稿有意不报告任何性能主张」这样的摘要——规则会被单向执行到自我否定。

**工具边界不得静默决定论文声称什么。** 「实验数字只走生成宏、禁止手抄」是对的纪律，但当生成器只输出本方法的数字时，正文在该纪律下会**结构性地写不出**与基线的对比，最强结果只能活在一张图里。发现「这句话写不出来」时，先判断是不是工具缺陷。

## 范围

默认目标期刊为 IET Radar Sonar & Navigation 一类的传统雷达工程期刊。若换到 ML 会议，`SKILL.md` 第六节的反向护栏列出了会产生反效果的三条规则（连接词密度、结果段问句、「不是 X 而是 Y」的批量清洗），按目标期刊口味调整。

范文对标默认绑定 Bu, Rao, Song, *IET RSN* 18(8):1351–1363, 2024（DOI `10.1049/rsn2.12574`）——同刊同题材。该论文本身不包含在本仓库中，只使用其公开书目信息与结构层面的功能对标。

## 许可

个人方法论沉淀，未设开源许可。
