# 落版 · PPT 生成与初稿制作专家

把上游锁定的设计规范和润好的文案，落成一份**原生可编辑、结构正确、无事实错误**的 PPT 初稿。

## 类型

Agent 型（单个 AI 专家）· maxTurns 80 · `06-ContentCreative`

## 在专家组中的位置

```
筑策(策划定位) → 验筹(商业审查) → 析纲(出框架) → 淬言(去AI味) → 立象(视觉规范) → ⑥ 落版(生成初稿) → 琢磨(精修定稿) → 总编排
```

## 功能

**1. 有约束地驱动 ppt-master**
本机装了 ppt-master（v6.7.3），但它是通用引擎，会按自己的流程重新追问受众和意图——而这些问题上游早已答过。落版的做法是走它的 Default 路线，把 `design_spec` 当"已定稿"喂进去：Strategist 只许补图片任务和逐页清单，**不许改视觉身份、不许改结论、不许重新发问**，同时保留 spec_lock 与五页复读机制，保证 45 页不走形。

**2. 三条锁**
内容锁（页序、结论、文案）、视觉锁（配色、字号、页型）、事实锁（数字、口径、黑名单）。落版不产生新内容，只把已有的内容放到位。这是它和"一般 AI 做 PPT"最大的区别。

**3. 可编辑性硬纪律**
文字原生不转曲、图表原生可改数、表格原生、关系图用原生形状拼、图片不承载文字。**任何一页出现整页截图直接判不合格返工。** 附一个自带的检查脚本，逐页统计文本对象/原生图表/原生表格/图片覆盖，把可疑页标出来——45 页靠眼睛扫一定漏。

**4. 缺就说缺**
缺数字留 `{待补}` 占位并进缺口清单，绝不估一个看起来合理的数；缺整页内容排空版不删页；文案与页型不合只能调结构，换主页型/拆页/并页必须先给用户看预览。

**5. 偏差记录**
微调自己定、结构先问、身份一律不许。每处偏离记全 `页码｜原蓝图｜实际做法｜级别｜原因｜影响`。没有这份记录，下一棒「琢磨」会把你批准过的改动当成错误改回去。

**6. 分批与 split**
前 5 页（覆盖主力页型）是关键关卡，之后每批 8–10 页。页数多时默认 split：规划与执行分两个会话跑，避免 45 页塞一个上下文导致后期掉质量。

## 使用示例

- 这是立象的 design_spec 和淬言的润色稿，帮我生成 PPT 初稿，先出前 5 页给我确认。
- 这份方案有 45 页，先按章分批生成，每批 8 到 10 页，出完一批我看一批。
- 检查一下这份初稿的可编辑性，哪些页是整页截图或者图表改不了数的，列出来。

## 交付物

pptx（原生可编辑）｜生成报告｜偏差记录｜可编辑性验收表｜已知薄弱页清单｜给总编排的流程回执

## 目录结构

```
ppt-producer/
├── agents/ppt-producer.md              角色、三条锁、工作流、纪律
├── skills/ppt-generate-toolkit/
│   ├── SKILL.md                        取用索引与五条铁律
│   ├── scripts/check_editability.py    可编辑性逐页检查（带实测）
│   └── references/
│       ├── ppt-master调用契约.md        加载顺序、七步命令、门位、禁止项
│       ├── 环境自检.md                  依赖/字体/路径/Windows 注意
│       ├── 页型到生成映射.md            15 种页型的原生构造与翻车点
│       ├── 可编辑性规范.md              五条硬约束 + 验收表 + 自动检查
│       ├── 图片落地规范.md              五级标签、生成纪律、占位与合规
│       ├── 偏差记录模板.md              三级判定、写法要求、方法级偏差
│       ├── 生成报告模板.md              报告 / 缺口清单 / 验收表 / 流程回执
│       ├── 交接契约.md                  接谁的料、交什么、何时退回、何时拒开工
│       └── 契约快照.md                  v6.7.3 依赖面与升级比对法
├── checklist.md                        交付前自检
└── avatars/expert.png
```

## 前置依赖

`python-pptx` `XlsxWriter` `skia-pathops` `uharfbuzz` `Pillow` `numpy` `PyYAML` `flask`

```bash
python -m pip install python-pptx XlsxWriter skia-pathops uharfbuzz Pillow numpy PyYAML flask
```

字体已确认可用：微软雅黑 / 黑体 / 宋体 / 思源黑体 / 阿里巴巴普惠体 / Noto Sans SC。

## 头像

`avatars/expert.png`，512×512、< 500KB。

## 安装

放在专家目录下并注册：

```bash
python3 scripts/register_expert.py "C:\Users\PC\.workbuddy\plugins\marketplaces\my-experts\plugins\ppt-producer"
```

## 打包分享

```bash
python3 scripts/package_expert.py "C:\Users\PC\.workbuddy\plugins\marketplaces\my-experts\plugins\ppt-producer"
```
