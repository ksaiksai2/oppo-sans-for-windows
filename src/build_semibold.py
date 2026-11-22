# -*- coding: utf-8 -*-
"""从 base-Regular 派生一个 Semibold 面。

为什么需要：Windows 请求「半粗（600）」时，如果家族里只有 400 和 700 两个面，
DirectWrite 只能落到 700 —— 界面里所有标题（通知标题、卡片大标题、设置小节）
都比手机上的 SemiBold 粗一档。补一个 600 的面，请求就能精确命中。

家族名用 "Microsoft YaHei UI"：壳界面的中文回退走的是 FontLink ->
`MSYH.TTC,Microsoft YaHei UI`，权重会传下来，所以这个家族必须有 600 面。
"""
import os
import sys

from fontTools.ttLib import TTFont


def build(base_ttf, out_ttf):
    f = TTFont(base_ttf, lazy=False)

    family = "Microsoft YaHei UI"
    sub = "Semibold"
    full = family + " " + sub
    ps = "MicrosoftYaHeiUI-Semibold"

    # 清掉旧的名字记录，按目标重建
    f["name"].names = []
    for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
        for nid, val in ((1, family), (2, sub), (3, full), (4, full), (6, ps),
                         (16, family), (17, sub)):
            f["name"].setName(val, nid, pid, eid, lid)

    # 版权/说明从原表里捞出来（不覆盖）
    src = TTFont(base_ttf, lazy=True)
    for rec in src["name"].names:
        if rec.nameID in (0, 7, 8, 9, 10, 11, 12, 13, 14, 19):
            f["name"].names.append(rec)
    src.close()

    f["OS/2"].usWeightClass = 600
    # 清掉 Bold(5) / Regular(6) 两个位，保留其余
    f["OS/2"].fsSelection = f["OS/2"].fsSelection & ~((1 << 5) | (1 << 6))
    f["head"].macStyle = 0

    f.save(out_ttf, reorderTables=False)
    size = os.path.getsize(out_ttf) / 1048576.0
    print("  msyhsc.ttf  <- %s  家族=%s / 子族=%s / 字重600  %.2fMB"
          % (os.path.basename(base_ttf), family, sub, size))
    return out_ttf


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else None
    if not base or not out:
        print("用法: build_semibold.py <base-Regular.ttf> <msyhsc.ttf>")
        sys.exit(1)
    build(base, out)
