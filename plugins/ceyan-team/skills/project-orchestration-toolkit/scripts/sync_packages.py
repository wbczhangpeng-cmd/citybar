# -*- coding: utf-8 -*-
"""全景同步：以 ceyan-team 为正本，同步到 7 个独立包 + project-orchestrator。
   - persona：保留各包自己的 frontmatter（name 不同），正文取团内
   - toolkit：双向并集（一方独有→合并过去）；同名冲突→团内为准；跳过 __pycache__
用法: python sync_all.py [--dry]
"""
import io
import os
import shutil
import hashlib
import sys

BASE = r"C:\Users\PC\.workbuddy\plugins\marketplaces\my-experts\plugins"
TEAM = os.path.join(BASE, "ceyan-team")

# (包名, 团内对应 persona 名)
PAIRS = [
    ("project-orchestrator", "ceyan-lead"),
    ("project-positioning-strategist", "project-positioning-strategist"),
    ("business-logic-reviewer", "business-logic-reviewer"),
    ("ppt-outline-architect", "ppt-outline-architect"),
    ("copy-polisher", "copy-polisher"),
    ("visual-design-architect", "visual-design-architect"),
    ("ppt-producer", "ppt-producer"),
    ("ppt-refiner", "ppt-refiner"),
]
# (toolkit 名, 独立包名)
TK = [
    ("business-review-toolkit", "business-logic-reviewer"),
    ("copy-polish-toolkit", "copy-polisher"),
    ("ppt-generate-toolkit", "ppt-producer"),
    ("ppt-outline-toolkit", "ppt-outline-architect"),
    ("ppt-refine-toolkit", "ppt-refiner"),
    ("project-orchestration-toolkit", "project-orchestrator"),
    ("visual-design-toolkit", "visual-design-architect"),
]

DRY = "--dry" in sys.argv


def read(p):
    return io.open(p, encoding="utf-8").read()


def split_fm(t):
    if not t.startswith("---"):
        return "", t
    i = t.index("\n---", 3)
    return t[:i + 4], t[i + 4:]


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def walk(d):
    out = {}
    for dp, dns, fs in os.walk(d):
        dns[:] = [x for x in dns if x != "__pycache__"]
        for f in fs:
            if f.endswith(".pyc"):
                continue
            p = os.path.join(dp, f)
            out[os.path.relpath(p, d).replace(os.sep, "/")] = p
    return out


def main():
    log = []
    # ---------- A. persona ----------
    for pkg, tm in PAIRS:
        dst = os.path.join(BASE, pkg, "agents", pkg + ".md")
        src = os.path.join(TEAM, "agents", tm + ".md")
        fm_dst, body_dst = split_fm(read(dst))
        fm_src, body_src = split_fm(read(src))
        new = fm_dst + body_src
        act = "同" if read(dst) == new else "改"
        log.append("persona  %-30s %-4s 正文 %d → %d 字节" % (pkg, act, len(body_dst), len(body_src)))
        if act == "改" and not DRY:
            io.open(dst, "w", encoding="utf-8", newline="").write(new)

    # ---------- B. toolkit ----------
    for tk, pkg in TK:
        A = os.path.join(TEAM, "skills", tk)
        B = os.path.join(BASE, pkg, "skills", tk)
        fa, fb = walk(A), walk(B)
        only_a = sorted(set(fa) - set(fb))
        only_b = sorted(set(fb) - set(fa))
        conf = sorted(k for k in set(fa) & set(fb) if md5(fa[k]) != md5(fb[k]))
        if only_a:
            log.append("  %-30s 团内独有 %d 项 → 并入独立" % (tk, len(only_a)))
            for k in only_a:
                log.append("      + %s" % k)
        if only_b:
            log.append("  %-30s 独立独有 %d 项 → 并入团内" % (tk, len(only_b)))
            for k in only_b:
                log.append("      + %s" % k)
        if conf:
            log.append("  %-30s 同名冲突 %d 项 → 团内为准" % (tk, len(conf)))
            for k in conf:
                log.append("      ≠ %s" % k)
        if DRY:
            continue
        for k in only_a:
            t = os.path.join(B, k)
            os.makedirs(os.path.dirname(t), exist_ok=True)
            shutil.copy2(fa[k], t)
        for k in only_b:
            t = os.path.join(A, k)
            os.makedirs(os.path.dirname(t), exist_ok=True)
            shutil.copy2(fb[k], t)
        for k in conf:
            shutil.copy2(fa[k], fb[k])

    print("\n".join(log))
    print("\n%s" % ("—— 以上为演练，未写入 ——" if DRY else "—— 已写入 ——"))


if __name__ == "__main__":
    main()
