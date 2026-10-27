#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""原始资料闸 —— 开工前比对 `原始资料/` 与台账，输出新增／改动／删除／未登记，
并把新增文件拿去对撞交付物里所有待补条目。

用法:
    python check_raw_materials.py --root <项目空间> [--ledger 原始资料/00-资料台账.md]
                                  [--pend 交付物] [--update] [--json raw.json]

退出码: 0 = 干净（无任何差异）；1 = 有差异，须处置后才能开工；2 = 用法/环境错误

设计约束（主人 2026-10-27 定）:
  01-外部提供  有变 → 走重判
  02-我方回灌  有变 → 只登记，不重判（自家产出不是新输入）
  `00-外部关联.txt` 列出的外部目录 → 与 01-外部提供 同等对待（关联不等于免责）
  台账无人值守：关联页／状态由本脚本自动写，主人不需要手改
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime

RAW_DIR = "原始资料"
LEDGER_NAME = "00-资料台账.md"
LINK_NAME = "00-外部关联.txt"
SUB_EXT = "01-外部提供"
SUB_OWN = "02-我方回灌"
SUB_LINK = "外部关联"
SKIP_NAMES = {LEDGER_NAME, LINK_NAME, ".DS_Store", "Thumbs.db"}

LEDGER_HEAD = """# 原始资料台账

> **本表由脚本生成，主人不需要手改。** 手改会在下一次 `--update` 被盘上实测覆盖。
> 维护：`python check_raw_materials.py --root <项目空间> --update`
> 列义：`md5` 内容指纹（变了＝内容变了）｜`关联页` 对撞命中的待补位置｜`状态` 是否已被交付物引用

| 文件名 | 子目录 | md5 | 字节 | 入库时间 | 提供人 | 关联页 | 状态 |
|---|---|---|---|---|---|---|---|
"""

LINK_HEAD = """# 外部关联目录（一行一条绝对路径，# 开头是注释）
# 关联进来的目录与 01-外部提供/ 同等对待：里面的文件变了，一样算改动，一样要重判。
# 例：
# D:\\项目\\某项目\\设计院图纸
# E:\\甲方材料\\2026-10
"""


def md5_of(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def external_roots(root):
    """读 00-外部关联.txt，返回 [(标签, 绝对路径)]"""
    p = os.path.join(root, RAW_DIR, LINK_NAME)
    out = []
    if not os.path.isfile(p):
        return out
    for line in io.open(p, encoding="utf-8"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        s = os.path.expandvars(os.path.expanduser(s))
        tag = os.path.basename(os.path.normpath(s)) or "外部"
        out.append((tag, s))
    return out


def walk_into(root_path, label, out):
    if not os.path.isdir(root_path):
        out[("__missing__", label)] = (root_path, 0, root_path)
        return
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [x for x in dirnames if not x.startswith(".")]
        for fn in filenames:
            if fn in SKIP_NAMES or fn.startswith("."):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root_path).replace(os.sep, "/")
            try:
                out[(label, rel)] = (md5_of(p), os.path.getsize(p), p)
            except OSError:
                continue


def scan(root):
    """返回 {(来源标签, 相对名): (md5, 字节, 绝对路径)}"""
    out = {}
    base = os.path.join(root, RAW_DIR)
    for sub in (SUB_EXT, SUB_OWN):
        d = os.path.join(base, sub)
        if os.path.isdir(d):
            walk_into(d, sub, out)
    for tag, p in external_roots(root):
        walk_into(p, SUB_LINK + "/" + tag, out)
    return out


CELL = re.compile(r"^\|(.+)\|\s*$")


def parse_ledger(path):
    rows = {}
    if not os.path.isfile(path):
        return rows
    for line in io.open(path, encoding="utf-8"):
        m = CELL.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if len(cells) < 8 or cells[0] == "文件名" or set(cells[0]) <= set("-: "):
            continue
        rows[(cells[1], cells[0])] = {
            "md5": cells[2], "字节": cells[3], "入库时间": cells[4],
            "提供人": cells[5], "关联页": cells[6], "状态": cells[7],
        }
    return rows


def corpus(pend_dir):
    """把交付物里所有 md 拼成一个大文本，用于判「这份料被用过没有」"""
    buf = []
    if pend_dir and os.path.isdir(pend_dir):
        for dirpath, dirnames, filenames in os.walk(pend_dir):
            dirnames[:] = [x for x in dirnames if not x.startswith(".")]
            for fn in filenames:
                if fn.endswith(".md"):
                    try:
                        buf.append(io.open(os.path.join(dirpath, fn), encoding="utf-8").read())
                    except (UnicodeDecodeError, OSError):
                        continue
    return "\n".join(buf)


PEND_PAT = re.compile(r"待补|待主人补|待甲方补|待确认|待出图|待现场核验")


def pend_lines(pend_dir):
    hits = []
    if not pend_dir or not os.path.isdir(pend_dir):
        return hits
    for dirpath, dirnames, filenames in os.walk(pend_dir):
        dirnames[:] = [x for x in dirnames if not x.startswith(".")]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                for i, line in enumerate(io.open(p, encoding="utf-8"), 1):
                    if PEND_PAT.search(line):
                        hits.append((os.path.relpath(p, pend_dir).replace(os.sep, "/"),
                                     i, line.strip()[:160]))
            except (UnicodeDecodeError, OSError):
                continue
    return hits


def tokens(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    parts = re.split(r"[_\-\s（）()【】\[\]·]+", stem)
    out = []
    for p in parts:
        if re.fullmatch(r"\d{6,8}", p) or p in ("主人提供", "甲方提供", "最终", "定稿", "v1", "v2", "v3"):
            continue
        if len(p) >= 3:
            out.append(p)
    return out


def write_ledger(path, disk, old, hits_map, body):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    lines = [LEDGER_HEAD]
    for k in sorted(disk, key=lambda x: (x[0], x[1])):
        label, rel = k
        d, sz, _ = disk[k]
        o = old.get(k, {})
        hit = hits_map.get(k) or o.get("关联页") or "—"
        stem = os.path.splitext(os.path.basename(rel))[0]
        if os.path.basename(rel) in body or (len(stem) >= 4 and stem in body):
            used = "已用"
        elif hit != "—":
            used = "待用"
        else:
            used = "未用"
        lines.append("| %s | %s | %s | %d | %s | %s | %s | %s |\n" % (
            os.path.basename(rel), label, d, sz,
            o.get("入库时间") or datetime.now().strftime("%Y-%m-%d %H:%M"),
            o.get("提供人") or "—",
            hit, used,
        ))
    io.open(path, "w", encoding="utf-8").writelines(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="项目空间根目录")
    ap.add_argument("--ledger", default=os.path.join(RAW_DIR, LEDGER_NAME))
    ap.add_argument("--pend", default="交付物", help="扫待补的目录，留空则跳过对撞")
    ap.add_argument("--update", action="store_true", help="把当前盘上状态写回台账")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    if not os.path.isdir(root):
        print("ERROR 项目空间不存在: %s" % root, file=sys.stderr)
        return 2
    ledger = a.ledger if os.path.isabs(a.ledger) else os.path.join(root, a.ledger)
    pend_dir = (a.pend if os.path.isabs(a.pend) else os.path.join(root, a.pend)) if a.pend else None

    for sub in (SUB_EXT, SUB_OWN):
        if not os.path.isdir(os.path.join(root, RAW_DIR, sub)):
            print("ERROR 缺少必建子目录: %s/%s" % (RAW_DIR, sub), file=sys.stderr)
            return 2

    disk_raw = scan(root)
    missing_roots = [(k[1], disk_raw[k][2]) for k in disk_raw if k[0] == "__missing__"]
    disk = {k: v for k, v in disk_raw.items() if k[0] != "__missing__"}
    old = parse_ledger(ledger)
    pend = pend_lines(pend_dir)
    body = corpus(pend_dir)

    new = [k for k in disk if k not in old]
    gone = [k for k in old if k not in disk]
    changed = [k for k in disk if k in old and old[k]["md5"] and old[k]["md5"] != disk[k][0]]
    blank = [k for k in disk if k in old and not old[k]["md5"]]

    hits, hits_map = [], {}
    for k in new + changed:
        for t in tokens(k[1]):
            for (pf, ln, text) in pend:
                if t in text:
                    hits.append({"文件": k[1], "来源": k[0], "命中词": t,
                                 "待补位置": "%s:%d" % (pf, ln), "待补原文": text})
                    hits_map[k] = "%s:%d" % (pf, ln)
                    break

    def show(title, keys, note=""):
        if not keys:
            return
        print("\n【%s】%d 项 %s" % (title, len(keys), note))
        for k in sorted(keys, key=lambda x: (x[0], x[1])):
            print("  - %s/%s" % (k[0], k[1]))

    print("原始资料闸  ·  %s" % root)
    print("盘上 %d 份（含外部关联 %d 份）｜台账 %d 份｜待补条目 %d 条" % (
        len(disk), sum(1 for k in disk if k[0].startswith(SUB_LINK)), len(old), len(pend)))

    if missing_roots:
        print("\n【外部关联失效】%d 处 —— 路径不存在，先修 00-外部关联.txt" % len(missing_roots))
        for tag, p in missing_roots:
            print("  - %s  →  %s" % (tag, p))

    show("新增", new, "（外部提供→重判；我方回灌→只登记）")
    show("改动（md5 变）", changed, "（必须报司南，判是否推翻已有成果）")
    show("删除", gone, "（必须报司南，确认不是误删）")
    show("未登记（md5 空）", blank, "（补登记，否则每轮都会漏判）")

    if hits:
        print("\n【新增×待补 对撞命中】%d 处" % len(hits))
        for h in hits:
            print("  ! %s（%s｜%s）↔ %s" % (h["文件"], h["来源"], h["命中词"], h["待补位置"]))
            print("      %s" % h["待补原文"])

    dirty = bool(new or gone or changed or blank or missing_roots)
    if not dirty:
        print("\n结论：干净。台账与盘上一致，可以开工。")
    else:
        print("\n结论：有差异 %d 项。**处置完才能开工。**" % (
            len(new) + len(gone) + len(changed) + len(blank) + len(missing_roots)))

    if a.update:
        write_ledger(ledger, disk, old, hits_map, body)
        lp = os.path.join(root, RAW_DIR, LINK_NAME)
        if not os.path.isfile(lp):
            io.open(lp, "w", encoding="utf-8").write(LINK_HEAD)
        print("台账已写回：%s" % ledger)

    if a.json:
        p = a.json if os.path.isabs(a.json) else os.path.join(root, a.json)
        with io.open(p, "w", encoding="utf-8") as f:
            json.dump({"新增": ["%s/%s" % k for k in new],
                       "改动": ["%s/%s" % k for k in changed],
                       "删除": ["%s/%s" % k for k in gone],
                       "未登记": ["%s/%s" % k for k in blank],
                       "外部关联失效": [k[1] for k in missing_roots],
                       "对撞命中": hits}, f, ensure_ascii=False, indent=2)
        print("json 已写：%s" % p)

    return 1 if dirty else 0


if __name__ == "__main__":
    sys.exit(main())
