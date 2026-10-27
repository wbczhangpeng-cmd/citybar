#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""逐页检查 pptx 的可编辑性，输出终端表格 + 可选 JSON。

用法：
    python check_editability.py <pptx路径> [--json <输出路径>]

判定口径：
    不合格  — 该页没有可编辑文本，且图片覆盖面积 >= 85%（疑似整页截图）
    待复核  — 该页无文本但有原生图表/表格（可能是纯图表页，需人工确认）
    合格    — 存在可编辑文本对象

退出码：0 全部合格或待复核；1 存在不合格页；2 参数或读取错误。
"""

import argparse
import json
import os
import sys

from pptx import Presentation
from pptx.util import Emu


def emu_area(shape):
    try:
        return int(shape.width) * int(shape.height)
    except Exception:
        return 0


def walk(shapes, acc):
    """递归统计，组合内的形状也算。"""
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            acc["groups"] += 1
            walk(sh.shapes, acc)
            continue
        if sh.has_text_frame and sh.text_frame.text.strip():
            acc["text"] += 1
            acc["chars"] += len(sh.text_frame.text.strip())
        if getattr(sh, "has_table", False) and sh.has_table:
            acc["tables"] += 1
        if getattr(sh, "has_chart", False) and sh.has_chart:
            acc["charts"] += 1
        if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
            acc["pictures"] += 1
            acc["picture_area"] += emu_area(sh)
        # 图片填充的自动图形同样按位图处理
        try:
            fill = sh.fill
            if fill.type is not None and str(fill.type).startswith("MSO_FILL_TYPE.PICTURE"):
                acc["pictures"] += 1
                acc["picture_area"] += emu_area(sh)
        except Exception:
            pass
    return acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx")
    ap.add_argument("--json", dest="json_path", default=None)
    args = ap.parse_args()

    if not os.path.isfile(args.pptx):
        print("找不到文件：%s" % args.pptx)
        return 2

    try:
        prs = Presentation(args.pptx)
    except Exception as exc:
        print("打不开 pptx：%s" % exc)
        return 2

    slide_area = int(prs.slide_width) * int(prs.slide_height) or 1
    rows = []
    bad = 0

    for idx, slide in enumerate(prs.slides, start=1):
        acc = {"text": 0, "chars": 0, "tables": 0, "charts": 0,
               "pictures": 0, "groups": 0, "picture_area": 0}
        walk(slide.shapes, acc)
        cover = acc["picture_area"] / float(slide_area)

        if acc["text"] == 0 and cover >= 0.85:
            verdict = "不合格"
            bad += 1
            note = "疑似整页位图"
        elif acc["text"] == 0 and (acc["charts"] or acc["tables"]):
            verdict = "待复核"
            note = "无文本，纯图表/表格页"
        elif acc["text"] == 0:
            verdict = "不合格"
            bad += 1
            note = "无可编辑文本"
        else:
            verdict = "合格"
            note = ""

        rows.append({
            "page": idx,
            "text_objects": acc["text"],
            "chars": acc["chars"],
            "native_charts": acc["charts"],
            "native_tables": acc["tables"],
            "pictures": acc["pictures"],
            "picture_coverage": round(cover, 3),
            "groups": acc["groups"],
            "verdict": verdict,
            "note": note,
        })

    hdr = "%-5s %-6s %-6s %-7s %-7s %-6s %-7s %-8s %s" % (
        "页", "文本", "字数", "原生图", "原生表", "图片", "图占比", "组合", "判定")
    print(hdr)
    print("-" * len(hdr.encode("gbk", "ignore")))
    for r in rows:
        pct = "%.0f%%" % (r["picture_coverage"] * 100)
        print("%-5s %-6d %-6d %-7d %-7d %-6d %-7s %-8d %s%s" % (
            "P%02d" % r["page"], r["text_objects"], r["chars"],
            r["native_charts"], r["native_tables"], r["pictures"],
            pct, r["groups"], r["verdict"],
            ("  ← " + r["note"]) if r["note"] else ""))

    total = len(rows)
    print("-" * len(hdr.encode("gbk", "ignore")))
    print("共 %d 页：合格 %d，待复核 %d，不合格 %d" % (
        total,
        sum(1 for r in rows if r["verdict"] == "合格"),
        sum(1 for r in rows if r["verdict"] == "待复核"),
        bad))

    payload = {
        "file": os.path.abspath(args.pptx),
        "slide_count": total,
        "slide_width_emu": int(prs.slide_width),
        "slide_height_emu": int(prs.slide_height),
        "failures": bad,
        "pages": rows,
    }

    out = args.json_path or (os.path.splitext(args.pptx)[0] + ".editability.json")
    try:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print("报告：%s" % out)
    except Exception as exc:
        print("报告写入失败（不影响判定）：%s" % exc)

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
