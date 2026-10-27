---
name: visual-design-toolkit
description: Method library for the visual expression designer. Design tokens, page-type library, per-page layout blueprint template, chart and image rules, style extraction with template library, SVG sample conventions, ppt-master contract snapshot, and handoff contracts. Load the specific reference file needed for the current stage.
---

# 视觉设计工具箱

这是「立象」的方法库。按当前阶段取用，不要一次全读。

## 何时读哪个

| 阶段 | 读这个 |
|---|---|
| 定视觉风格来源、出候选方向 | `references/设计令牌规范.md` |
| 建页型库、判定某页该用什么页型 | `references/页型库.md` |
| 写逐页蓝图 | `references/逐页蓝图模板.md` |
| 定图表怎么画、图片怎么标 | `references/图表与图元规范.md` |
| 用户给了参考文件或样本文件夹 | `references/风格提取与模板库.md` |
| 出 SVG 样张 | `references/样张产出规范.md` |
| 写 design_spec、对接 ppt-master | `references/契约快照.md` |
| 交付给上下游 | `references/交接契约.md` |

## 贯穿全流程的三条铁律

1. **禁止形容词**。"大气、简洁、高级、灵动、呼吸感、层次分明、视觉冲击力"——这些词必须翻译成色值、尺寸、比例、数量、位置。翻译不了的，说明你自己也没想清楚。
2. **每个参数都要有理由**。不是"我选了 #C8A46A"，而是"辅色选 #C8A46A，因为它与主色 #1F3A34 的明度差足够承载强调，同时比正红更克制，适合政府评审场合"。
3. **破例必须记账**。任何破掉默认规则的地方，写一句"此处破例：因为 X，代价是 Y"。不记账的破例等于失控。

## 可调用的外部能力

- **ppt-master** 是本机已装的 PPT 生成技能，你的 `design_spec` 要与它的契约对齐。它同时提供 33 种图表模板、6 种表格模板、12,027 个图标——**图元直接复用，不要自己从零画**。
- 需要出样张时可写 SVG 文件；需要预览图时转 PNG。

## 表达型优先（v1.3 新增，这条排在最前面）

**先定表达型，再动令牌。** 顺序颠倒的代价是：令牌做得再精确，出来的页面仍然"平"。

九种表达型：E1 结论冲击 / E2 现场图主导 / E3 图文并置 / E4 数据主导 / E5 关系图 / E6 对照矩阵 / E7 时间轴 / E8 清单索引 / E9 氛围过渡。

每页必须归入之一，含图文配比。**判不出来 = 这页有两个核心 = 拆页。**

选型依据是**内容性质**（判断型 / 事实型·现场 / 事实型·数据 / 关系型 / 对照型 / 过程型 / 清单型 / 场景型）。详见 `references/表达型库与决策树.md`。
