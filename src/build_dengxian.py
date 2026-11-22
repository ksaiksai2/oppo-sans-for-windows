# -*- coding: utf-8 -*-
"""等线（DengXian）的拉丁字形替换。

为什么需要：系统里所有西文来源——Segoe UI 家族、Segoe UI Variable、微软雅黑的拉丁
——都已经换成 OPPO Sans 了。**唯一漏掉的是等线**（Deng.ttf / Dengb.ttf / Dengl.ttf）。
如果某个界面用的是等线的拉丁，那处就"压根没加上 OPPO Sans"。

做法：**只换拉丁部分，保留等线自己的中文与度量**。
等线是很多 Office 文档的中文默认字体，度量一动文档排版就会位移；保留中文和 advance
可以保证文档版式完全不变，只让英文字母变成 OPPO Sans。

参照：等线本身（advance、中文、度量全留）
来源：OPPO Sans 的拉丁字形，按等线的字面大小缩放
"""
import os
import sys

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

# 要替换的码位范围：ASCII + Latin-1 Supplement + Latin Extended-A/B 的一部分
LATIN_RANGES = [(0x20, 0x24F), (0x1E00, 0x1EFF)]

ANCHOR = "H"


def bbox_em(font, ch):
    upem = font["head"].unitsPerEm
    g = font["glyf"][font.getBestCmap()[ord(ch)]]
    g.recalcBounds(font["glyf"])
    return (g.xMin / upem, g.yMin / upem, g.xMax / upem, g.yMax / upem)


def build(ref_path, oppo_path, out_path):
    ref = TTFont(ref_path)
    src = TTFont(oppo_path)

    rcmap, scmap = ref.getBestCmap(), src.getBestCmap()
    if ord(ANCHOR) not in rcmap or ord(ANCHOR) not in scmap:
        raise SystemExit("参照与来源都缺少锚点字 %s" % ANCHOR)

    rb, sb = bbox_em(ref, ANCHOR), bbox_em(src, ANCHOR)
    sx = (rb[2] - rb[0]) / (sb[2] - sb[0])
    sy = (rb[3] - rb[1]) / (sb[3] - sb[1])
    dx = rb[0] - sb[0] * sx
    dy = rb[1] - sb[1] * sy
    k = ref["head"].unitsPerEm / src["head"].unitsPerEm
    KX, KY, DX, DY = sx * k, sy * k, dx * ref["head"].unitsPerEm, dy * ref["head"].unitsPerEm

    gs = src.getGlyphSet()
    glyf = ref["glyf"]
    replaced = 0
    for lo, hi in LATIN_RANGES:
        for cp in range(lo, hi + 1):
            if cp not in rcmap or cp not in scmap:
                continue
            if not (0x20 <= cp <= 0x7E or 0xA0 <= cp <= 0x24F):
                continue
            name = rcmap[cp]
            if name not in glyf.glyphs:
                continue
            rec = DecomposingRecordingPen(gs)
            gs[scmap[cp]].draw(TransformPen(rec, (KX, 0, 0, KY, DX, DY)))
            pen = TTGlyphPen(None)
            rec.replay(pen)
            g = pen.glyph()
            g.recalcBounds(glyf)
            if g.numberOfContours == 0:
                continue
            glyf.glyphs[name] = g
            replaced += 1

    # 说明写进 nameID 10；nameID 0 保留原厂版权（产物里含原厂中文字形）
    for rec in ref["name"].names:
        if rec.nameID == 10:
            rec.string = ("Latin glyphs replaced with OPPO Sans 4.0 outlines, metrics-aligned to the "
                          "original. Chinese glyphs and all metrics unchanged. For local system UI use "
                          "only; not for redistribution.").encode("utf-16-be" if rec.platformID == 3 else "latin-1")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    ref.save(out_path, reorderTables=False)
    print("  %-14s <- OPPO 拉丁 %d 字形  %.2fMB" % (os.path.basename(out_path), replaced,
                                                  os.path.getsize(out_path) / 1048576.0))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: build_dengxian.py <DengXian.ttf> <OPPOSans.ttf> <输出.ttf>")
        sys.exit(1)
    build(sys.argv[1], sys.argv[2], sys.argv[3])
