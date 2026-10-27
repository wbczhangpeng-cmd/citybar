#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文件引用存在性核验 —— 查「文中提到的那个文件，到底在不在」。

## 为什么需要这个脚本

真实事故（张掖项目）：析纲的 P55 写了「8 张表完整明细见附录文档」，
下一棒淬言照着引用，再下一棒立象照着排——**连续三棒引用同一份从未存在过的文件**，
直到有人真去找它才撞见。

这类错误靠读是读不出来的：文字读起来完全通顺，因为它描述的东西"应该有"。
只能机器核。

## 它查什么

从 Markdown / 纯文本里抽出**被当作文件引用的名字**，逐个在工作区里找。
找不到 → 报「缺失」；有同名但路径不同 → 报「路径不符」（轻一级）。

识别形态（保守，宁漏不错）：
- 反引号包裹：`` `step6-02_附录数据附表_v1.md` ``
- 「见 / 详见 / 参见 / 落点 / 保存为 / 输出到 / 新建」+ 文件名
- 带目录的路径：`交付物/xxx.md`、`./_build/x.py`

刻意忽略：URL、通配符、占位符（含 `<>{}*?|%`）、命令参数、纯扩展名。

## 适用场景与已知噪声（重要，别用错地方）

**适用**：项目工作区里的交付物互相引用。比如「P55 说明细见 step6-02_附录数据附表_v1.md」
——这个文件应该有，没有就是错。

**不适用于专家包的规范文档**。规范文档天生会提到大量**通用产物名**
（`台账.md`、`design_spec.md`、`styles_index.json`、`schema.json`……），
这些不是"本目录该有的文件"，而是"某个项目里会产生的东西"。
拿本脚本去扫它们，会得到几十条误报，而且**每一条看起来都很像真的**。

用 `--builtin-ignore` 可滤掉常见产物名与 ppt-master 规范名，适合粗扫；
但只要你知道自己在扫规范文档，就该换个判据——**不存在 ≠ 该存在**。

## 退出码

    0 = 引用的文件全部存在        1 = 有缺失

用法：
    python check_file_refs.py                          # 核当前目录下所有 .md
    python check_file_refs.py --root . --root 交付物
    python check_file_refs.py 交付物/step3-02_xxx.md   # 只核指定文件
    python check_file_refs.py --json refs.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# 只认这些扩展名，避免把「1.5」「v1.2」当成文件
EXTS = ('.md', '.markdown', '.txt', '.json', '.jsonl', '.py', '.pptx', '.ppt',
        '.docx', '.doc', '.xlsx', '.xls', '.svg', '.png', '.jpg', '.jpeg',
        '.html', '.htm', '.pdf', '.csv', '.yaml', '.yml')

# 文件名主体：允许带目录前缀（schemas/xxx.schema.json 要整体抓，不能截成 xxx.json）
# 中英文数字下划线横线点，可带 / 或 \ 分段
_NAME_BODY = r'[\w\u4e00-\u9fff.\-]'
NAME_RE = re.compile(
    r'(?<![A-Za-z0-9_\-])'
    r'((?:%s+[/\\])*%s+?\.(?:%s))' % (_NAME_BODY, _NAME_BODY,
                                      '|'.join(re.escape(e[1:]) for e in EXTS)),
    re.IGNORECASE)

# 前文出现这些词，才算"被当作文件引用"（否则可能只是随口提一个后缀）
CTX_RE = re.compile(r'(见|详见|参见|参照|落点|保存为|另存为|输出到|写入|新建|产出|交付物|文件|路径|放在|位于|参照|读取|读|open\()')

BAD_CHARS = set('*?<>|{}%$`')

# 内置忽略集：这些是「某个项目里会产生的东西」或「外部工具的规范名」，
# 不是「本目录该有的文件」。扫规范文档时开 --builtin-ignore，否则全是误报。
#   ⚠ 扫项目交付物时**不要开**——项目里真该有 台账.md，缺了就是要报。
BUILTIN_IGNORE = [
    r'^台账\.md$', r'^project\.json$',
    r'^design_spec(\w*)?(\.schema)?\.(md|json)$',
    r'^styles_index\.json$', r'^charts_index\.json$', r'^tables_index\.json$',
    r'^meta\.json$', r'^schema\.json$', r'^spec_lock\.md$',
    r'^marketplace\.json$',
]


def _index(root_dirs):
    """建立 basename → [相对路径...] 索引。"""
    idx = {}
    for root in root_dirs:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if not d.startswith('.') and d not in ('node_modules', '__pycache__')]
            for fn in filenames:
                idx.setdefault(fn.lower(), []).append(os.path.join(dirpath, fn))
    return idx


def _scan_text(path: str):
    """从一份文件里抽出所有疑似文件引用，返回 [(行号, 引用原文, 上下文)]。"""
    try:
        with open(path, encoding='utf-8') as f:
            lines = f.read().split('\n')
    except (UnicodeDecodeError, OSError):
        return []
    hits = []
    in_code = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue                      # 代码块里的路径多为示例，不核
        for m in NAME_RE.finditer(line):
            name = m.group(1).strip('.,;:')
            if any(c in BAD_CHARS for c in name):
                continue
            low = name.lower()
            if low.startswith(('http', 'www')):
                continue
            # 上下文判据：同行有"见/详见/保存为..."，或名字被反引号包着
            ctx = line[max(0, m.start() - 26):m.start()]
            quoted = ('`' in line[max(0, m.start() - 1):m.start() + len(name) + 2])
            if not (CTX_RE.search(ctx) or quoted):
                continue
            hits.append((i, name, s[:90]))
    return hits


def main():
    ap = argparse.ArgumentParser(description='核验文中引用的文件是否存在')
    ap.add_argument('files', nargs='*', help='要核的文件（默认：root 下所有 .md）')
    ap.add_argument('--root', action='append', default=[],
                    help='搜索根目录（可多次给）。默认：文件所在目录 + 当前目录')
    ap.add_argument('--include-plugins', action='store_true',
                    help='把策研组包目录与 ~/.workbuddy/skills 也纳入搜索根（引用自己 toolkit 时必须开）')
    ap.add_argument('--ignore', action='append', default=[],
                    help='正则：命中则跳过该引用（外部工具约定名，如 design_spec\\.md）')
    ap.add_argument('--builtin-ignore', action='store_true',
                    help='开内置忽略集（通用产物名 / ppt-master 规范名）。扫规范文档时用，扫项目交付物时别用')
    ap.add_argument('--json', help='明细写 JSON')
    ap.add_argument('--quiet', action='store_true', help='只出结论与缺失清单')
    a = ap.parse_args()

    targets = a.files or []
    if not targets:
        for dirpath, dirnames, filenames in os.walk('.'):
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']
            for fn in filenames:
                if fn.lower().endswith('.md'):
                    targets.append(os.path.join(dirpath, fn))
    if not targets:
        sys.exit('[FATAL] 没找到要核的文件')

    roots = a.root or sorted({os.path.dirname(os.path.abspath(t)) or '.' for t in targets} | {'.'})
    if a.include_plugins:
        pkg = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        home = os.path.expanduser('~')
        for extra in (pkg, os.path.join(home, '.workbuddy', 'skills')):
            if os.path.isdir(extra):
                roots.append(extra)
    pats = (BUILTIN_IGNORE if a.builtin_ignore else []) + a.ignore
    ignores = [re.compile(p) for p in pats]

    idx = _index(roots)
    print('搜索根：%s' % ' | '.join(roots))
    print('工作区文件数：%d ｜ 待核文件：%d\n' % (sum(len(v) for v in idx.values()), len(targets)))

    total = missing = mismatch = skipped = 0
    rows = []
    for t in targets:
        for ln, name, ctx in _scan_text(t):
            base = os.path.basename(name.replace('\\', '/')).lower()
            if any(rx.search(name) or rx.search(base) for rx in ignores):
                skipped += 1
                continue
            total += 1
            found = idx.get(base)
            if not found:
                missing += 1
                rows.append(dict(file=os.path.relpath(t), line=ln, ref=name, status='缺失', ctx=ctx))
            else:
                # 带目录的引用：再核那个相对路径本身在不在（否则是"文件在、路径写错"）
                if '/' in name or '\\' in name:
                    ok = any(os.path.abspath(p).replace('\\', '/')
                             .endswith(name.replace('\\', '/')) for p in found)
                    if not ok:
                        mismatch += 1
                        rows.append(dict(file=os.path.relpath(t), line=ln, ref=name,
                                         status='路径不符',
                                         actual=[os.path.relpath(p) for p in found[:2]], ctx=ctx))

    if rows and not a.quiet:
        print('%-44s %5s %-8s %s' % ('来源', '行', '状态', '引用'))
        print('-' * 96)
        for r in rows:
            print('%-44s %5d %-8s %s' % (r['file'][-42:], r['line'], r['status'], r['ref'][:36]))

    print()
    if absent := [r for r in rows if r['status'] == '缺失']:
        print('缺失 %d 处（引用了但文件不存在）：' % len(absent))
        for r in absent:
            print('  %s:%d  →  %s' % (r['file'], r['line'], r['ref']))
        print('  这类错误的特征：文字读起来完全通顺，因为它描述的东西"应该有"。')
        print('  处置：补建该文件，或把引用改成真存在的东西。不许放任。')
    else:
        print('缺失 0 处 —— 所有被引用的文件都真实存在。')
    if mismatch:
        print('\n路径不符 %d 处（文件在，但写的路径找不到它）：' % mismatch)
        for r in [x for x in rows if x['status'] == '路径不符']:
            print('  %s:%d  →  %s（实际：%s）' % (r['file'], r['line'], r['ref'],
                                               ', '.join(r['actual'])))

    print('\n共核对引用 %d 处 ｜ 缺失 %d ｜ 路径不符 %d%s' % (
        total, missing, mismatch, (' ｜ 按 --ignore 跳过 %d' % skipped) if skipped else ''))

    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(dict(total=total, missing=missing, mismatch=mismatch, rows=rows),
                      f, ensure_ascii=False, indent=1)
        print('明细已写入：%s' % a.json)

    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())
