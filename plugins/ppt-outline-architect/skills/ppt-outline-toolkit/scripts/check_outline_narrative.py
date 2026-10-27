#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""大纲叙事体检 —— 查「这份大纲是围绕结论重建的论证，还是把原文拆成了很多页」。

## 为什么需要它

55 页逐页看，是看不出拆页的。每一页单看都很合理：有标题、有要点、有数据。
但**把标题竖着连起来读**，立刻露馅 —— 读出来是一份目录（"项目背景/区位分析/历史文化/业态规划"），
而不是一段论证（"钱漏在哪 → 为什么漏 → 只有三处能堵 → 先堵哪个"）。

这件事人的眼睛做不到，机器一秒钟就能做。

## 它查八样

1. **标题竖读** —— 把全部页面标题按序排出，让你站在读者的角度连读一遍（核心功能）
2. **观点重复** —— 同一结论在多页反复出现（拆页最直接的证据）
3. **并列信号** —— 标题或核心观点里出现「另外 / 同时 / 还有」这类无推进关系的连接
4. **一页多问** —— 「本页唯一要解决的问题」里出现多个问号
5. **文案纯度** —— 「初步文案」字段装的是施工备忘/要点罗列，不是能进版面的成段文字
6. **幕式结构** —— 每段有没有幕名 / 对句 / 一字定性 / 释义（缺了就是文档标签，不是叙事单元）
7. **情绪曲线** —— 起/沉/扬/放/收 是否成一条能喘气的曲线（一路高亢 = 疲劳 = 记不住）
8. **本节输出** —— 每一节有没有留下一个可用的结论给下一节（区分论证式与资料式）

## 退出码

    0 = 未发现问题      1 = 有警告      2 = 有严重问题（重复/拆页信号）

用法：
    python check_outline_narrative.py 交付物/step3-02_PPT逐页脚本_v1.md
    python check_outline_narrative.py deck.md --json out.json --min-copy 80
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# ── 字段名容错（新旧格式都要认）─────────────────────────────────────────────
FIELD_ALIASES = {
    'title': ['页面标题 / 副标题', '页面标题', '标题 / 副标题', '标题'],
    'question': ['本页唯一要解决的问题', '唯一要解决的问题'],
    'claim': ['核心观点', '核心结论句', '核心观点（一句判断）'],
    'copy': ['初步文案', '初步文案（半成稿）'],
    'chart': ['数据或图表'],
    'visual': ['画面建议', '表达方式'],
    'note': ['口播重点', '演讲备注'],
    'image': ['本页图片需求', '图片需求'],
    'intent': ['页面意图'],
    'mood': ['情绪档', '情绪'],
    'section_out': ['本节输出'],
    # 幕式结构三件套
    'act_dup': ['对句'],
    'act_one': ['一字定性', '一字'],
    'act_gloss': ['释义'],
}

# 施工指令词：出现在「初步文案」里就说明这不是文案，是写给下游的备忘
INSTRUCTION_WORDS = ['已删', '已改', '待核', '页面类型', '本页须', '不误杀',
                     '保留并放大', '全篇禁用', '不得', '须按', '说明：']

# 「注：」只在句首/行首才算施工指令。
# 反例（必须放行）：「郑玄注："弱水出张掖。"」——「注」是注疏，是学术表达，不是备忘。
# 「说明：」不走这条规则：它在正常文案里几乎不出现，纯子串匹配的准确率已经够高；
# 一旦也做位置敏感，v1 的 P38/P40（「页脚说明：」）会漏检 —— 收紧误报不能换来漏检。
_INSTRUCTION_PATTERNS = [
    (re.compile(r'(?:^|[。！？；\n>\s])注：', re.M), '注：'),
]

# 并列信号：没有推进关系的连接词
PARALLEL_WORDS = ['另外还有', '另外', '同时也可以', '同时还', '还有一点', '除此之外']

# 叙事动作词（用于粗判这页在做什么，仅供人工参考）
NARRATIVE_HINTS = {
    '立靶': ['现状', '问题', '为什么', '根因', '漏', '痛点', '差距'],
    '归因': ['因为', '原因', '根子在', '结构', '机制'],
    '定点': ['只能', '三处', '可改', '改不了', '约束', '边界'],
    '给路': ['第一步', '路径', '分期', '节奏', '投入', '先做'],
    '兜底': ['风险', '前提', '不成立', '如果', '假设'],
}

PAGE_RE = re.compile(r'^#{2,4}\s*P(\d{2,3})\s*[·.、]?\s*(.*)$', re.M)
FIELD_RE = re.compile(r'^\s*[-*]\s*\*{0,2}(?:★\s*)?([^*：:\n]{2,24})\*{0,2}\s*[：:]\s*(.*)$')

# 幕（卷）：一级或二级标题里必须出现「卷」或「幕」字，避免误吃「# 2. 图位总表」这类文档标题
ACT_RE = re.compile(r'^#{1,2}\s*(?:第)?\s*([卷幕])\s*[一二三四五六七八九十\d]*\s*[·.、:：\s]?\s*(.*)$', re.M)

# 情绪五档
MOODS = ['起', '沉', '扬', '放', '收']


def norm_mood(s: str) -> str:
    """从「情绪档」字段里取出五档之一。认不出返回空串。"""
    s = strip_marks(s or '')
    for ch in s:
        if ch in MOODS:
            return ch
    return ''


def parse_acts(text: str):
    """解析幕式结构，返回 [{head, dup, one, gloss, pages, outs}]。"""
    acts = []
    ms = list(ACT_RE.finditer(text))
    for i, m in enumerate(ms):
        start = m.end()
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        body = text[start:end]
        keys = []
        one_val = ''
        for line in body.split('\n'):
            fm = FIELD_RE.match(line)
            if fm:
                k = fm.group(1).strip()
                keys.append(k)
                if any(a in k for a in FIELD_ALIASES['act_one']):
                    one_val = strip_marks(fm.group(2))[:2]
        joined = ' '.join(keys)
        acts.append(dict(
            head=(m.group(1) + ' ' + m.group(2).strip()).strip(' ·.、:：'),
            dup=any(a in joined for a in FIELD_ALIASES['act_dup']),
            one=any(a in joined for a in FIELD_ALIASES['act_one']),
            gloss=any(a in joined for a in FIELD_ALIASES['act_gloss']),
            one_val=one_val,
            pages=len(re.findall(r'^#{2,4}\s*P\d{2,3}', body, re.M)),
            outs=len(re.findall(r'本节输出', body)),
        ))
    return acts


def parse(md_path: str):
    """宽松解析逐页脚本，返回 [{page, title, fields{}}]。"""
    with open(md_path, encoding='utf-8') as f:
        text = f.read()

    pages = []
    matches = list(PAGE_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        head_title = m.group(2).strip()

        fields = {}
        cur_key = None
        for line in body.split('\n'):
            fm = FIELD_RE.match(line)
            if fm:
                key, val = fm.group(1).strip(), fm.group(2).strip()
                cur_key = key
                fields[key] = val
            elif cur_key and line.strip() and not line.strip().startswith('---'):
                # 字段值折行（列表项、续行）
                fields[cur_key] = (fields.get(cur_key, '') + '\n' + line.rstrip()).strip()
            elif not line.strip():
                cur_key = None

        def get(name):
            for alias in FIELD_ALIASES[name]:
                for k, v in fields.items():
                    if alias in k:
                        return v
            return ''

        pages.append(dict(page='P' + m.group(1), head=head_title,
                          title=get('title') or head_title,
                          question=get('question'), claim=get('claim'),
                          copy=get('copy'), chart=get('chart'),
                          visual=get('visual'), note=get('note'),
                          image=get('image'), mood=get('mood'),
                          section_out=get('section_out')))
    return pages


def strip_marks(s: str) -> str:
    """去掉 Markdown 标记与括注，只留可读文字。"""
    s = re.sub(r'\*\*|__|`', '', s)
    s = re.sub(r'（[^）]{0,60}）', '', s)
    return s.strip()


def main():
    ap = argparse.ArgumentParser(description='大纲叙事体检（拆页 / 重复 / 文案纯度）')
    ap.add_argument('md', help='逐页脚本 Markdown')
    ap.add_argument('--json', help='明细写 JSON')
    ap.add_argument('--min-copy', type=int, default=80, help='初步文案最低字数，默认 80')
    ap.add_argument('--no-list', action='store_true', help='不打印完整竖读清单')
    a = ap.parse_args()

    if not os.path.exists(a.md):
        sys.exit('[FATAL] 文件不存在：%s' % a.md)

    pages = parse(a.md)
    if not pages:
        sys.exit('[FATAL] 没解析出任何页面。检查是否用了 `### P01 · 标题` 这种格式')

    issues = []          # (级别, 页码, 问题)

    # ── ① 标题竖读（核心输出）─────────────────────────────────────────────
    if not a.no_list:
        print('=' * 74)
        print('标题竖读 —— 从读者的角度，把这 %d 个标题连起来读一遍' % len(pages))
        print('=' * 74)
        for p in pages:
            t = strip_marks(p['title'])[:52]
            print('  %s  %s' % (p['page'], t))
        print('=' * 74)
        print('  读出来像一段论证吗？')
        print('   · 像目录（"背景/分析/规划/路径/结语"）→ 这是拆页，回去重排')
        print('   · 像论证（"漏在哪/为什么/只能堵三处/先堵哪个"）→ 叙事成立')
        print('=' * 74)
        print()

    # ── ①b 字段完整性（新版七项必备，含图片需求）────────────────────────────────────────
    REQUIRED = [('question', '本页唯一要解决的问题'), ('claim', '核心观点'),
                ('chart', '数据或图表'), ('visual', '画面建议'),
                ('note', '口播重点'), ('copy', '初步文案'),
                ('image', '本页图片需求')]
    missing = {}
    for key, label in REQUIRED:
        lack = [p['page'] for p in pages if not (p[key] or '').strip()]
        if lack:
            missing[label] = lack
    if missing:
        print('[严重] 七项必备字段有缺项 —— 缺字段的页，下游只能自己补：')
        for label, lack in missing.items():
            print('   「%s」缺 %d 页：%s%s' % (label, len(lack),
                   ' '.join(lack[:12]), ' …' if len(lack) > 12 else ''))
            issues.append(('严重', ' '.join(lack[:12]), '缺字段：%s' % label))
        print('   → 尤其「数据或图表」「画面建议」「本页图片需求」缺失，等于把立象的活推给它自己猜。')
        print()

    # ── ② 观点重复 ─────────────────────────────────────────────────────────
    seen = {}
    for p in pages:
        key = strip_marks(p['claim'])[:26]
        if len(key) < 8:
            continue
        seen.setdefault(key, []).append(p['page'])
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    if dups:
        issues.append(('严重', '', '同一核心观点在多页重复出现 %d 组' % len(dups)))
        for k, v in list(dups.items())[:5]:
            print('[严重] 观点重复 %s：「%s…」' % ('/'.join(v), k))
            issues.append(('严重', '/'.join(v), '核心观点重复：%s' % k))

    # ── ③ 并列信号 ─────────────────────────────────────────────────────────
    for p in pages:
        blob = (p['title'] or '') + ' ' + (p['claim'] or '')
        for w in PARALLEL_WORDS:
            if w in blob:
                print('[警告] %s 出现并列连接「%s」——检查这页是否与前后构成推进关系' % (p['page'], w))
                issues.append(('警告', p['page'], '并列连接词：%s' % w))
                break

    # ── ④ 一页多问 ─────────────────────────────────────────────────────────
    q_multi = []
    for p in pages:
        q = p['question']
        if q and q.count('？') + q.count('?') > 1:
            q_multi.append(p['page'])
    if q_multi:
        print('\n[严重] 以下页的「本页唯一要解决的问题」有多个问号 —— 一页只许一个问题：')
        for pg in q_multi:
            print('   %s' % pg)
            issues.append(('严重', pg, '一页多问题'))

    # ── ⑤ 文案纯度 ─────────────────────────────────────────────────────────
    dirty, short, listy, empty = [], [], [], []
    for p in pages:
        c = p['copy'] or ''
        if not c.strip():
            empty.append(p['page'])
            continue
        body = strip_marks(c)
        hit = [w for w in INSTRUCTION_WORDS if w in c]
        hit += [label for pat, label in _INSTRUCTION_PATTERNS if pat.search(c)]
        if hit:
            dirty.append((p['page'], hit))
        elif len(body) < a.min_copy:
            # 条目化判断：多行且每行很短 → 是要点不是成段
            lines = [x.strip(' -*0123456789.') for x in c.split('\n') if x.strip()]
            lines = [x for x in lines if x]
            avg = sum(len(x) for x in lines) / max(1, len(lines))
            if len(lines) >= 3 and avg < 30:
                listy.append((p['page'], len(lines), int(avg)))
            else:
                short.append((p['page'], len(body)))

    if empty:
        print('\n[严重] 「初步文案」为空的页 %d 个：%s' % (len(empty), ' '.join(empty)))
        issues.append(('严重', ' '.join(empty), '文案为空'))
    if dirty:
        print('\n[严重] 文案字段里装的是施工指令，不是页面文案 —— 下游会照搬：')
        for pg, ws in dirty[:12]:
            print('   %s  命中：%s' % (pg, '、'.join(ws)))
            issues.append(('严重', pg, '文案含指令词：%s' % '、'.join(ws)))
        print('   → 这是真实事故的原型：55 页里有 29 页这样，最后 8 页骨架进了定稿。')
    if listy:
        print('\n[警告] 文案是条目罗列而非成段文字（%d 页）：' % len(listy))
        for pg, n, avg in listy[:10]:
            print('   %s  %d 条 · 平均每行 %d 字' % (pg, n, avg))
            issues.append(('警告', pg, '文案条目化'))
    if short:
        print('\n[警告] 文案偏短（<%d 字，%d 页）：%s' % (
            a.min_copy, len(short), ' '.join(p for p, _ in short[:14])))
        for pg, n in short:
            issues.append(('警告', pg, '文案过短 %d 字' % n))

    # ── ⑥ 图片（文旅类汇报的生死线）──────────────────────────────────────
    tiers = {'P': [], 'S': [], 'O': []}
    no_tier, vague, wrong_src = [], [], []
    gen_able = 0
    for p in pages:
        v = (p['image'] or '').strip()
        if not v:
            continue
        # 判档：字段开头第一个独立的 P / S / O
        m = re.search(r'(?<![A-Za-z])([PSO])(?![A-Za-z])', v[:24])
        if m:
            tiers[m.group(1)].append(p['page'])
        else:
            no_tier.append(p['page'])
            if re.search(r'可配图|可有配图|适当配图|酌情|看情况', v):
                vague.append(p['page'])
        # 图源自相矛盾：本该自己画的，却挂着等甲方
        if re.search(r'分析图|意向图', v) and re.search(r'待甲方|甲方提供|等甲方|待外部', v):
            wrong_src.append(p['page'])
        if re.search(r'分析图|意向图', v):
            gen_able += 1

    n_all = len(pages)
    if no_tier:
        print('[严重] 图片需求没落到 P / S / O 三档 —— %d 页%s：%s' % (
            len(no_tier), '（含含糊表述）' if vague else '',
            ' '.join(no_tier[:12]) + (' …' if len(no_tier) > 12 else '')))
        print('   → 写「本页可配图」等于没判。判据只有一句：删掉这张图，核心观点还成立吗？')
        issues.append(('严重', ' '.join(no_tier[:12]), '图片需求未分档'))
        print()

    if tiers['P'] or tiers['S'] or tiers['O']:
        ratio = len(tiers['P']) / n_all if n_all else 0
        print('图片分档：P（必须有）%d 页 ｜ S（应该有）%d 页 ｜ O（可选）%d 页' % (
            len(tiers['P']), len(tiers['S']), len(tiers['O'])))
        print('   P 档占比 %.0f%%（文旅/商业综合体类底线 35%%）' % (ratio * 100))
        if ratio < 0.35:
            print('   [严重] P 档不足 —— 这份汇报不是"以图论证"型，是资料汇编')
            issues.append(('严重', '', 'P 档占比 %.0f%% < 35%%' % (ratio * 100)))
        else:
            print('   ✓ 达到以图论证的底线')
        print('   可自行生成（分析图 + 意向图）%d 张%s' % (
            gen_able, '' if gen_able else '  ← [严重] 全是"等甲方"，落版必然 0 图'))
        if not gen_able:
            issues.append(('严重', '', '无一张可自行生成的图'))
        print()

    if wrong_src:
        print('[严重] 图源标错 —— %d 页把「能自己画的」标成了等外部：%s' % (
            len(wrong_src), ' '.join(wrong_src[:12])))
        print('   → 分析图基于已核验数据自绘、意向图可 AI 生成。标了这两级就不许写"待甲方"。')
        issues.append(('严重', ' '.join(wrong_src[:12]), '分析图/意向图误标为待外部'))
        print()

    if not tiers['P'] and not tiers['S'] and not tiers['O'] and not no_tier:
        print('[严重] 全篇没有任何图片需求 —— 逐页脚本里没有「本页图片需求」字段')
        print('   → 下游只能忠实执行一份没有图片需求的脚本。这是 0 图汇报的根因。')
        issues.append(('严重', '', '全篇无图片需求字段'))
        print()

    # ── ⑦ 幕式结构（幕名 / 对句 / 一字定性 / 释义）────────────────────────
    with open(a.md, encoding='utf-8') as f:
        _text = f.read()
    acts = parse_acts(_text)

    if not acts:
        print('[警告] 未使用幕式结构 —— 全篇没有「卷 / 幕」标题')
        print('   → 若只有"第一部分 / 第二部分"，或干脆直接就是页，听众记不住任何一段。')
        print('   → 至少给每一段一个幕名（四字·四字）+ 一句对句 + 一个字的定性。')
        issues.append(('警告', '', '未使用幕式结构'))
        print()
    else:
        miss = [x for x in acts if not (x['dup'] and x['one'] and x['gloss'])]
        if miss:
            print('[严重] 幕名三件套不齐 —— %d 个幕缺「对句 / 一字定性 / 释义」：' % len(miss))
            for x in miss[:8]:
                lack = []
                if not x['dup']:
                    lack.append('对句')
                if not x['one']:
                    lack.append('一字定性')
                if not x['gloss']:
                    lack.append('释义')
                print('   %-26s 缺：%s' % (x['head'][:24], '、'.join(lack)))
            print('   → 幕名是文档标签还是叙事单元，就看这三件有没有。一字定性写不出 = 这段性质没想清。')
            issues.append(('严重', ' '.join(x['head'][:8] for x in miss[:5]), '幕名三件套不齐'))
            print()
        else:
            print('幕式结构：%d 幕，三件套齐全' % len(acts))

        dup_one = {}
        for x in acts:
            if x['one_val']:
                dup_one.setdefault(x['one_val'], []).append(x['head'][:12])
        d2 = {k: v for k, v in dup_one.items() if len(v) > 1}
        if d2:
            print('[严重] 一字定性重复 —— 两段用同一个字，说明它们其实是一段：')
            for k, v in d2.items():
                print('   「%s」：%s' % (k, ' / '.join(v)))
            issues.append(('严重', '', '一字定性重复 %d 组' % len(d2)))
            print()
        print()

    # ── ⑧ 情绪曲线（起 / 沉 / 扬 / 放 / 收）──────────────────────────────
    moods = [(p['page'], norm_mood(p['mood'])) for p in pages]
    have = [(pg, m) for pg, m in moods if m]
    if not have:
        print('[警告] 全篇没有标「情绪档」—— 45 分钟的节奏没有设计过')
        print('   → 逐页标 起/沉/扬/放/收。一路高亢 = 疲劳 = 记不住；没有"沉"是不给喘息。')
        issues.append(('警告', '', '未标情绪档'))
        print()
    elif len(have) < len(pages) * 0.8:
        lack = [pg for pg, m in moods if not m]
        print('[警告] 「情绪档」标了 %d / %d 页，%d 页空着：%s' % (
            len(have), len(pages), len(lack), ' '.join(lack[:12])))
        issues.append(('警告', ' '.join(lack[:12]), '情绪档未标全'))
        print()
    else:
        seq = [m for _, m in have]
        # 硬规则 ①：相邻三页不同档
        trip = []
        for i in range(len(seq) - 2):
            if seq[i] == seq[i + 1] == seq[i + 2]:
                trip.append(have[i + 1][0])
        if trip:
            print('[严重] 连续三页同一情绪档 —— %d 处：%s' % (len(trip), ' '.join(trip[:10])))
            print('   → 连读三页"扬"观众会疲劳；三页"沉"会走神。中间插一页换档。')
            issues.append(('严重', ' '.join(trip[:10]), '连续三页同情绪档'))
            print()
        # 硬规则 ②：至少一次沉、一次放
        for need in ('沉', '放'):
            if need not in seq:
                print('[严重] 全篇没有「%s」档 —— %s' % (
                    need, '没给喘息，甲方听不到 20 分钟就累了' if need == '沉'
                    else '没有让人松下来掏钱的段落，产品与收益页转化率会低'))
                issues.append(('严重', '', '全篇无「%s」档' % need))
                print()
        # 硬规则 ③：扬连续 ≤ 3
        run = best = 0
        for m in seq:
            run = run + 1 if m == '扬' else 0
            best = max(best, run)
        if best > 3:
            print('[严重] 「扬」连续 %d 页 —— 超过 3 页，高潮太长等于没有高潮' % best)
            issues.append(('严重', '', '「扬」连续 %d 页' % best))
            print()
        # 硬规则 ④：末页必须是收
        if seq and seq[-1] != '收':
            print('[警告] 最后一页情绪档是「%s」，不是「收」—— 收尾还在高潮，等于没给结论' % seq[-1])
            issues.append(('警告', have[-1][0], '末页情绪档非「收」'))
            print()
        if not trip and '沉' in seq and '放' in seq and best <= 3:
            print('情绪曲线：%s ｜ 四条硬规则通过' % ' '.join(seq[:20]))
            print()

    # ── ⑨ 本节输出（每节有没有留结论给下一节）────────────────────────────
    if acts:
        silent = [x for x in acts if x['pages'] >= 3 and x['outs'] == 0]
        if silent:
            print('[警告] 下列幕有 %d 页以上、却没有一处「本节输出」：' % 3)
            for x in silent[:8]:
                print('   %-26s %d 页' % (x['head'][:24], x['pages']))
            print('   → 区分"论证式"和"资料式"的就是这一条：每节结束要留一个可用的结论给下一节。')
            issues.append(('警告', ' '.join(x['head'][:8] for x in silent[:5]), '幕内无本节输出'))
            print()
        else:
            total_out = sum(x['outs'] for x in acts)
            print('本节输出：全篇 %d 处，%d 幕均有' % (total_out, len(acts)))
            print()

    # ── 汇总 ───────────────────────────────────────────────────────────────
    crit = [i for i in issues if i[0] == '严重']
    warn = [i for i in issues if i[0] == '警告']
    print('\n' + '-' * 74)
    print('共 %d 页 ｜ 严重 %d 条 ｜ 警告 %d 条' % (len(pages), len(crit), len(warn)))
    if not crit and not warn:
        print('结论：叙事与文案两项体检通过。')
    else:
        print('结论：需处理。优先看「严重」——最后一条判据永远是人读一遍标题链。')
        print('       本脚本只能指出症状，重排叙事需要人（析纲）来判。')

    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(dict(pages=pages, issues=issues,
                           critical=len(crit), warning=len(warn)),
                      f, ensure_ascii=False, indent=1)
        print('明细已写入：%s' % a.json)

    return 0 if not issues else (2 if crit else 1)


if __name__ == '__main__':
    sys.exit(main())
