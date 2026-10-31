---
name: ppt-generate-toolkit
description: Method library for the PPT production expert. How to drive the ppt-master pipeline under a locked upstream spec, the page-type to generation mapping, editability hard rules and acceptance checks, image landings and labels, deviation log and generation report templates, the v6.7.3 contract snapshot, and handoff contracts. Load only the reference file the current stage needs.
---

# PPT 生成工具箱

这是「落版」的方法库。按当前阶段取用，**不要一次全读**。

## 何时读哪个

| 阶段 | 读这个 |
|---|---|
| 动手前：搞清怎么驱动 ppt-master、命令与门位 | `references/ppt-master调用契约.md` |
| 动手前：核对依赖、字体、模板路径是否就位 | `references/环境自检.md` |
| 画每页：某页型该怎么落成具体构造 | `references/页型到生成映射.md` |
| 画每页：文字、图表、表格、关系图的原生约束 | `references/可编辑性规范.md` |
| 处理图片：生成、申请、占位、打标签 | `references/图片落地规范.md` |
| 出偏差记录 | `references/偏差记录模板.md` |
| 交付：生成报告、可编辑性验收表 | `references/生成报告模板.md` |
| **交付验收：三个独立脚本都要跑** | `references/可编辑性规范.md`（§四 与 §四之二）｜`references/图片落地规范.md`（§零、§七） |
| 交给琢磨与总编排 | `references/交接契约.md` |
| ppt-master 升级后核对差异 | `references/契约快照.md` |

## 贯穿全流程的五条铁律

1. **你不产生新内容**。数字、结论、文案、视觉规范全是上游锁定的。你只负责把它们放到正确的位置。
2. **缺就说缺**。`{待补}` 占位是合法输出，"估一个看起来合理的数"是严重事故。缺口要进《缺口清单》。
3. **可编辑性优先于美观**。一页排得再漂亮，如果是整页截图，就是废页，必须返工。
4. **偏离要记账**。任何偏离 `design_spec` 的地方写全 `页码｜原蓝图｜实际做法｜级别｜原因｜影响`。不记账的偏离等于失控，而且会让琢磨把你的决定当成错误改回去。
5. **放行要过四性，缺一不可**：① 可编辑性（`check_editability.py`）② **内容可见性**（`check_content_visibility.py`：越界/溢出/碰撞）③ 事实准确性（数字与结论逐页对撞）④ **图片到位率**（`check_image_coverage.py`）。**每一条都独立，谁也替代不了谁**——
   - 可编辑性过了 ≠ 内容能看见（真实事故：「全页合格、图片覆盖 0%」的稿子里 多页内容在画布外、一页丢了整段文字）
   - 前两条都过了 ≠ 图文汇报（真实事故：58 页文旅汇报 **0 张图**，而清单里能自绘的图有 9 张没画）
6. **检查不过就停，不要糊**。同一问题 3 轮不解决就交给人。删页、并页、抽图表、贴图降级——这四种"过检查"的手段一律禁止，它们是作弊不是修复。

## 可调用的外部能力

- **ppt-master**（本机，v6.7.3，MIT）是执行引擎。它的默认链是：接料 → 建项目 → 模板候选 → **两段确认** → 图片获取 → 逐页画 → 质量门 → 导出。
- **ImageGen** 用于生成意向图与装饰图（须打标签，不得承载信息）。
- 上游产物：立象 `design_spec`、淬言润色稿、验筹事实包。读它们，不改它们。

## 一句提醒

ppt-master 是通用引擎，它不知道自己接的是一个已经定稿的项目。**你的任务之一就是不让它重新发明这个项目。** 凡是它想"重新规划""重新确认受众与意图"的地方，用上游的锁定输入把它按回去。
