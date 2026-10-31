---
name: project-orchestration-toolkit
description: "Flow director's toolkit. Load when setting up a charter, routing a specialist, deciding whether a stage can be released, assembling a handoff note, or checking that referenced files exist. Deliberately thin: three release criteria per stage, three fields per handoff note, checks run after the work rather than before it."
---

# 编排工具箱

**一句话原则：编排的价值在于"快速走到一个能被否掉的东西"，不在于"保证每一步都不出错"。**

## 这个案例决定了一切设计

一个 58 页项目跑完全链，**检查点 7 次全 pass、0 次退回、10 余条问题被"记账"消化**。结果：29 页只有施工备忘没有文案 → 落版照搬 → 定稿里 8 页仍是骨架。

原因不是检查太少，是**检查在事后签字，而问题在事前已经发生**。

所以本工具箱反过来：

| 旧 | 现在 |
|---|---|
| 开工前过 7 道闸门检查表 | **开工前只给判断方法；检查表留到交付后** |
| 每道闸门 15–30 条判据 | **每段 3 条**，都问"这东西现在能不能用" |
| 交接包六个字段 | **三个字段** |
| 台账脚本核对 | 手工核，不写脚本 |

## 加载指引

| 要做的事 | 加载 |
|---|---|
| 判断这段能不能放行 | `references/放行判据.md` |
| 出交接包 | `references/交接包模板.md` |
| 交接前三核 | `references/交接核验协议.md` |
| 派工 / 查专家接口 | `references/专家接口速查.md` |
| 立章程 | `references/项目章程规范.md` |
| **开工前确认是全新项目／没串旧项目** | `references/冷启动与数据隔离.md` |
| 记台账 | `references/台账规范.md` |
| 查闸门判据 / 数到第几道闸 | `references/闸门判据表.md` |
| 段末验收、填验收单 | `references/验收单模板.md` |
| 核专家族规模、契约边界 | `references/契约快照.md` |
| 核交付物里的文件是否真存在 | 跑 `scripts/check_file_refs.py` |

## 四条铁律

1. **检查项只在事后用。** 放在开工前，效果是"什么都不许写"——每句话都能挑出错。先大胆做，做完再扫。
2. **放行只看三条，且都是"能不能用"。** 不看"有没有做到 32 条"，看"下一棒会不会退回来"。
3. **归上游的问题必须回流。** 代改、记账了事、另建补充文件绕过——三条路全封。粒度是「一条问题」，不是「整棒重跑」。
4. **向主人提问：一次问全 + 三件齐全 + 终审不可重提。** 见 `agents/ceyan-lead.md` 第六节。

## 四段式（结构没变，节奏变了）

```
段一 调研与立项：章程 → 主人批 → 观澜（行业研究四件）→ 停 → 筑策（第1–5步）→ 验筹（前置审查）→ 停
段二 文本：析纲（章节 → 逐页）→ 淬言 → 停
段三 视觉：立象（规格 + 样张）→ 落版（初稿）→ 停
段四 收尾：琢磨（精修）→ 我终验 → 交付
```

**每段结束必停，等主人签字。这是唯一的硬规矩。**

两处决策点必停：**方向**（筑策给 5–8 个 × 300 字，主人砍到 2–3 个，**不许跳**）、**样张**（立象给令牌 + 3–5 页样张，点头后才全篇）。

## 交付前自检（30 秒）

- [ ] 本段三条放行判据都过了
- [ ] 交接包三个字段写齐
- [ ] 跑过 `check_file_refs.py`，无缺失
- [ ] 归上游的问题已回流，没有记账了事
- [ ] 需要主人定的，一次问全，每条都有选项和推荐
