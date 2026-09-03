# 卡片 · 防御性表述平衡

**触发**：`hedge_over_budget`、`hedge_position`、`hedge_duplicate`（hedge_budget）；`claim_dangling`、`claim_no_boundary`（claim_ledger）。

## 先做两问（04-hedging §三）
1. 删掉这句，读者会不会把结论外推到未验证的范围？
2. 这个边界在全稿是否只在此处出现一次？
两问都「是」→ 必留，写豁免（带标签）；否则进入下面的处理。

## 允许改
- 合并同一边界的重复陈述，保留主张处 1 次 + 结论呼应 1 次。
- 把引言/相关工作里的防御句删除或改写成中性的适用性判据。
- 把「不能证明 A、不表示 B、也不应解释为 C」的排比压成一句真实边界。
- 闭环表：补证据钩子（图/表/区间/消融/协议）、样本量、封口句。

## 禁止改
- 带豁免标签的句子（`statistical_boundary` `baseline_identity` `information_contract` `model_assumption` `evaluation_condition` `submission_compliance` `evaluator_disclosure` `pointwise_declaration`）。
- 摘要里的边界句（摘要不计入额度）。
- 用删边界的方式凑上限——上限超了先找重复，不找唯一。

## 必保留
- 结果与结论各 ≥ 1 句适用范围（下限）。
- claim 强度改动同步到摘要 · 引言 · 结果 · 结论 · 图注（04-hedging §十四）。

## 自检与停止
- `hedge_budget` 转绿；`claim_ledger` 无 HARD_FAIL。
- 每删一句在 `edits/units.jsonl` 记 reason_code 与两问答案。
- 同一 unit 最多 2 次；第二次仍超 → 问题在闭环表的边界列写得太散，回骨架层。
