# ppt-master 调用契约

这是落版和 ppt-master 之间的操作约定。依据版本 **v6.7.3**。**不要凭记忆调脚本，按这里的顺序和命令走。**

## 一、加载顺序（不可跳步）

```
1. Read  <SKILL_DIR>/SKILL.md
2. 运行  python <SKILL_DIR>/scripts/attribution_guard.py     # 非零则立即停止，不要检查、修复或绕过
3. Read  <SKILL_DIR>/workflows/routing.md
4. 选定唯一顶层路线 → 读它的 runtime authority
5. 只读该路线显式触发的支撑文档
```

`<SKILL_DIR>` = `~/.workbuddy/skills/ppt-master`（宿主机实际路径；每次调用都在当次工具调用内展开，**不要 cd、不要依赖 CWD、不要搜索猜路径**）。

Windows 上若 `python3` 是 WindowsApps 存根（退出码 9009 且无输出），**改用 `python`**——那不是守卫结果，别误判成校验失败。

## 二、路线选择

本专家**只用一条路线：Generate PPTX 的 Default 档**（`workflows/generate-pptx.md`）。

| 路线 | 用不用 | 原因 |
|---|---|---|
| Generate — Default | ✅ 唯一选择 | 有 spec + lock + 质量门，长稿一致性靠它 |
| Generate — Quick | ❌ | 跳过 spec/lock，45 页必然散；这是省两层门换来的假快 |
| Generate — Image to PPTX | ❌ | 我们是"有规范做页"，不是"照像素复刻" |
| Generate — Beautify | ❌ | 那是"保原文改外观"，与我们的从规范生成不同 |
| Create Template | ❌（本环节） | 模板由立象产出，本环节只消费 |
| Edit Native PPTX | ❌（本环节） | 初稿不存在，没有可编辑的原生稿 |

**硬规则**：选定后不加载其他顶层路线的流程。不同路线互斥，混用会把门位搞乱。

## 三、七个步骤与命令

所有命令以 `<SKILL_DIR>` 和 `<project_path>` 为参数，**一次一条，串行执行**，当前条成功再走下一条。

### Step 1 接料
```bash
python <SKILL_DIR>/scripts/source_to_md.py <文件或目录...>
```
上游给的是 Markdown（立象 spec、淬言稿、验筹事实包）时**直接读，不要转换**。转换是给 pdf/docx/xlsx/pptx 用的。

### Step 2 建项目
```bash
python <SKILL_DIR>/scripts/project_manager.py init <project_name>
python <SKILL_DIR>/scripts/project_manager.py import-sources <project_path> <文件或目录...>
```
- 画布格式：**只在用户/上游已明确画布规格时**才加 `--format <registered_format>`；否则留给第 2 段确认。
- `import-sources` 退出码 0 表示"至少有一个成功"，**必须读它打印的 `skipped` 原因**，把被跳过的当"不存在"处理。

### Step 3 模板候选（内部准备，不交互）
读四个索引拿候选，不做选择、不安装、不弹窗。
**我们的纪律覆盖它**：本项目有立象产出的 Style 模板 → 直接指定它为唯一候选；立象交付"自由设计" → `free_design`；**禁止从历史库里主动推荐别的样式**。

### Step 4 Strategist（本环节风险最高的一步）
```bash
# 读规划核心
Read <SKILL_DIR>/references/strategist.md
Read <SKILL_DIR>/references/plan-core.md
Read <SKILL_DIR>/references/canvas-formats.md

# 确认服务
python <SKILL_DIR>/scripts/confirm_ui/server.py <project_path> --daemon
python <SKILL_DIR>/scripts/confirm_ui/server.py <project_path> --wait-only --wait-stage stage1
python <SKILL_DIR>/scripts/confirm_ui/server.py <project_path> --wait-only
python <SKILL_DIR>/scripts/confirm_ui/server.py <project_path> --shutdown
```

**在 Default 链里，这一步是强制的，但它的输出边界被你约束：**

| Strategist 想干的事 | 允许吗 |
|---|---|
| 补 §VIII 图片资源任务、补 §IX 逐页清单 | ✅ 必须做 |
| 定生产机制（备注、动画、旁白开关） | ✅ 允许 |
| 改配色角色、字号阶梯、页型定义 | ❌ 视觉锁，退回立象 |
| 改页面结论、要点、页序、页数 | ❌ 内容锁，退回析纲 |
| 因模板候选而"顺手调一下方向" | ❌ 模板不重写目标 |
| 重新追问受众、意图、成果、核心信息 | ❌ 已确认过，直接取 `design_spec §I` |

**两段确认 → 合并成一张确认单**（见 agent 第 2 段）。由你预填、用户签一次。**只有用户能确认**——你不代签、不自动化提交、不合成 payload、不写用户结果状态。

⚠️ 如果用户选择在聊天里确认（chat 分支），就**不要再起 UI**，整轮在对话里跑完。

**Design Spec 与 lock**
```bash
Read <SKILL_DIR>/templates/design_spec_reference.md
Read <SKILL_DIR>/templates/spec_lock_reference.md
python <SKILL_DIR>/scripts/project_manager.py validate <project_path>
```
- `design_spec.md` 的 §I–§X 一次写全，不留占位、不留 `scaffold-*`
- **Gate 1**：逐字段对照已确认值审计
- `spec_lock.md` 从 spec 派生：身份、每个重复出现的字体角色、路由锚点、每张图的来源与裁切策略。**lock 里不放页级装饰细节**
- **Gate 2**：lock 锚点与 spec 对齐 + `validate` 通过
- schema 合法 ≠ 保真：spec 与确认值不符、lock 与 spec 不符、有未应用的修订，**都算阻塞**

可选：用户要求细看 spec 时跑 `refine-spec` 阶段，在 Gate 1 之后、lock 之前。

### Step 5 图片获取（有条件触发）
```bash
Read <SKILL_DIR>/references/image-base.md
python <SKILL_DIR>/scripts/image_gen.py ...        # AI 生成
python <SKILL_DIR>/scripts/image_search.py ...     # 网络检索
python <SKILL_DIR>/scripts/image_treat.py ...      # 派生（模糊/去色/双色调/缩放）
python <SKILL_DIR>/scripts/slice_images.py ...     # 从大图切分
python <SKILL_DIR>/scripts/analyze_images.py <project_path>/images
```
触发条件：§VIII 里存在 `ai` / `web` / `slice` 行，或有待生成的派生件。
**我们的过滤规则（覆盖默认行为）**：
- 该由甲方提供的实景、该由设计单位出的效果图 → **不生成、不检索**，直接 `placeholder` + 进缺口清单
- 意向图 → `ai`，prompt 由你按页面内容写，风格词与 design_spec 一致
- 装饰图 → `ai`，不得承载数据或空间主张
- `web` 检索到的图**不能当"本项目实景"**；确需用作氛围参考时，标签必须是"意向图"

**出口门**：所有行必须到达终态（无 `Pending` / `Failed` / `Needs-Selection`）。自动路径都失败时，问用户：修好重试 / 手动生成 / 取消这几张并改方案——**不静默进离线手动**。

### Step 6 逐页画（Executor）
```bash
Read <SKILL_DIR>/references/executor-base.md
Read <SKILL_DIR>/references/shared-standards-core.md
Read <SKILL_DIR>/references/semantic-svg.md
Read <SKILL_DIR>/references/preset-shape-vocabulary.md
Read <SKILL_DIR>/references/modes/<resolved-id>.md
Read <SKILL_DIR>/references/visual-styles/<resolved-id>.md
# 按 executor-base 的路由表读被触发的模块
```

**开工前两件必做**：
```bash
python <SKILL_DIR>/scripts/text_measure.py calibrate <project_path> --outline
python <SKILL_DIR>/scripts/svg_editor/server.py <project_path> --live --daemon
```
- 前者产出逐角色字宽标定（CJK / Latin 每百像素字数 + 最长计划行），**后面每页都按这套算术估，不要靠眼估**
- 后者是实时预览（默认从 6060 起找空端口，`--port N` 严格绑定），**先报出 URL 再画第一页**；起不来就明说，不静默继续

**画页纪律**
- `design_spec §IX` 是**有序队列**：一条一个最终页，id 与顺序不变。**不增、不删、不并、不拆、不重排**
- 每页的可见元素必须全在这页的 SVG 里（Chart/Table 以 JSON 为准的除外）
- **节奏（强制）**：P01–P05 → 早期门 → 其余页 → 最终门。不逐页跑检查
- **五页复读**：P05、P10、P15… 之后，下一頁开始前**整读一次 `spec_lock.md`**，纯重锚定配色、字体、图标风格、页面节奏；不跑检查、不输出、不停顿
- 长上下文失效时按"重新读 spec → lock → 触发的参考 → 最新完成的页"恢复

**早期门（第 5 页后，页数 ≤6 则跳过）**
```bash
python <SKILL_DIR>/scripts/svg_quality_checker.py <project_path> --canonical-authoring --stage early --json
```
- `--json` 把报告写到 `validation/svg_quality_early_report.json`；**stdout 是人类摘要，永远不要当 JSON 解析**
- 修之前先判性质：同一类问题出现两处及以上，或落在全篇重复的写法上（段落构造、页眉、卡片框）→ **是方法级偏差，先改规则再继续**；孤立单页问题 → 就地修
- 输出截断时只从报告 JSON 里取 `categories.blocking.issues`

**最终门（全部页画完，在备注与标注之前）**
```bash
python <SKILL_DIR>/scripts/svg_quality_checker.py <project_path> --canonical-authoring --stage final --json
```
- 导出器要求存在匹配的 `final` 报告；缺、非 final、阻塞、过期、不可验证 → **拒绝导出**
- 成功时只看退出码与终端摘要；**不要把整份 JSON cat 进上下文**

**有图表页**：Step 7 之前跑 `verify-charts` 阶段标定坐标。

### Step 6.5 演讲备注（开启时）
```bash
Read <SKILL_DIR>/references/executor-notes.md
```
把淬言的备注落到 `notes/total.md`，**逐页覆盖、只写不改**。关闭时不读、不建。

### Step 7 后处理与导出
```bash
python <SKILL_DIR>/scripts/total_md_split.py <project_path>     # 7.1 备注切分（开启时）
python <SKILL_DIR>/scripts/finalize_svg.py <project_path>       # 7.2 自包含预览
python <SKILL_DIR>/scripts/svg_to_pptx.py <project_path> [--no-notes] [--native-charts-and-tables] [--image-sizing display]
```
- 备注开启 → 不加 `--no-notes`；关闭 → 必须加
- 用户明确要"图表可改数"或页型里有 chart/table 槽位 → 加 `--native-charts-and-tables`
- 最终门报图片超尺寸 → 加 `--image-sizing display`
- **严格串行**：一次一条命令，前一条成功且验收标准成立，才进下一条
- 成功判据：退出 0，产出 `exports/<project_name>_<timestamp>.pptx` 与 `validation/<project_name>_<timestamp>.report.json`，状态为 `passed` 或 `passed-with-warnings`
- 读 `[POSTFLIGHT]` 回执（状态、质量门、页数、警告数、路径）；**实质性警告要告知用户**

**图片就绪门**：任何行是 `Needs-Manual` 时，第一条 Step 7 命令前必须确认文件与切片都在 `images/` 下。缺就停下、点名缺哪些文件，**绝不运行导出脚本、绝不带着虚线占位框交付**。

## 四、split 模式（默认启用）

页数多时规划与执行分两个会话跑：

1. 规划会话跑到 Step 5 结束，打印交接说明
2. 用户在新会话发 `继续生成 projects/<project_name>`
3. 新会话走 `resume-execute` 阶段接上

**页数 ≤15 不启用。** 启用时必须把"下一步怎么继续"讲清楚，否则用户会以为活干完了。

## 五、修订轮（初稿交付后要改时）

已交付项目回来要改，**不重跑规划**，在出问题的层动手：
- 改措辞/加条件/改页标题 → 改该页 SVG → 改 §IX 块 → 改 `notes/total.md` → 改所有重复该句的页（章扉页的目录、目录页页码）
- 加页/删页/移页 → **先重编号**（文件名、页脚、目录页码、§IX 块、`page_rhythm`、`page_visualizations`、`animations.json` 键、备注标题、同稿超链接目标）→ 再增删页
- 全篇改一个颜色或字体 → 跑 `update_spec.py`，但它只处理受支持的键；**派生色、围绕旧值设计的页面、spec 里点名它的文字要手工改**；已生成图片里的旧色不会跟着变——**报告，不要擅自重生成**
- 重编号后要先清 `notes/` 与 `svg_final/` 里对应页的旧文件，这两处只写不清
- 改完重跑：最终门 → 动画校验 → 7.1（备注变了才跑）→ 7.2 → 7.3

## 六、门位速查

| 门 | 位置 | 不过会怎样 |
|---|---|---|
| 接料门 | Step 1 前 | 停 |
| 合并确认门 | Step 4 前 | 不许开工 |
| Design Spec Gate 1 | spec 写完 | 阻塞 lock |
| Gate 2 / validate | lock 派生后 | 阻塞画页 |
| 图片终态门 | Step 5 末 | 阻塞 Executor |
| 早期门 | 第 5 页后 | 阻塞后续页 |
| 最终门 | 全部页完 | **阻塞导出** |
| 图片就绪门 | Step 7 前 | 阻塞导出 |
| **首 5 页用户确认** | 第 3 段末 | 阻塞第 4 段 |
| **批次确认** | 每批末 | 阻塞下一批 |
| **可编辑性验收** | 导出后 | 阻塞交付 |

## 七、禁止事项

- 不跳过 `attribution_guard.py`，不绕过它的非零结果
- 不跳过 Strategist（会丢 §IX 与生产机制），也不让它改锁定内容
- 不用 Quick 图快
- 不删页/并页/抽图表来"过检查"
- 不把图表降级成贴图、不把文字转曲
- 不带虚线占位框导出交付
- 不代替用户确认
- 不在质量门没过时宣布完成
