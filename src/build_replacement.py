# -*- coding: utf-8 -*-
"""把 OPPO Sans 4.0 的静态字重伪装成「微软雅黑 / 微软雅黑 UI」的替换字体。

关键点（这也是网上那些一键包没做的）：
1) 设计空间对齐：把 OPPO 的「国」字外框缩放平移到雅黑「国」的外框上，
   这样同字号下字面大小完全一致，不会出现「换完字变小」。
2) 字宽取雅黑的：全角字符一律用雅黑的 advance，中文排版不会变宽、按钮文字不会顶出。
3) 度量取雅黑的：hhea / OS-2 的 ascent、descent、lineGap 全用雅黑的值，行距不变。
4) 补字：雅黑有而 OPPO 没有的字符，直接从雅黑搬轮廓过来——因为设计空间已对齐，
   搬过来尺寸天然吻合，不会出现方框。
"""
import os
import sys

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont, TTCollection, newTable

D = r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\build"
OUT = r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\replacement"
ANCHOR = "国"          # 用来对齐设计空间的基准字
FULLWIDTH_MIN = 0.85   # advance >= 0.85em 视为全角，用雅黑字宽

# (OPPO 静态文件, 目标系统 TTC, 目标 face 序号, 字重)
JOBS = [
    ("OPPOSans40-Regular.ttf", r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\backup\msyh.ttc", 0, 400, "Regular"),
    ("OPPOSans40-Bold.ttf", r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\backup\msyhbd.ttc", 0, 700, "Bold"),
    ("OPPOSans40-Light.ttf", r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\backup\msyhl.ttc", 0, 300, "Light"),
]

OPPO_COPYRIGHT = "Copyright 2024 Guangdong OPPO Mobile Telecommunications Corp., Ltd. OPPO Sans Fonts."
DESC = ("OPPO Sans 4.0 outlines, metrics-aligned to Microsoft YaHei for local system UI replacement. "
        "Derived font for personal use only; not for redistribution.")


def bbox_em(font, ch):
    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    g = font["glyf"][cmap[ord(ch)]]
    g.recalcBounds(font["glyf"])
    return (g.xMin / upem, g.yMin / upem, g.xMax / upem, g.yMax / upem)


def build_base(src_ttf, ref_ttc, ref_face, weight, style, verbose=True):
    src = TTFont(src_ttf)
    ref = TTCollection(ref_ttc, lazy=False).fonts[ref_face]

    s_upem = src["head"].unitsPerEm
    r_upem = ref["head"].unitsPerEm          # 2048

    sb = bbox_em(src, ANCHOR)
    rb = bbox_em(ref, ANCHOR)
    sx = (rb[2] - rb[0]) / (sb[2] - sb[0])
    sy = (rb[3] - rb[1]) / (sb[3] - sb[1])
    dx = rb[0] - sb[0] * sx
    dy = rb[1] - sb[1] * sy

    k = r_upem / s_upem                      # 1000 -> 2048
    KX, KY = sx * k, sy * k
    DX, DY = dx * r_upem, dy * r_upem
    if verbose:
        print("  设计空间: sx=%.4f sy=%.4f dx=%+.4fem dy=%+.4fem (upem %d->%d)"
              % (sx, sy, dx, dy, s_upem, r_upem))

    # ---- 1. 拆轮廓并变换 ----
    order = src.getGlyphOrder()
    glyph_set = src.getGlyphSet()
    glyf = src["glyf"]
    new_glyphs = {}
    for name in order:
        rec = DecomposingRecordingPen(glyph_set)
        glyph_set[name].draw(TransformPen(rec, (KX, 0, 0, KY, DX, DY)))
        pen = TTGlyphPen(None)
        rec.replay(pen)
        new_glyphs[name] = pen.glyph()
    glyf.glyphs = new_glyphs

    # ---- 1.5 符号尺寸对齐 ----
    # 纯几何符号（●○※─「」等）OPPO 和雅黑的画法差很多：● 的直径能到 1.64 倍，
    # 而字宽取的是雅黑的，结果就是又大又互相重叠（登录界面密码圆点就是这样）。
    # 这类偏差过大的符号，直接换成雅黑的字形 —— 设计空间已对齐，直接搬即可。
    ref_glyph_set = ref.getGlyphSet()
    ref_hmtx0 = ref["hmtx"]
    def _is_symbol(cp):
        return (0x2000 <= cp <= 0x2BFF or 0x3000 <= cp <= 0x303F or
                0xFE30 <= cp <= 0xFE6F or 0xFF00 <= cp <= 0xFF65)

    resync = 0
    for cp, gn in src.getBestCmap().items():
        # 只处理标点/符号/箭头/几何/制表这类；汉字和拉丁字母保留 OPPO 自己的设计
        if cp < 0x20 or cp not in ref.getBestCmap() or not _is_symbol(cp):
            continue
        g = new_glyphs[gn]
        g.recalcBounds(glyf)
        if g.numberOfContours == 0:
            continue
        rg = ref["glyf"][ref.getBestCmap()[cp]]
        rg.recalcBounds(ref["glyf"])
        h1, h2 = g.yMax - g.yMin, rg.yMax - rg.yMin
        w1, w2 = g.xMax - g.xMin, rg.xMax - rg.xMin
        if h2 <= 0 or w2 <= 0:
            continue
        adv = ref_hmtx0[ref.getBestCmap()[cp]][0]
        too_big = (h1 / h2 > 1.15) or (w1 / w2 > 1.15) or (w1 > adv * 0.99)
        too_small = (h1 / h2 < 0.87) or (w1 / w2 < 0.87)
        if too_big or too_small:
            rec = DecomposingRecordingPen(ref_glyph_set)
            ref_glyph_set[ref.getBestCmap()[cp]].draw(TransformPen(rec, (1, 0, 0, 1, 0, 0)))
            pen = TTGlyphPen(None)
            rec.replay(pen)
            new_glyphs[gn] = pen.glyph()
            resync += 1
    if verbose:
        print("    符号尺寸对齐：替换 %d 个" % resync)

    # ---- 2. 补字：从雅黑搬缺失字符 ----
    ref_cmap = ref.getBestCmap()
    ref_glyph_set = ref.getGlyphSet()
    src_cmap = src.getBestCmap()
    missing = [cp for cp in ref_cmap if cp not in src_cmap]
    # 假名 / 注音 / 康熙部首 / 半角片假名这类界面用不到的，跳过以省体积
    def skip(cp):
        return cp < 0x20 or cp == 0x7F
    added = 0
    for cp in missing:
        if skip(cp):
            continue
        new_name = "yh%05X" % cp
        if new_name in new_glyphs:
            continue
        ref_name = ref_cmap[cp]
        rec = DecomposingRecordingPen(ref_glyph_set)
        ref_glyph_set[ref_name].draw(TransformPen(rec, (1, 0, 0, 1, 0, 0)))
        pen = TTGlyphPen(None)
        rec.replay(pen)
        new_glyphs[new_name] = pen.glyph()
        order.append(new_name)
        added += 1
    src.setGlyphOrder(order)
    glyf.glyphs = new_glyphs
    glyf.glyphOrder = order

    # cmap 补映射
    for table in src["cmap"].tables:
        if not table.isUnicode():
            continue
        for cp in missing:
            if skip(cp):
                continue
            if cp in table.cmap:
                continue
            if table.format == 4 and cp > 0xFFFF:
                continue
            table.cmap[cp] = "yh%05X" % cp

    # ---- 3. 重建 hmtx：全角用雅黑字宽，其余按缩放 ----
    ref_hmtx = ref["hmtx"]
    new_metrics = {}
    src_hmtx = src["hmtx"]
    reverse = {}
    for cp, gn in src.getBestCmap().items():
        reverse.setdefault(gn, cp)

    for name in order:
        g = new_glyphs[name]
        g.recalcBounds(glyf)
        lsb = getattr(g, "xMin", 0) if g.numberOfContours != 0 else 0
        cp = reverse.get(name)
        adv = None
        if name.startswith("yh"):
            cp2 = int(name[2:], 16)
            if cp2 in ref_cmap:
                adv = ref_hmtx[ref_cmap[cp2]][0]
        elif cp is not None and cp in ref_cmap:
            # 只要雅黑有这个字，字宽就用雅黑的：界面排版零位移，文字不会被截断
            adv = ref_hmtx[ref_cmap[cp]][0]
        if adv is None:
            adv = int(round(src_hmtx[name][0] * KX))
        new_metrics[name] = (adv, lsb)
    src["hmtx"].metrics = new_metrics

    # ---- 4. 度量全部改雅黑 ----
    rh, ro = ref["hhea"], ref["OS/2"]
    h, o = src["hhea"], src["OS/2"]
    h.ascent, h.descent, h.lineGap = rh.ascent, rh.descent, rh.lineGap
    o.sTypoAscender, o.sTypoDescender, o.sTypoLineGap = ro.sTypoAscender, ro.sTypoDescender, ro.sTypoLineGap
    o.usWinAscent, o.usWinDescent = ro.usWinAscent, ro.usWinDescent
    o.xAvgCharWidth = ro.xAvgCharWidth
    o.usWeightClass = weight
    keep = o.fsSelection & 0b10000000
    if weight == 700:
        keep |= 0b100000
    elif weight == 400:
        keep |= 0b1000000
    o.fsSelection = keep

    head = src["head"]
    head.unitsPerEm = r_upem
    head.macStyle = 0b01 if weight == 700 else 0
    head.flags = head.flags | 0b1000   # 力度无关，保持原值

    # ---- 5. 名字：照抄目标系统的 name 表，只换版权与说明 ----
    src["name"].names = []
    for rec in ref["name"].names:
        src["name"].names.append(rec)
    def setname(nid, text, all_langs=True):
        hit = False
        for rec in src["name"].names:
            if rec.nameID == nid:
                rec.string = text.encode("utf-16-be" if rec.platformID in (0, 3) else "latin-1")
                hit = True
        return hit
    setname(0, OPPO_COPYRIGHT)
    setname(10, DESC)
    src["post"].formatType = 3.0
    # 竖排度量 / 与 upem 绑定的缓存表：新增字形后无法一致，且界面排版用不到
    for tag in ("DSIG", "STAT", "fvar", "gvar", "MVAR", "vhea", "vmtx", "hdmx", "VDMX", "LTSH"):
        if tag in src:
            del src[tag]

    # 重算极值
    xmins, ymins, xmaxs, ymaxs = [], [], [], []
    for name in order:
        g = new_glyphs[name]
        g.recalcBounds(glyf)
        if g.numberOfContours != 0:
            xmins.append(g.xMin); ymins.append(g.yMin)
            xmaxs.append(g.xMax); ymaxs.append(g.yMax)
    head.xMin, head.yMin, head.xMax, head.yMax = min(xmins), min(ymins), max(xmaxs), max(ymaxs)
    h.advanceWidthMax = max(a for a, _ in new_metrics.values())
    h.minLeftSideBearing = min(l for _, l in new_metrics.values())
    h.minRightSideBearing = min(a - l - (new_glyphs[n].xMax - new_glyphs[n].xMin)
                                for n, (a, l) in new_metrics.items()
                                if new_glyphs[n].numberOfContours != 0)
    h.xMaxExtent = max(l + (new_glyphs[n].xMax - new_glyphs[n].xMin)
                       for n, (a, l) in new_metrics.items()
                       if new_glyphs[n].numberOfContours != 0)
    h.numberOfHMetrics = len(order)
    if "maxp" in src:
        try:
            src["maxp"].recalc(src)
        except Exception:
            pass

    if verbose:
        print("  补字 %d 个（跳过假名/注音/部首），总字形 %d" % (added, len(order)))
    return src


def verify(font, ref_ttc, ref_face, tag):
    ref = TTCollection(ref_ttc, lazy=False).fonts[ref_face]
    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    ok = True
    # 字面外框
    for ch in (ANCHOR, "一", "口"):
        g = font["glyf"][cmap[ord(ch)]]
        g.recalcBounds(font["glyf"])
        rg = ref["glyf"][ref.getBestCmap()[ord(ch)]]
        rg.recalcBounds(ref["glyf"])
        d = max(abs(g.xMin - rg.xMin), abs(g.yMin - rg.yMin), abs(g.xMax - rg.xMax), abs(g.yMax - rg.yMax))
        if d > 2:
            ok = False
        print("    '%s' 外框偏差 %d 单位 (%s)" % (ch, d, "OK" if d <= 2 else "!!超差"))
    # 字宽
    bad = 0
    for ch in "国显示与亮度字体大小粗细设置网络蓝牙，。！？（）":
        if ord(ch) not in cmap:
            continue
        a1 = font["hmtx"][cmap[ord(ch)]][0]
        a2 = ref["hmtx"][ref.getBestCmap()[ord(ch)]][0]
        if abs(a1 - a2) > 1:
            bad += 1
            print("    '%s' 字宽 %d vs 雅黑 %d" % (ch, a1, a2))
    if bad == 0:
        print("    全角字宽与雅黑完全一致")
    else:
        ok = False
    print("    hhea asc/desc = %d/%d (雅黑 %d/%d)" % (
        font["hhea"].ascent, font["hhea"].descent, ref["hhea"].ascent, ref["hhea"].descent))
    return ok


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for fn, ttc, face, weight, style in JOBS:
        if only and only.lower() != style.lower():
            continue
        print("[%s] %s" % (style, fn))
        f = build_base(os.path.join(D, fn), ttc, face, weight, style)
        out = os.path.join(OUT, "base-%s.ttf" % style)
        f.save(out, reorderTables=False)
        print("  保存 %s  %.1fMB" % (os.path.basename(out), os.path.getsize(out) / 1048576.0))
        g = TTFont(out)
        verify(g, ttc, face, style)
        g.close()
        f.close()
    print("DONE")
