#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目隔离闸 —— 开工前确认 root 是**本次新建**的项目空间，不是上一个项目的目录。

用法:
    python check_project_isolation.py --root <项目空间> --project-name <本项目名>
    python check_project_isolation.py --root <项目空间> --project-name <本项目名> --init

退出码: 0 = 全新空间或同名续做，可以开工；1 = 疑似旧项目／拿错目录，须回问主人；2 = 用法/环境错误

判定表:
    目录不存在                          → NEW     全新，加 --init 可直接建
    目录存在但空                        → NEW     全新
    非空且无 00-项目标识.json            → SUSPECT 疑似上个项目的目录，停下来问主人
    子目录里有项目标识（本层没有）       → PARENT  你指到了父目录，要指到具体项目
    标识存在且项目名一致                → SAME    同一项目续做，放行
    标识存在且项目名不一致               → WRONG   拿错目录了

设计约束（主人 2026-10-29 定）:
  - 每次新任务都当全新项目从 0 开始；历史项目的结论／数字／文件不进本项目
  - 项目身份写在 00-项目标识.json，不依赖目录名（目录名可改，标识跟着文件走）
  - 判不准时一律 STOP：误停只是多问一句，误放会把上个项目的数据带进新项目
"""
import argparse
import io
import json
import os
import sys
from datetime import datetime

MARKER = "00-项目标识.json"
JUNK = {".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep"}


def real_entries(d):
    try:
        return [e for e in os.listdir(d) if e not in JUNK]
    except OSError:
        return []


def read_marker(d):
    p = os.path.join(d, MARKER)
    if not os.path.isfile(p):
        return None
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return {"project": "<标识文件损坏>", "created": "?", "root": d}


def norm(s):
    return (s or "").strip().lower().replace(" ", "")


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--root", required=True, help="本次项目的空间目录")
    ap.add_argument("--project-name", required=True, help="本项目名称，用于核对标识")
    ap.add_argument("--init", action="store_true", help="全新空间时写入项目标识")
    a = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(a.root))
    name = a.project_name.strip()
    if not name:
        print("ERROR  --project-name 不能为空")
        return 2

    # 1) 目录不存在
    if not os.path.isdir(root):
        print(f"NEW     目录还不存在：{root}")
        if a.init:
            os.makedirs(root, exist_ok=True)
            _write(root, name)
            print(f"INIT    已建空间并写入标识（项目：{name}）")
            return 0
        print("        这是全新项目。加 --init 建空间，或让主人确认路径后再开工。")
        return 0

    entries = real_entries(root)

    # 2) 空目录
    if not entries:
        print(f"NEW     目录为空：{root}")
        if a.init:
            _write(root, name)
            print(f"INIT    已写入标识（项目：{name}）")
            return 0
        print("        这是全新项目，可以开工。建议加 --init 落一个项目标识。")
        return 0

    # 3) 有标识 → 比对项目名
    m = read_marker(root)
    if m is not None:
        old = m.get("project", "")
        if norm(old) == norm(name):
            print(f"SAME    同一项目续做（{old}，建于 {m.get('created','?')}）：{root}")
            print("        放行。但仍只读主人本次提供的资料。")
            return 0
        print(f"WRONG   目录标识的项目是「{old}」，不是「{name}」：{root}")
        print("        拿错目录了。换成本项目的空间，或让主人确认。")
        return 1

    # 4) 没标识但看着像父目录（子目录里有标识）
    subs = [e for e in entries if os.path.isdir(os.path.join(root, e))]
    kids = [e for e in subs if os.path.isfile(os.path.join(root, e, MARKER))]
    if len(kids) >= 1:
        print(f"PARENT  你指的是父目录，里面装着 {len(kids)} 个项目：{', '.join(kids[:5])}")
        print("        --root 必须指到具体项目那一层，不能指它们的上级。")
        return 1

    # 5) 非空、没标识、不是父目录 → 判不了，停
    print(f"SUSPECT 目录已有内容，但没有项目标识：{root}")
    print(f"        已有 {len(entries)} 个条目，前几个：{', '.join(entries[:6])}")
    print("        可能是上一个项目的空间。**不要在这上面开工。**")
    print("        → 新建一个本项目空间；或让主人确认「这就是本项目」后加 --init 补标识。")
    return 1


def _write(root, name):
    p = os.path.join(root, MARKER)
    data = {
        "project": name,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "root": root,
        "note": "本文件标记该目录属于哪个项目。写了它，别的项目就不会误用这个空间。",
    }
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    sys.exit(main())
