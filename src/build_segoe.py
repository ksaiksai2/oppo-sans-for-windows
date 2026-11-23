# -*- coding: utf-8 -*-
"""把 Segoe UI Variable 换成 OPPO 的拉丁字形，专治 Win11 开始菜单 / 任务栏面板里
「中文很粗、英文很细」的错位。

这两个界面是 XAML，英文走 SegUIVar.ttf（family = Segoe UI Variable，带 wght/opsz 两个
可变轴），中文才回落到微软雅黑。所以只换雅黑，英文那半边救不到。

做法同雅黑：把 OPPO 的拉丁字形按比例对齐到 Segoe 的设计空间（用 H 的高度/位置做基准），
字宽全取 Segoe 的（排版零位移），度量全取 Segoe 的。
输出为双 face TTC（Regular + Bold），两个 face 都是 OPPO 的粗字形，
避免 DirectWrite 在请求 600/700 时对单面字体做二次合成加粗（那样会糊）。
"""
import os
import sys

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont, TTCollection

D = r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\build"
OUT = r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\replacement"
SEGOE = r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\backup\SegUIVar.ttf"
ANCHOR = "H"
SRC = {
    400: "OPPOSans40-Regular.ttf",
    500: "OPPOSans40-Medium.ttf",
    600: "OPPOSans40-SemiBold.ttf",
    700: "OPPOSans40-Bold.ttf",
}
ALIASES = ["Segoe UI Variable", "Segoe UI Variable Text",
           "Segoe UI Variable Display", "Segoe UI Variable Small"]
VARIANTS = {"w400": (400, 700), "w500": (500, 700), "w600": (600, 700), "w700": (700, 700)}
OPPO_COPYRIGHT = "Copyright 2024 Guangdong OPPO Mobile Telecommunications Corp., Ltd. OPPO Sans Fonts."
DESC = ("OPPO Sans 4.0 Latin outlines, metrics-aligned to Segoe UI Variable for local shell UI replacement. "
        "Derived font for personal use only; not for redistribution.")


def bbox_em(font, ch):
    upem = font["head"].unitsPerEm
    g = font["glyf"][font.getBestCmap()[ord(ch)]]
    g.recalcBounds(font["glyf"])
    return (g.xMin / upem, g.yMin / upem, g.xMax / upem, g.yMax / upem)


def build_face(src_ttf, ref, weight, style, verbose=True):
    src = TTFont(src_ttf)
    s_upem, r_upem = src["head"].unitsPerEm, ref["head"].unitsPerEm

    sb, rb = bbox_em(src, ANCHOR), bbox_em(ref, ANCHOR)
    sx = (rb[2] - rb[0]) / (sb[2] - sb[0])
    sy = (rb[3] - rb[1]) / (sb[3] - sb[1])
    dx = rb[0] - sb[0] * sx
    dy = rb[1] - sb[1] * sy
    k = r_upem / s_upem
    KX, KY, DX, DY = sx * k, sy * k, dx * r_upem, dy * r_upem
    if verbose:
        print("    sx=%.4f sy=%.4f dx=%+.4f dy=%+.4f" % (sx, sy, dx, dy))

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

    # 符号尺寸对齐：● ○ · 这类几何符号 OPPO 画得比 Segoe 大 1.4~1.6 倍，
    # 而字宽取的是 Segoe，直接用会又大又重叠（登录界面密码圆点就是这样）。
    # 偏差过大的标点/符号一律换成 Segoe 的字形。
    ref_gs0 = ref.getGlyphSet()
    ref_cmap0 = ref.getBestCmap()
    ref_hmtx0 = ref["hmtx"]
    resync = 0
    for cp, gn in src.getBestCmap().items():
        if cp < 0x20 or cp not in ref_cmap0:
            continue
        if not (0x2000 <= cp <= 0x2BFF or 0x3000 <= cp <= 0x303F or
                0xFE30 <= cp <= 0xFE6F or 0xFF00 <= cp <= 0xFF65):
            continue
        g = new[gn]
        g.recalcBounds(glyf)
        if g.numberOfContours == 0:
            continue
        rgn = ref_cmap0[cp]
        rg = ref["glyf"][rgn]
        rg.recalcBounds(ref["glyf"])
        h1, h2 = g.yMax - g.yMin, rg.yMax - rg.yMin
        w1, w2 = g.xMax - g.xMin, rg.xMax - rg.xMin
        if h2 <= 0 or w2 <= 0:
            continue
        adv = ref_hmtx0[rgn][0]
        if (h1 / h2 > 1.15) or (w1 / w2 > 1.15) or (w1 > adv * 0.99) or (h1 / h2 < 0.87) or (w1 / w2 < 0.87):
            rec = DecomposingRecordingPen(ref_gs0)
            ref_gs0[rgn].draw(TransformPen(rec, (1, 0, 0, 1, 0, 0)))
            pen = TTGlyphPen(None)
            rec.replay(pen)
            new[gn] = pen.glyph()
            resync += 1
    if verbose:
        print("    符号尺寸对齐：替换 %d 个" % resync)

    # 补 Segoe 有、OPPO 没有的字符（设计空间已对齐，直接搬）
    ref_cmap = ref.getBestCmap()
    ref_gs = ref.getGlyphSet()
    src_cmap = src.getBestCmap()
    added = 0
    for cp in ref_cmap:
        if cp in src_cmap or cp < 0x20:
            continue
        nm = "sg%05X" % cp
        if nm in new:
            continue
        rec = DecomposingRecordingPen(ref_gs)
        ref_gs[ref_cmap[cp]].draw(TransformPen(rec, (1, 0, 0, 1, 0, 0)))
        pen = TTGlyphPen(None)
        rec.replay(pen)
        new[nm] = pen.glyph()
        order.append(nm)
        added += 1
    glyf.glyphs = new
    src.setGlyphOrder(order)
    glyf.glyphOrder = order

    for table in src["cmap"].tables:
        if not table.isUnicode():
            continue
        for cp in ref_cmap:
            if cp in src_cmap or cp < 0x20:
                continue
            if table.format == 4 and cp > 0xFFFF:
                continue
            table.cmap[cp] = "sg%05X" % cp

    # 字宽全取 Segoe
    ref_hmtx = ref["hmtx"]
    src_hmtx = src["hmtx"]
    reverse = {}
    for cp, gn in src.getBestCmap().items():
        reverse.setdefault(gn, cp)
    metrics = {}
    for name in order:
        g = new[name]
        g.recalcBounds(glyf)
        lsb = getattr(g, "xMin", 0) if g.numberOfContours != 0 else 0
        cp = reverse.get(name)
        adv = None
        if name.startswith("sg"):
            cp2 = int(name[2:], 16)
            if cp2 in ref_cmap:
                adv = ref_hmtx[ref_cmap[cp2]][0]
        elif cp is not None and cp in ref_cmap:
            adv = ref_hmtx[ref_cmap[cp]][0]
        if adv is None:
            adv = int(round(src_hmtx[name][0] * KX))
        metrics[name] = (adv, lsb)
    src["hmtx"].metrics = metrics

    h, o = src["hhea"], src["OS/2"]
    rh, ro = ref["hhea"], ref["OS/2"]
    h.ascent, h.descent, h.lineGap = rh.ascent, rh.descent, rh.lineGap
    o.sTypoAscender, o.sTypoDescender, o.sTypoLineGap = ro.sTypoAscender, ro.sTypoDescender, ro.sTypoLineGap
    o.usWinAscent, o.usWinDescent = ro.usWinAscent, ro.usWinDescent
    # x-height / cap-height: DirectWrite/XAML 用它算行内视觉中心，
    # 不复制会让 Edge 自带 UI 的文字相对图标偏高（网页 CSS 排版不受影响）。
    o.sxHeight, o.sCapHeight = ro.sxHeight, ro.sCapHeight
    o.xAvgCharWidth = ro.xAvgCharWidth
    o.usWeightClass = weight
    o.fsSelection = (o.fsSelection & 0b10000000) | (0b100000 if weight == 700 else 0b1000000)

    head = src["head"]
    head.unitsPerEm = r_upem
    head.macStyle = 1 if weight == 700 else 0

    # 名字：照抄 Segoe 的，只换版权/说明
    src["name"].names = []
    for rec in ref["name"].names:
        src["name"].names.append(rec)
    # Bold 面必须改掉子家族名，否则两个面都叫 Regular，Windows 会当成重复面
    full = "Segoe UI Variable" if style == "Regular" else "Segoe UI Variable " + style
    ps = "SegoeUIVariable" if style == "Regular" else "SegoeUIVariable-" + style
    for rec in src["name"].names:
        def put(text):
            rec.string = text.encode("utf-16-be" if rec.platformID in (0, 3) else "latin-1")
        if rec.nameID == 0:
            put(OPPO_COPYRIGHT)
        elif rec.nameID == 10:
            put(DESC)
        elif rec.nameID in (2, 17):
            put(style)
        elif rec.nameID in (4, 3):
            put(full)
        elif rec.nameID == 6:
            put(ps)

    src["post"].formatType = 3.0
    for tag in ("DSIG", "STAT", "fvar", "gvar", "HVAR", "MVAR", "avar", "cvar",
                "cvt ", "fpgm", "prep", "vhea", "vmtx", "hdmx", "VDMX", "LTSH"):
        if tag in src:
            del src[tag]

    xs = [new[n].xMin for n in order if new[n].numberOfContours != 0]
    ys = [new[n].yMin for n in order if new[n].numberOfContours != 0]
    x2 = [new[n].xMax for n in order if new[n].numberOfContours != 0]
    y2 = [new[n].yMax for n in order if new[n].numberOfContours != 0]
    head.xMin, head.yMin, head.xMax, head.yMax = min(xs), min(ys), max(x2), max(y2)
    h.advanceWidthMax = max(a for a, _ in metrics.values())
    h.minLeftSideBearing = min(l for _, l in metrics.values())
    h.numberOfHMetrics = len(order)
    # 只保留 Segoe 本身覆盖的字符：中文必须继续回落到雅黑，
    # 否则 CJK 会被按 Segoe 的设计空间缩放，字面会明显偏大
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

    if verbose:
        print("    补字 %d，裁剪后字形 %d" % (added, len(src.getGlyphOrder())))
    return src


def build_variant(vname, reg_w, bold_w):
    vdir = os.path.join(OUT, vname)
    if not os.path.isdir(vdir):
        print("跳过（无目录）:", vname)
        return
    print("[%s] Regular<-OPPO%d  Bold<-OPPO%d" % (vname, reg_w, bold_w))
    ref = TTFont(SEGOE)
    bases = {}
    for w, style, fname in ((reg_w, "Regular", "seg-%s.ttf" % vname),
                            (bold_w, "Bold", "seg-%s-b.ttf" % vname)):
        f = build_face(os.path.join(D, SRC[w]), ref, 400 if style == "Regular" else 700, style)
        tmp = os.path.join(vdir, fname)
        f.save(tmp, reorderTables=False)
        f.close()
        bases[style] = tmp

    # WinUI 部分控件直接请求子族名（...Text / Display / Small），
    # 原文件只提供 "Segoe UI Variable"，所以这里把四个名字都塞进同一个 TTC，
    # 无论壳界面请求哪个都能命中我们的字形。
    faces = []
    for alias in ALIASES:
        for style in ("Regular", "Bold"):
            f = TTFont(bases[style])
            fam = alias if style == "Regular" else alias + " Bold"
            psname = "".join(alias.split()) + ("" if style == "Regular" else "-Bold")
            for rec in f["name"].names:
                if rec.nameID in (1, 16):
                    rec.string = alias.encode("utf-16-be" if rec.platformID in (0, 3) else "latin-1")
                elif rec.nameID in (3, 4):
                    rec.string = fam.encode("utf-16-be" if rec.platformID in (0, 3) else "latin-1")
                elif rec.nameID == 6:
                    rec.string = psname.encode("utf-16-be" if rec.platformID in (0, 3) else "latin-1")
            faces.append(f)
    col = TTCollection()
    col.fonts = faces
    out = os.path.join(vdir, "SegUIVar.ttf")
    col.save(out, shareTables=True)
    col.close()

    chk = TTCollection(out, lazy=True)
    for i, ff in enumerate(chk.fonts):
        nm = [r.toUnicode() for r in ff["name"].names if r.nameID == 4 and r.platformID == 3][:1]
        g = ff["glyf"][ff.getBestCmap()[ord("H")]]
        g.recalcBounds(ff["glyf"])
        rg = ref["glyf"][ref.getBestCmap()[ord("H")]]
        rg.recalcBounds(ref["glyf"])
        same = (g.xMin, g.yMin, g.xMax, g.yMax) == (rg.xMin, rg.yMin, rg.xMax, rg.yMax)
        print("   face%d %-28s 「H」外框%s" % (i, nm, "一致" if same else "不一致!"))
    chk.close()
    print("   -> %s  %.2fMB" % (out, os.path.getsize(out) / 1048576.0))


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for vname, (rw, bw) in VARIANTS.items():
        if only and only != vname:
            continue
        build_variant(vname, rw, bw)
    print("DONE")
