#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_project.py — 校验项目台账与实物是否相符。

它只回答一个问题：**账实是否相符**。它不判断内容好坏。

检查四项：
  1. 登记在案的交付物文件是否真的存在
  2. 台账.md 与 project.json 是否一致
  3. 有没有步骤标了「已通过」却没有通过的闸门结论、或没有交付物
  4. 未闭环项与待办是否超期

用法:
    python check_project.py <项目目录>              # 只校验
    python check_project.py <项目目录> --render     # 先由 json 生成 台账.md，再校验
    python check_project.py <项目目录> --today 2026-10-26

退出码: 0 干净(可有警告) / 1 有问题 / 2 读不了
"""

import json
import os
import sys
import datetime
import unicodedata


def dwidth(s):
    """按终端显示宽度算，CJK 占 2 格"""
    w = 0
    for ch in s:
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def pad(s, width):
    s = str(s)
    d = dwidth(s)
    return s if d >= width else s + " " * (width - d)

STATUS_LABEL = {
    "not_started": ("⬜", "未开始"),
    "in_progress": ("🔄", "进行中"),
    "awaiting_gate": ("⏳", "待验收"),
    "passed": ("✅", "已通过"),
    "conditional": ("⚠️", "有条件"),
    "rejected": ("❌", "已打回"),
    "skipped": ("⏭", "跳步"),
}

GATE_LABEL = {
    "pass": "过",
    "conditional": "有条件",
    "reject": "打回",
    None: "—",
}

REQUIRED_TOP = ["project_id", "project_name", "steps"]


def _u8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def load_ledger(root):
    path = os.path.join(root, "project.json")
    if not os.path.isfile(path):
        raise FileNotFoundError("找不到 project.json：%s" % path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("project.json 顶层必须是对象")
    return data


def fmt_step(step):
    sid = step.get("id", "?")
    name = step.get("name", "")
    expert = step.get("expert", "")
    icon, label = STATUS_LABEL.get(step.get("status"), ("❓", str(step.get("status"))))
    dels = step.get("deliverables") or []
    gate = (step.get("gate") or {}).get("conclusion")
    gdate = (step.get("gate") or {}).get("checked_at") or ""
    gtext = GATE_LABEL.get(gate, str(gate))
    if gdate:
        gtext = "%s %s" % (gtext, gdate)
    return " P%s %s %s %s %s  %d 件  闸门 %s" % (
        pad(sid, 2), pad(expert, 6), pad(name, 26),
        icon, pad(label, 6), len(dels), gtext
    )


def render_md(data, today):
    """由 project.json 生成 台账.md"""
    params = data.get("params") or {}
    charter = data.get("charter") or {}
    aud = params.get("audience") or []
    prio = params.get("audience_priority") or []
    aud_txt = " · ".join(
        (a + "（主）" if prio and a == prio[0] else a) for a in aud
    ) or "未定"

    lines = []
    lines.append("# %s · 项目台账" % data.get("project_name", "未命名项目"))
    lines.append("")
    lines.append(
        "项目ID：%s ｜ 类型：%s ｜ 章程：%s（批 %s）"
        % (
            data.get("project_id", "—"),
            data.get("project_type", "—"),
            charter.get("version", "—"),
            charter.get("approved_at", "—"),
        )
    )
    lines.append("")
    lines.append("## 锁定参数")
    lines.append("")
    lines.append(
        "受众：%s ｜ 时长：%s min ｜ 目标页数：%s ｜ 风格：%s"
        % (
            aud_txt,
            params.get("duration_min", "—"),
            params.get("target_pages", "—"),
            params.get("style", "—"),
        )
    )
    lines.append("")

    lines.append("## 七步状态")
    lines.append("")
    lines.append("| # | 步骤 | 专家 | 状态 | 交付物 | 闸门 |")
    lines.append("|---|---|---|---|---|---|")
    for st in data.get("steps") or []:
        icon, label = STATUS_LABEL.get(st.get("status"), ("❓", str(st.get("status"))))
        dels = st.get("deliverables") or []
        del_txt = "、".join(d.get("name", "?") + "_" + (d.get("version") or "") for d in dels) or "—"
        g = st.get("gate") or {}
        g_txt = GATE_LABEL.get(g.get("conclusion"), str(g.get("conclusion")))
        if g.get("checked_at"):
            g_txt = "%s %s" % (g_txt, g["checked_at"])
        lines.append(
            "| %s | %s | %s | %s %s | %s | %s |"
            % (st.get("id", "?"), st.get("name", ""), st.get("expert", ""),
               icon, label, del_txt, g_txt)
        )
    lines.append("")

    def table(title, rows, empty="（无）"):
        lines.append("## " + title)
        lines.append("")
        if not rows:
            lines.append(empty)
            lines.append("")
            return
        lines.append(rows[0])
        lines.append(rows[1])
        for r in rows[2:]:
            lines.append(r)
        lines.append("")

    oi = data.get("open_items") or []
    rows = ["| ID | 步骤 | 内容 | 负责人 | 计划闭环 | 状态 |", "|---|---|---|---|---|---|"]
    for it in oi:
        rows.append("| %s | %s | %s | %s | %s | %s |" % (
            it.get("id", "?"), it.get("step", "—"), it.get("content", ""),
            it.get("owner", "—"), it.get("due", "—"),
            "待办" if it.get("status") == "open" else (it.get("status") or "")))
    table("未闭环项", rows if oi else [])

    td = data.get("todos") or []
    rows = ["| ID | 内容 | 负责人 | 计划 | 状态 |", "|---|---|---|---|---|"]
    for it in td:
        rows.append("| %s | %s | %s | %s | %s |" % (
            it.get("id", "?"), it.get("content", ""), it.get("owner", "—"),
            it.get("due", "—"),
            "待办" if it.get("status") == "open" else (it.get("status") or "")))
    table("待办（非专家环节）", rows if td else [])

    sk = data.get("skips") or []
    rows = ["| 步骤 | 理由 | 决定人 | 时间 | 风险 |", "|---|---|---|---|---|"]
    for it in sk:
        rows.append("| %s | %s | %s | %s | %s |" % (
            it.get("step", "—"), it.get("reason", ""), it.get("decided_by", "—"),
            it.get("decided_at", "—"), it.get("risk", "—")))
    table("跳步记录", rows if sk else [])

    cr = data.get("charter_revisions") or []
    rows = ["| 从 | 到 | 理由 | 时间 | 影响步骤 |", "|---|---|---|---|---|"]
    for it in cr:
        rows.append("| %s | %s | %s | %s | %s |" % (
            it.get("from", "—"), it.get("to", "—"), it.get("reason", ""),
            it.get("decided_at", "—"),
            ", ".join(str(x) for x in (it.get("affected_steps") or [])) or "—"))
    table("章程修订", rows if cr else [])

    lines.append("---")
    lines.append("由 project.json 生成于 %s。**不要手改本文件，改 json 后加 --render 重生成。**" % today)
    lines.append("")
    return "\n".join(lines)


def check(data, root, today):
    errors, warnings = [], []
    E, W = errors.append, warnings.append

    for k in REQUIRED_TOP:
        if k not in data:
            E("project.json 缺少必填字段：%s" % k)
    if errors:
        return errors, warnings

    charter = data.get("charter") or {}
    if not charter.get("version"):
        E("未登记章程版本 —— 章程未锁定，不许开工")
    if not charter.get("approved_at"):
        E("章程未登记批准日期 —— 未批准的章程不生效")
    if charter.get("version") and not os.path.isfile(
            os.path.join(root, charter.get("path") or "章程.md")):
        W("章程文件不存在：%s" % (charter.get("path") or "章程.md"))

    params = data.get("params") or {}
    if not (params.get("audience") or []):
        E("未锁定受众 —— 闸门零未过，不许开工")
    if not params.get("target_pages"):
        W("未锁定目标页数")

    steps = data.get("steps") or []
    if not steps:
        E("steps 为空")

    seen = set()
    open_by_step = {}
    for it in (data.get("open_items") or []):
        if it.get("status") == "open":
            open_by_step.setdefault(it.get("step"), []).append(it)

    skips = data.get("skips") or []
    skip_steps = {s.get("step") for s in skips}

    for st in steps:
        sid = st.get("id")
        nm = st.get("name") or ""
        tag = "P%s %s" % (sid, nm)
        if sid in seen:
            E("%s：步骤号重复" % tag)
        seen.add(sid)

        status = st.get("status")
        if status not in STATUS_LABEL:
            E("%s：非法状态 %r" % (tag, status))
            continue

        gate = (st.get("gate") or {}).get("conclusion")
        dels = st.get("deliverables") or []

        for d in dels:
            p = d.get("path")
            if not p:
                E("%s：交付物「%s」没有登记路径" % (tag, d.get("name", "?")))
                continue
            full = os.path.join(root, p.replace("/", os.sep))
            if not os.path.isfile(full):
                E("%s：交付物不存在 —— %s" % (tag, p))

        if status == "passed":
            if gate != "pass":
                E("%s：状态为已通过，但闸门结论是 %r" % (tag, gate))
            if not dels:
                E("%s：状态为已通过，但没有登记交付物" % tag)
        elif status == "conditional":
            if gate != "conditional":
                E("%s：状态为有条件通过，但闸门结论是 %r" % (tag, gate))
            if not open_by_step.get(sid):
                E("%s：有条件通过但没有关联的未闭环项（条件没写清就是打回）" % tag)
        elif status == "rejected":
            if gate != "reject":
                E("%s：状态为已打回，但闸门结论是 %r" % (tag, gate))
        elif status == "skipped":
            if sid not in skip_steps:
                E("%s：标了跳步但没有 skips 记录" % tag)
        elif status == "not_started" and dels:
            W("%s：未开始却已登记交付物" % tag)

        if status in ("in_progress", "awaiting_gate") and gate in ("pass", "conditional"):
            W("%s：闸门已出结论但状态仍是 %s" % (tag, status))

    for it in (data.get("open_items") or []):
        if it.get("status") != "open":
            continue
        due = it.get("due")
        if due and due < today:
            W("未闭环项 %s 超期：%s（负责人 %s，计划 %s）"
              % (it.get("id", "?"), it.get("content", ""), it.get("owner", "?"), due))

    for it in (data.get("todos") or []):
        if it.get("status") != "open":
            continue
        due = it.get("due")
        if due and due < today:
            W("待办 %s 超期：%s（负责人 %s，计划 %s）"
              % (it.get("id", "?"), it.get("content", ""), it.get("owner", "?"), due))

    return errors, warnings


def check_md(data, root):
    """台账.md 与 project.json 的一致性（粗粒度）"""
    errors, warnings = [], []
    p = os.path.join(root, "台账.md")
    if not os.path.isfile(p):
        errors.append("台账.md 不存在 —— 跑 --render 生成")
        return errors, warnings
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()

    for st in data.get("steps") or []:
        nm = (st.get("name") or "").strip()
        if nm and nm not in txt:
            errors.append("台账.md 未包含步骤「%s」—— md 与 json 已分叉" % nm)

    cv = (data.get("charter") or {}).get("version")
    if cv and cv not in txt:
        warnings.append("台账.md 未出现章程版本 %s" % cv)

    return errors, warnings


def main(argv):
    _u8()
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print("用法: python check_project.py <项目目录> [--render] [--today YYYY-MM-DD]")
        return 2

    root = args[0]
    do_render = "--render" in argv
    today = datetime.date.today().isoformat()
    if "--today" in argv:
        i = argv.index("--today")
        if i + 1 < len(argv):
            today = argv[i + 1]

    if not os.path.isdir(root):
        print("读不了：目录不存在 —— %s" % root)
        return 2

    try:
        data = load_ledger(root)
    except Exception as e:
        print("读不了 project.json：%s" % e)
        return 2

    if do_render:
        md = render_md(data, today)
        with open(os.path.join(root, "台账.md"), "w", encoding="utf-8") as f:
            f.write(md)
        print("已由 project.json 生成 台账.md")
        print()

    print("项目：%s（%s）" % (data.get("project_name", "?"), data.get("project_id", "?")))
    ch = data.get("charter") or {}
    print("章程：%s 批于 %s" % (ch.get("version", "—"), ch.get("approved_at", "—")))
    print("目录：%s" % os.path.abspath(root))
    print()

    steps = data.get("steps") or []
    cnt = {}
    for st in steps:
        cnt[st.get("status")] = cnt.get(st.get("status"), 0) + 1
    print("七步状态")
    print("-" * 78)
    for st in steps:
        print(fmt_step(st))
    print("-" * 78)
    passed = cnt.get("passed", 0)
    print("进展：%d/%d 已通过，%d 有条件，%d 进行中，%d 未开始"
          % (passed, len(steps), cnt.get("conditional", 0),
             cnt.get("in_progress", 0) + cnt.get("awaiting_gate", 0),
             cnt.get("not_started", 0)))
    print()

    e1, w1 = check(data, root, today)
    e2, w2 = check_md(data, root)
    errors = e1 + e2
    warnings = w1 + w2

    if errors or warnings:
        print("问题")
        print("-" * 78)
        for m in errors:
            print("[错误] %s" % m)
        for m in warnings:
            print("[警告] %s" % m)
        print("-" * 78)

    if errors:
        print("结论：%d 个错误，%d 个警告 → 不通过" % (len(errors), len(warnings)))
        return 1
    if warnings:
        print("结论：0 个错误，%d 个警告 → 通过（有警告）" % len(warnings))
        return 0
    print("结论：账实相符，无问题")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
