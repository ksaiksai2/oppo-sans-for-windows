# -*- coding: utf-8 -*-
"""把经典 Segoe UI（segoeui.ttf 那一家）的拉丁字形换成 OPPO。

为什么要这一层：Win11 的开始菜单 / 任务栏面板 / 资源管理器的英文并不使用
"Segoe UI Variable"，而是经典 "Segoe UI"。前面替换 SegUIVar 之后英文依旧偏细，
GDI 取字形验证过：Variable 四族已是我们（md5 0d6cf68c），英文却没变 → 说明走的是这份。

字重映射（按用户选择，英文整体比中文轻一档）：
    Regular   <- OPPO 500   （比原版 Segoe Regular 略重，网页长文仍好读）
    Bold      <- OPPO 700
    Semibold  <- OPPO 600
    Light     <- OPPO 300
    Semilight <- OPPO 400

不处理斜体：OPPO Sans 没有真斜体，做出来是伪斜体，反而更丑。
"""
import os
import sys

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0"
SRCDIR = os.path.join(ROOT, "build")
OUTDIR = os.path.join(ROOT, "replacement", "segclassic")
WINFONTS = r"C:\Windows\Fonts"
ANCHOR = "H"

SRC = {
    300: "OPPOSans40-Light.ttf",
    400: "OPPOSans40-Regular.ttf",
    500: "OPPOSans40-Medium.ttf",
    600: "OPPOSans40-SemiBold.ttf",
    700: "OPPOSans40-Bold.ttf",
}
# (目标文件, 子家族名, OPPO 字重, OS/2 字重值)
TARGETS = [
    ("segoeui.ttf",   "Regular",   500, 400),
    ("segoeuib.ttf",  "Bold",      700, 700),
    ("seguisb.ttf",   "Semibold",  600, 600),
    ("segoeuil.ttf",  "Light",     300, 300),
    ("segoeuisl.ttf", "Semilight", 400, 350),
]
OPPO_COPYRIGHT = "Copyright 2024 Guangdong OPPO Mobile Telecommunications Corp., Ltd. OPPO Sans Fonts."
DESC = ("OPPO Sans 4.0 Latin outlines, metrics-aligned to Segoe UI for local system UI replacement. "
        "Derived font for personal use only; not for redistribution.")


def bbox_em(font, ch):
    upem = font["head"].unitsPerEm
    g = font["glyf"][font.getBestCmap()[ord(ch)]]
    g.recalcBounds(font["glyf"])
    return (g.xMin / upem, g.yMin / upem, g.xMax / upem, g.yMax / upem)


def build(out_name, subfamily, oppo_w, os2_w):
    ref = TTFont(os.path.join(WINFONTS, out_name))
    src = TTFont(os.path.join(SRCDIR, SRC[oppo_w]))

    sb, rb = bbox_em(src, ANCHOR), bbox_em(ref, ANCHOR)
    sx = (rb[2] - rb[0]) / (sb[2] - sb[0])
    sy = (rb[3] - rb[1]) / (sb[3] - sb[1])
    dx = rb[0] - sb[0] * sx
    dy = rb[1] - sb[1] * sy
    k = ref["head"].unitsPerEm / src["head"].unitsPerEm
    KX, KY, DX, DY = sx * k, sy * k, dx * ref["head"].unitsPerEm, dy * ref["head"].unitsPerEm

    order = src.getGlyphOrder()
    gs = src.getGlyphSet()
    glyf = src["glyf"]
    new = {}
    for name in order:
        rec = DecomposingRecordingPen(gs)
        gs[name].draw(TransformPen(rec, (KX, 0, 0, KY, DX, DY)))
        pen = TTGlyphPen(None)
        rec.replay(pen)
        new[name] = pen.glyph()
    glyf.glyphs = new

    # 符号尺寸对齐（● ○ · 这类 OPPO 画得比 Segoe 大，会又大又叠）
    ref_gs = ref.getGlyphSet()
    ref_cmap = ref.getBestCmap()
    ref_hmtx = ref["hmtx"]
    resync = 0
    for cp, gn in src.getBestCmap().items():
        if cp < 0x20 or cp not in ref_cmap:
            continue
        if not (0x2000 <= cp <= 0x2BFF or 0x3000 <= cp <= 0x303F or
                0xFE30 <= cp <= 0xFE6F or 0xFF00 <= cp <= 0xFF65):
            continue
        g = new[gn]
        g.recalcBounds(glyf)
        if g.numberOfContours == 0:
            continue
        rgn = ref_cmap[cp]
        rg = ref["glyf"][rgn]
        rg.recalcBounds(ref["glyf"])
        h1, h2 = g.yMax - g.yMin, rg.yMax - rg.yMin
        w1, w2 = g.xMax - g.xMin, rg.xMax - rg.xMin
        if h2 <= 0 or w2 <= 0:
            continue
        adv = ref_hmtx[rgn][0]
        if (h1 / h2 > 1.15) or (w1 / w2 > 1.15) or (w1 > adv * 0.99) or (h1 / h2 < 0.87) or (w1 / w2 < 0.87):
            rec = DecomposingRecordingPen(ref_gs)
            ref_gs[rgn].draw(TransformPen(rec, (1, 0, 0, 1, 0, 0)))
            pen = TTGlyphPen(None)
            rec.replay(pen)
            new[gn] = pen.glyph()
            resync += 1

    # 字宽全部取 Segoe
    metrics = {}
    reverse = {}
    for cp, gn in src.getBestCmap().items():
        reverse.setdefault(gn, cp)
    for name in order:
        g = new[name]
        g.recalcBounds(glyf)
        lsb = getattr(g, "xMin", 0) if g.numberOfContours != 0 else 0
        cp = reverse.get(name)
        adv = ref_hmtx[ref_cmap[cp]][0] if (cp is not None and cp in ref_cmap) else int(round(src["hmtx"][name][0] * KX))
        metrics[name] = (adv, lsb)
    src["hmtx"].metrics = metrics

    h, o = src["hhea"], src["OS/2"]
    rh, ro = ref["hhea"], ref["OS/2"]
    h.ascent, h.descent, h.lineGap = rh.ascent, rh.descent, rh.lineGap
    o.sTypoAscender, o.sTypoDescender, o.sTypoLineGap = ro.sTypoAscender, ro.sTypoDescender, ro.sTypoLineGap
    o.usWinAscent, o.usWinDescent = ro.usWinAscent, ro.usWinDescent
    o.xAvgCharWidth = ro.xAvgCharWidth
    o.usWeightClass = os2_w
    o.fsSelection = (o.fsSelection & 0b10000000) | (0b100000 if os2_w >= 700 else 0b1000000)
    src["head"].unitsPerEm = ref["head"].unitsPerEm
    src["head"].macStyle = 1 if os2_w >= 700 else 0

    # 名字：家族 Segoe UI，子家族按目标文件
    src["name"].names = []
    for rec in ref["name"].names:
        src["name"].names.append(rec)
    full = "Segoe UI" if subfamily == "Regular" else "Segoe UI " + subfamily
    ps = "SegoeUI" if subfamily == "Regular" else "SegoeUI-" + subfamily
    for rec in src["name"].names:
        def put(t):
            rec.string = t.encode("utf-16-be" if rec.platformID in (0, 3) else "latin-1")
        if rec.nameID == 0:
            put(OPPO_COPYRIGHT)
        elif rec.nameID == 10:
            put(DESC)
        elif rec.nameID in (2, 17):
            put(subfamily)
        elif rec.nameID in (3, 4):
            put(full)
        elif rec.nameID == 6:
            put(ps)

    src["post"].formatType = 3.0
    for tag in ("DSIG", "STAT", "fvar", "gvar", "HVAR", "MVAR", "avar", "cvar",
                "cvt ", "fpgm", "prep", "vhea", "vmtx", "hdmx", "VDMX", "LTSH"):
        if tag in src:
            del src[tag]

    # 只保留 Segoe 覆盖的字符，中文继续回落雅黑
    from fontTools import subset as _subset
    opts = _subset.Options()
    opts.drop_tables += ["GSUB", "GPOS", "GDEF"]
    opts.layout_features = []
    opts.name_IDs = ["*"]
    opts.name_legacy = True
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.recalc_bounds = True
    sub = _subset.Subsetter(options=opts)
    sub.populate(unicodes=[cp for cp in ref_cmap if cp >= 0x20])
    sub.subset(src)

    xs = [new[n].xMin for n in order if new[n].numberOfContours != 0]
    ys = [new[n].yMin for n in order if new[n].numberOfContours != 0]
    x2 = [new[n].xMax for n in order if new[n].numberOfContours != 0]
    y2 = [new[n].yMax for n in order if new[n].numberOfContours != 0]
    head = src["head"]
    head.xMin, head.yMin, head.xMax, head.yMax = min(xs), min(ys), max(x2), max(y2)
    h.advanceWidthMax = max(a for a, _ in metrics.values())
    h.minLeftSideBearing = min(l for _, l in metrics.values())
    h.numberOfHMetrics = len(order)

    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, out_name)
    src.save(out, reorderTables=False)
    print("  %-14s <- OPPO %d  %.2fMB  符号对齐 %d" % (out_name, oppo_w, os.path.getsize(out) / 1048576.0, resync))
    return out_name, ref, out


if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    print("=== 经典 Segoe UI 替换 ===")
    results = []
    for t in TARGETS:
        results.append(build(*t))
    print("\n=== 校验 ===")
    for name, ref, out in results:
        f = TTFont(out)
        cm, rcm = f.getBestCmap(), ref.getBestCmap()
        rg = ref["glyf"][rcm[ord("A")]]
        rg.recalcBounds(ref["glyf"])
        g = f["glyf"][cm[ord("A")]]
        g.recalcBounds(f["glyf"])
        same_size = abs((g.xMax - g.xMin) - (rg.xMax - rg.xMin)) <= 2
        adv_same = f["hmtx"][cm[ord("A")]][0] == ref["hmtx"][rcm[ord("A")]][0]
        print("  %-14s A 尺寸%s 字宽%s" % (name, "一致" if same_size else "差 %d" % ((g.xMax - g.xMin) - (rg.xMax - rg.xMin)),
                                          "一致" if adv_same else "不一致"))
    print("DONE")
