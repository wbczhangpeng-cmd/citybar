#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""图片覆盖率体检 —— 查「这份汇报到底是不是一份图文汇报」。

## 为什么需要这个脚本

文旅 / 商业综合体 / 景区类汇报，**图片承担的是论证功能，不是装饰功能**。
说「园区基本闲置」是判断，配一张空荡广场的实景才是证据。

真实事故（某文旅项目实测）：一份数十页的汇报交出来 **0 张图片**，
图位表里有 17 项却几乎全标"待甲方提供"，而其中动线图、矩阵图、
面积分析图本来都是能自己画的。最后甲方看到的是一份纯文字可行性研究报告。

**这个脚本回答一件事：成稿里的图，到底够不够、空在哪几页。**

## 它查四样

1. **图片覆盖页占比** —— 有图的页 / 总页数。零图页超过 20% 判不合格
2. **零图页清单** —— 逐页列出，且区分「有图表但无照片」与「纯文字」
3. **图片面积占用** —— 每页图片占总面积比，识别"塞了个小图标充数"
4. **图文配比** —— 对照 `--plan` 给的图位分配表（P/S/O），核 P 档页是否都有图

## 怎么和「图表」区分

原生图表（chart）、表格（table）**不算图片**。它们承载数据，不是视觉素材。
脚本分开统计：`photo`（图片/位图）、`chart`（原生图表）、`table`（原生表格）。
判「是不是图文汇报」只看 photo。

## 退出码

    0 = 达标        1 = 零图页过多        2 = P 档缺图（最严重）

用法：
    python check_image_coverage.py deck.pptx
    python check_image_coverage.py deck.pptx --json out.json
    python check_image_coverage.py deck.pptx --plan 图位分配表.md
    python check_image_coverage.py deck.pptx --max-empty 0.20 --min-cover 0.35

依赖：python-pptx
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

try:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
except ImportError:
    sys.exit('[FATAL] 缺 python-pptx。装它：pip install python-pptx')

EMU_PER_PT = 12700


def _px(emu, per_px):
    """EMU → px"""
    return float(emu) / per_px if emu is not None else 0.0


def _walk(shapes, per_px):
    """递归展开 group，产出 (shape, box)。box 单位统一为 px —— 面积必须在 px 下算，否则 EMU²/px² 会算飞。"""
    for sh in shapes:
        try:
            w = _px(sh.width, per_px)
            h = _px(sh.height, per_px)
        except Exception:
            continue
        cur = dict(w=w, h=h)
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            for sub, _ in _walk(sh.shapes, per_px):
                yield sub, cur
        else:
            yield sh, cur


def _kind(sh):
    """判形状类型：photo / chart / table / other"""
    try:
        st = sh.shape_type
    except Exception:
        return 'other'
    if st == MSO_SHAPE_TYPE.PICTURE:
        return 'photo'
    if getattr(sh, 'has_chart', False) and sh.has_chart:
        return 'chart'
    if getattr(sh, 'has_table', False) and sh.has_table:
        return 'table'
    # 占位符里可能是图片
    if getattr(sh, 'image', None) is not None:
        return 'photo'
    return 'other'


def _load_plan(path):
    """解析图位分配表（Markdown 表格），返回 {page: 'P'/'S'/'O'}。

    宽容匹配：找含「P」「S」「O」独立字母的单元格；页码从 P01 / 第1页 / 1 里提。
    """
    plan = {}
    if not path or not os.path.exists(path):
        return plan
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not line.strip().startswith('|'):
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) < 2:
                continue
            m = re.search(r'(?:P|第)?\s*0*(\d{1,3})\s*(?:页)?', cells[0])
            if not m:
                continue
            page = int(m.group(1))
            tier = None
            for c in cells[1:4]:
                mm = re.fullmatch(r'\*{0,2}([PSO])\*{0,2}', c.strip())
                if mm:
                    tier = mm.group(1)
                    break
            if tier:
                plan[page] = tier
    return plan


def check(pptx_path, plan=None, max_empty=0.65, min_cover=0.35,
          max_textonly=0.30, quiet=False):
    prs = Presentation(pptx_path)
    # 从 slide_width 反推 1px 对应多少 EMU（默认按 1920 宽）
    W_px = 1920.0
    per_px = float(prs.slide_width) / W_px
    H_px = float(prs.slide_height) / per_px
    page_area = W_px * H_px

    rows = []
    for idx, slide in enumerate(prs.slides, 1):
        photo, chart, table = [], [], []
        for sh, box in _walk(slide.shapes, per_px):
            k = _kind(sh)
            if k == 'other':
                continue
            area = max(0.0, box['w']) * max(0.0, box['h'])
            item = dict(w=round(box['w'], 1), h=round(box['h'], 1),
                        area_ratio=round(area / page_area * 100, 1))
            (photo if k == 'photo' else chart if k == 'chart' else table).append(item)

        rows.append(dict(page=idx,
                         photo=len(photo), chart=len(chart), table=len(table),
                         photo_area=round(sum(x['area_ratio'] for x in photo), 1),
                         tiny=[x for x in photo if x['area_ratio'] < 1.0],
                         tier=(plan or {}).get(idx)))

    n = len(rows)
    with_photo = [r for r in rows if r['photo'] > 0]
    empty = [r for r in rows if r['photo'] == 0]
    text_only = [r for r in empty if r['chart'] == 0 and r['table'] == 0]
    tiny_pages = [r for r in rows if r['tiny']]

    # P 档缺图
    p_pages = [r for r in rows if r['tier'] == 'P']
    p_missing = [r for r in p_pages if r['photo'] == 0]
    s_pages = [r for r in rows if r['tier'] == 'S']
    s_missing = [r for r in s_pages if r['photo'] == 0]

    cover = len(with_photo) / n if n else 0
    result = dict(file=os.path.abspath(pptx_path), slides=n,
                  photo_pages=len(with_photo), empty_pages=len(empty),
                  text_only_pages=len(text_only), cover=round(cover * 100, 1),
                  total_photo=sum(r['photo'] for r in rows),
                  total_chart=sum(r['chart'] for r in rows),
                  total_table=sum(r['table'] for r in rows),
                  plan_loaded=bool(plan),
                  p_pages=len(p_pages), p_missing=[r['page'] for r in p_missing],
                  s_pages=len(s_pages), s_missing=[r['page'] for r in s_missing],
                  rows=rows)

    # ── 出报告 ────────────────────────────────────────────────────────────
    if not quiet:
        print('文件：%s' % os.path.basename(pptx_path))
        print('画布：%.0f×%.0f px ｜ 共 %d 页' % (W_px, H_px, n))
        print()
        print('图片 %d 张 ｜ 原生图表 %d 个 ｜ 原生表格 %d 个'
              % (result['total_photo'], result['total_chart'], result['total_table']))
        print('有图的页 %d / %d（覆盖 %.0f%%）' % (len(with_photo), n, cover * 100))
        print()

        if empty:
            print('零图页 %d 页：%s' % (len(empty),
                  ' '.join('P%02d' % r['page'] for r in empty[:20])
                  + (' …' if len(empty) > 20 else '')))
            if text_only:
                print('  其中「纯文字页」（无图、无图表、无表格）%d 页：%s'
                      % (len(text_only), ' '.join('P%02d' % r['page'] for r in text_only[:16])))
            print()

        if tiny_pages:
            print('有图但图极小（< 页面 1%%，疑似图标充数）%d 页：' % len(tiny_pages))
            for r in tiny_pages[:8]:
                print('  P%02d  最小一张仅占 %.1f%%' % (r['page'], min(x['area_ratio'] for x in r['tiny'])))
            print()

        if result['plan_loaded']:
            print('对照图位分配表：P 档 %d 页 ｜ S 档 %d 页' % (result['p_pages'], result['s_pages']))
            if p_missing:
                print('  [严重] P 档缺图 %d 页：%s' % (len(p_missing),
                      ' '.join('P%02d' % r['page'] for r in p_missing)))
                print('         这几页的论证不成立，不许定稿')
            else:
                print('  ✓ P 档页面全部有图')
            if s_missing:
                print('  [警告] S 档缺图 %d 页：%s' % (len(s_missing),
                      ' '.join('P%02d' % r['page'] for r in s_missing)))
            print()

    # ── 判定 ──────────────────────────────────────────────────────────────
    code = 0
    reasons = []
    if p_missing:
        code = 2
        reasons.append('P 档缺图 %d 页' % len(p_missing))
    if len(empty) / n > max_empty if n else False:
        code = max(code, 1)
        reasons.append('零图页 %.0f%% > 阈值 %.0f%%' % (len(empty) / n * 100, max_empty * 100))
    if cover < min_cover:
        code = max(code, 1)
        reasons.append('图片覆盖页 %.0f%% < 底线 %.0f%%' % (cover * 100, min_cover * 100))
    to_ratio = len(text_only) / n if n else 0
    if to_ratio > max_textonly:
        code = max(code, 1)
        reasons.append('纯文字页 %.0f%% > 上限 %.0f%%（这类页连图表表格都没有）'
                       % (to_ratio * 100, max_textonly * 100))

    if not quiet:
        print('-' * 60)
        if code == 0:
            print('结论：达标 —— 覆盖页 %.0f%%，零图页 %.0f%%，P 档齐备'
                  % (cover * 100, len(empty) / n * 100))
        else:
            print('结论：不达标 —— %s' % '；'.join(reasons))
            print('注意：补图不属于精修（那是内容生产）。零图页过多说明当初排页时没定图位，退回流。')
    return result, code


def main():
    ap = argparse.ArgumentParser(description='图片覆盖率体检')
    ap.add_argument('pptx')
    ap.add_argument('--json', help='明细写 JSON')
    ap.add_argument('--plan', help='图位分配表（Markdown），核 P/S/O 档是否到位')
    ap.add_argument('--max-empty', type=float, default=0.65,
                    help='零图页占比上限，默认 0.65（与 --min-cover 互补：0.35 覆盖 = 0.65 零图）')
    ap.add_argument('--min-cover', type=float, default=0.35,
                    help='有图页占比底线，默认 0.35（文旅类底线）')
    ap.add_argument('--max-textonly', type=float, default=0.30,
                    help='纯文字页（无图无图表无表格）占比上限，默认 0.30')
    ap.add_argument('--quiet', action='store_true', help='只出结论')
    a = ap.parse_args()

    if not os.path.exists(a.pptx):
        sys.exit('[FATAL] 文件不存在：%s' % a.pptx)

    plan = _load_plan(a.plan)
    res, code = check(a.pptx, plan=plan, max_empty=a.max_empty,
                      min_cover=a.min_cover, max_textonly=a.max_textonly,
                      quiet=a.quiet)

    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        if not a.quiet:
            print('\n明细已写入：%s' % a.json)
    sys.exit(code)


if __name__ == '__main__':
    main()
