---
name: ppt-refine-toolkit
description: "Visual refinement toolkit for converging a first-draft PPTX into a deliverable deck. Use when fixing objective page defects, aligning deck-wide consistency across many pages, strengthening expression on the agreed key pages, laying out image pages the user added manually, or re-verifying full editability before final delivery. Contains the rule execution manual, the added-page intake guide, the L1/L2/L3 change approval matrix, the iteration-and-rollback protocol, a deck-consistency checker and an editability checker."
---

# PPT 精修工具箱

## 这个工具箱解决什么

45 页以上的方案稿，**「不专业」几乎从不是某一页难看，而是全篇不一致**：字号用了 7 种、页码在第 3 页和第 30 页差 4px、同类页的元素一个靠左一个居中、配色越出令牌。这些东西单看每一页都挑不出毛病，合起来就是廉价感。

反过来，**精修最常犯的错也在这里**：为了修一处小毛病，改出十处新问题；为了让一页好看，破了全篇规则。

所以这个工具箱的重心不是「怎么改得更好看」，而是三件事：

1. **怎么判断哪些该改**（客观规则，不靠手感）
2. **怎么保证改了不坏**（分级审批 + 回滚）
3. **怎么证明改完还能用**（可编辑性 + 一致性双复验）

---

## 一、三层结构

| 层 | 内容 | 载体 |
|---|---|---|
| **规则层** | 客观缺陷的判定标准 | 直接执行 ppt-master 的 `visual-review` 规则，**不重写** |
| **扩展层** | 规则不覆盖的两类问题：跨页一致性、表达强化 | `视觉规则执行手册.md` |
| **机制层** | 改动怎么审批、怎么回滚、怎么验收 | `改动分级与审批.md` · `迭代与回滚.md` · 两个检查脚本 |

**关键原则：规则层不重叠。** 规则里已有的，不发明替代判据。重叠的判据会互相打架，用户不知道该信谁。

---

## 二、目录

```
references/
  视觉规则执行手册.md      ← 操作主线，每次都读
  新增页接手指南.md         ← 段二必读
  改动分级与审批.md         ← 动 L2 之前读
  迭代与回滚.md             ← 一页修不动时读
  精修报告模板.md           ← 写报告时读
  交接契约.md               ← 接料/退货/交付
  契约快照.md               ← ppt-master 升级时比对
scripts/
  check_editability.py      ← 单页可编辑性（与落版同一套判据）
  check_deck_consistency.py ← 跨页一致性
```

---

## 三、两个脚本的分工

| 脚本 | 查什么 | 查不出什么 |
|---|---|---|
| `check_editability.py` | 逐页：文本对象数、原生图表/表格、图片覆盖、**整页位图判定** | 全篇一致性问题 |
| `check_deck_consistency.py` | 全篇：字号使用清单与越阶、颜色使用与越令牌、页码/页眉页脚位置漂移、页面尺寸不统一、页型分布异常 | 单页内的排版质量 |

**两个都要跑，缺一不可。** 前者管「改不动」，后者管「看起来不专业」。

```bash
# 单页可编辑性（对落版基线复验）
python scripts/check_editability.py "<定稿.pptx>"

# 跨页一致性（可用 design_spec 里的令牌做基准）
python scripts/check_deck_consistency.py "<定稿.pptx>"
python scripts/check_deck_consistency.py "<定稿.pptx>" --tokens tokens.json
```

两个脚本都会输出人类可读的表格 + 同目录的 `.json` 明细，退出码非 0 表示有不合格项。

### `tokens.json` 怎么来

从 `design_spec` 的令牌段抄成一份 JSON，让脚本能判断「越令牌」而不是只看「用了多少种颜色」：

```json
{
  "font_sizes": [12, 14, 16, 20, 24, 32, 44, 64],
  "colors": ["#1F2A2E", "#2F5D62", "#C8A46A", "#F5F1E8", "#6E7681"],
  "canvas": {"width_emu": 12192000, "height_emu": 6858000}
}
```

没有 `tokens.json` 时，脚本只做「使用频次统计 + 异常项提示」，不做越界判定——**它是检查工具，不是裁判**。

---

## 四、执行顺序（固定）

```
① 接料体检          → 报一句话结论（缺什么、能不能开工）
② 出精修范围确认单  → 重点页建议 + 一致性项 + 问「要不要加减 / 有没有你的清单」
③ 段一：全篇机械校验 → 跑两个脚本 → 修 L1 → 记账
④ 段一：重点页表达强化 → 出 L2 前后对比 → 用户点头 → 改
⑤ 段一收口：重新导出 → 复跑两个脚本 → 与基线对比
⑥ 段二：用户手工加页贴图 → 接手体检 → 判页型套版式 → 出前后对比 → 用户确认
⑦ 终检：两个脚本全绿 → 出六件交付物 + 终稿回执
```

**③ 和 ④ 的顺序不能反。** 先修机械问题再加表达——反过来会把刚强化的构图又改回去。

---

## 五、硬约束（写死，不可协商）

1. **不重做。** 已获用户确认的结构改动是前提，不是待纠正项
2. **不发明判据。** 规则层只用 ppt-master 的 rubric
3. **不改文案、不改数字、不改结论。** 发现问题是提出来，不是自己改
4. **整页截图 = 不合格。** 任何一页出现，直接返工
5. **默认不加动效。** 加只加 fade，加完复验
6. **一页最多 2 轮。** 第 3 轮要用户明确说继续
7. **交不出六件不算交付**

---

## 六、依赖

- `python-pptx`（读 pptx 结构、append 新页、原生绘制）
- `playwright` + chromium（渲染 PNG，做视觉复核与前后对比）
  - **不要用 cairosvg**：它没有字体回退链，中文会渲染成方块，看起来像全篇崩了
- `Pillow`（PNG 比对、对比图拼版）
- ppt-master 技能（`~/.workbuddy/skills/ppt-master`）：`visual_review.py`、`svg_quality_checker.py`、`svg_to_pptx.py`、`verify-charts` 阶段

环境自检脚本思路：**能 import、能渲染一张中文 PNG、能读回它**，三步全过才算就绪。只 import 成功不算——字体没装照样 import 得通，渲染出来全是方块。
