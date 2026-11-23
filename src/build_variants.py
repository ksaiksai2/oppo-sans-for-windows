# -*- coding: utf-8 -*-
"""在 400 之外再生成 500 / 600 / 700 三套「常规字重更重」的替换字体。

思路：界面正文用的是 msyh.ttc 里的 Regular face。把它的字形换成 OPPO 的
Medium / SemiBold / Bold，但 OS/2 字重仍标 400，Windows 就把这当作「常规体」，
于是正文整体变粗；而需要真正粗体的位置（标题、加粗）仍旧命中 msyhbd.ttc，
对比关系不丢。字面尺寸与字宽仍按雅黑对齐，排版依旧零位移。
"""
import os
import sys

sys.path.insert(0, r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0")
from build_replacement import build_base, D  # noqa: E402
from fontTools.ttLib import TTFont, TTCollection  # noqa: E402

OUT = r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\replacement"
OPPO_COPYRIGHT = "Copyright 2024 Guangdong OPPO Mobile Telecommunications Corp., Ltd. OPPO Sans Fonts."
DESC = ("OPPO Sans 4.0 outlines, metrics-aligned to Microsoft YaHei for local system UI replacement. "
        "Derived font for personal use only; not for redistribution.")

SRC = {
    300: "OPPOSans40-Light.ttf",
    400: "OPPOSans40-Regular.ttf",
    500: "OPPOSans40-Medium.ttf",
    600: "OPPOSans40-SemiBold.ttf",
    700: "OPPOSans40-Bold.ttf",
}
# 每个槽位用的目标系统文件；weight 是写进字体元数据的值（Regular 槽保持 400）
SLOTS = [
    ("Regular", r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\backup\msyh.ttc", "msyh.ttc", 400),
    ("Bold", r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\backup\msyhbd.ttc", "msyhbd.ttc", 700),
    ("Light", r"C:\Users\ksaiksai\Fonts\OPPO-Sans-4.0\backup\msyhl.ttc", "msyhl.ttc", 300),
]
VARIANTS = {
    "w400": {"Regular": 400, "Bold": 700, "Light": 300},
    "w500": {"Regular": 500, "Bold": 700, "Light": 400},
    "w600": {"Regular": 600, "Bold": 700, "Light": 500},
    "w700": {"Regular": 700, "Bold": 700, "Light": 600},
}


def patch_face(font, ref):
    font["name"].names = [rec for rec in ref["name"].names]
    for rec in font["name"].names:
        if rec.nameID == 0:
            rec.string = OPPO_COPYRIGHT.encode("utf-16-be" if rec.platformID in (0, 3) else "latin-1")
        elif rec.nameID == 10:
            rec.string = DESC.encode("utf-16-be" if rec.platformID in (0, 3) else "latin-1")
    rh, ro = ref["hhea"], ref["OS/2"]
    font["hhea"].ascent, font["hhea"].descent, font["hhea"].lineGap = rh.ascent, rh.descent, rh.lineGap
    font["OS/2"].usWinAscent, font["OS/2"].usWinDescent = ro.usWinAscent, ro.usWinDescent
    # x-height / cap-height: DirectWrite/XAML 用它算行内视觉中心，
    # 不复制会让 Edge 自带 UI 的文字相对图标偏高（网页 CSS 排版不受影响）。
    font["OS/2"].sxHeight, font["OS/2"].sCapHeight = ro.sxHeight, ro.sCapHeight


def bbox_of(font, ch="国"):
    g = font["glyf"][font.getBestCmap()[ord(ch)]]
    g.recalcBounds(font["glyf"])
    return (g.xMin, g.yMin, g.xMax, g.yMax)


def build_variant(name, mapping):
    vdir = os.path.join(OUT, name)
    os.makedirs(vdir, exist_ok=True)
    print("=== %s  常规槽=%d 粗体槽=%d 细体槽=%d ===" % (
        name, mapping["Regular"], mapping["Bold"], mapping["Light"]))
    for slot, ref_ttc, out_name, meta_weight in SLOTS:
        src_w = mapping[slot]
        font = build_base(os.path.join(D, SRC[src_w]), ref_ttc, 0, meta_weight, slot, verbose=False)
        tmp = os.path.join(vdir, "base-%s.ttf" % slot)
        font.save(tmp, reorderTables=False)
        font.close()

        ref = TTCollection(ref_ttc, lazy=False)
        faces = []
        for idx in range(len(ref.fonts)):
            f = TTFont(tmp)
            patch_face(f, ref.fonts[idx])
            faces.append(f)
        col = TTCollection()
        col.fonts = faces
        out = os.path.join(vdir, out_name)
        col.save(out, shareTables=True)
        col.close()

        chk_col = TTCollection(out, lazy=True)
        chk = chk_col.fonts[0]
        g = chk["glyf"][chk.getBestCmap()[ord("国")]]
        g.recalcBounds(chk["glyf"])
        r = ref.fonts[0]
        rg = r["glyf"][r.getBestCmap()[ord("国")]]
        rg.recalcBounds(r["glyf"])
        same = (g.xMin, g.yMin, g.xMax, g.yMax) == (rg.xMin, rg.yMin, rg.xMax, rg.yMax)
        print("  %-8s <- OPPO %d  %5.1fMB  「国」外框%s" % (
            slot, src_w, os.path.getsize(out) / 1048576.0, "一致" if same else "不一致!"))
        chk_col.close()
        for f in faces:
            f.close()
    print("")


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, mapping in VARIANTS.items():
        if only and only != name:
            continue
        build_variant(name, mapping)
    print("DONE")
