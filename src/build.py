# -*- coding: utf-8 -*-
"""构建入口：把用户自备的 OPPO Sans 静态字重，生成可安装的替换字体。

用法（在仓库根目录执行）：

    python src\\build.py --weight 600

输入：
    input\\OPPOSans40-Light.ttf / Regular / Medium / SemiBold / Bold

参考字体（必须是最初的微软原版，否则度量会跟着漂）：
    backup\\  里如果有 msyh.ttc / SegUIVar.ttf / segoeui.ttf 等，就用它；
    否则退回到 C:\\Windows\\Fonts（仅当你从未装过替换字体时才安全）。

输出：
    output\\w<字重>\\msyh.ttc / msyhbd.ttc / msyhl.ttc / SegUIVar.ttc
    output\\w<字重>\\segclassic\\segoeui.ttf ... （经典 Segoe UI 五个字重）
"""
import argparse
import importlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "input")
OUT_ROOT = os.path.join(ROOT, "output")
BAK_DIR = os.path.join(ROOT, "backup")
WINFONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

OPPO_FILES = {
    300: "OPPOSans40-Light.ttf",
    400: "OPPOSans40-Regular.ttf",
    500: "OPPOSans40-Medium.ttf",
    600: "OPPOSans40-SemiBold.ttf",
    700: "OPPOSans40-Bold.ttf",
}
# 参考字体：文件名 -> 备份名
REF_NEEDED = ["msyh.ttc", "msyhbd.ttc", "msyhl.ttc", "SegUIVar.ttf",
              "segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "segoeuil.ttf", "segoeuisl.ttf"]

# 每个档位：常规槽 / 粗体槽 / 细体槽 用哪个 OPPO 字重
TIERS = {
    400: {"Regular": 400, "Bold": 700, "Light": 300},
    500: {"Regular": 500, "Bold": 700, "Light": 400},
    600: {"Regular": 600, "Bold": 700, "Light": 500},
    700: {"Regular": 700, "Bold": 700, "Light": 600},
}
# 经典 Segoe UI 的字重映射。常规档跟着中文档位走：中文越粗，英文也提一档，
# 否则中英并排时英文会显得发虚（中文 700 配英文 500 就是这种效果）。
CLASSIC_REGULAR = {400: 400, 500: 500, 600: 500, 700: 600}
CLASSIC_MAP = {
    "segoeuib.ttf": 700,
    "seguisb.ttf": 600,
    "segoeuil.ttf": 300,
    "segoeuisl.ttf": 400,
}


def resolve_ref():
    """确定参考字体目录：优先 backup（必然是最初的原版）。"""
    use_bak = all(os.path.exists(os.path.join(BAK_DIR, f)) for f in ("msyh.ttc", "SegUIVar.ttf"))
    if use_bak:
        print("参考字体：backup\\（原版备份）")
        return BAK_DIR
    print("参考字体：%s" % WINFONTS)
    print("  ⚠ 如果你之前装过替换字体，这里的 msyh.ttc 已经不是原版了，")
    print("    构建结果的度量会跟着漂。先跑 rollback 或从 WinSxS 取原版再构建。")
    return WINFONTS


def check_inputs():
    missing = [f for f, name in OPPO_FILES.items() if not os.path.exists(os.path.join(SRC_DIR, name))]
    if missing:
        print("缺少 OPPO Sans 字体文件，请放到 input\\ 下：")
        for w in missing:
            print("  %s  （%d 字重）" % (OPPO_FILES[w], w))
        print("\n官方下载：https://www.coloros.com/ （页面底部「OPPO Sans」）")
        sys.exit(1)


def build(weight):
    ref_dir = resolve_ref()
    check_inputs()
    mapping = TIERS[weight]
    out_dir = os.path.join(OUT_ROOT, "w%d" % weight)
    os.makedirs(out_dir, exist_ok=True)

    sys.path.insert(0, os.path.join(ROOT, "src"))
    br = importlib.import_module("build_replacement")
    bv = importlib.import_module("build_variants")
    bs = importlib.import_module("build_segoe")
    bsc = importlib.import_module("build_segoe_classic")

    print("\n=== 1/4 微软雅黑三件套 ===")
    bv.D = SRC_DIR
    bv.OUT = OUT_ROOT
    bv.SLOTS = [
        ("Regular", os.path.join(ref_dir, "msyh.ttc"), "msyh.ttc", 400),
        ("Bold", os.path.join(ref_dir, "msyhbd.ttc"), "msyhbd.ttc", 700),
        ("Light", os.path.join(ref_dir, "msyhl.ttc"), "msyhl.ttc", 300),
    ]
    bv.VARIANTS = {"w%d" % weight: mapping}
    bv.build_variant("w%d" % weight, mapping)

    print("\n=== 2/4 Segoe UI Variable（壳界面英文）===")
    bs.D = SRC_DIR
    bs.OUT = OUT_ROOT
    bs.SEGOE = os.path.join(ref_dir, "SegUIVar.ttf")
    bs.VARIANTS = {"w%d" % weight: (mapping["Regular"], 700)}
    bs.build_variant("w%d" % weight, mapping["Regular"], 700)

    print("\n=== 3/4 经典 Segoe UI（五个字重）===")
    bsc.SRCDIR = SRC_DIR
    bsc.OUTDIR = os.path.join(OUT_ROOT, "segclassic")
    bsc.WINFONTS = ref_dir
    reg_w = CLASSIC_REGULAR.get(weight, 500)
    bsc.TARGETS = [(f, sub, w, {"segoeuil.ttf": 300, "segoeuisl.ttf": 350}.get(f, w))
                   for f, sub, w in (("segoeui.ttf", "Regular", reg_w),
                                     ("segoeuib.ttf", "Bold", CLASSIC_MAP["segoeuib.ttf"]),
                                     ("seguisb.ttf", "Semibold", CLASSIC_MAP["seguisb.ttf"]),
                                     ("segoeuil.ttf", "Light", CLASSIC_MAP["segoeuil.ttf"]),
                                     ("segoeuisl.ttf", "Semilight", CLASSIC_MAP["segoeuisl.ttf"]))]
    os.makedirs(bsc.OUTDIR, exist_ok=True)
    for t in bsc.TARGETS:
        bsc.build(*t)

    print("\n=== 4/4 补 Semibold 面（让标题命中 600 而不是 700）===")
    bsem = importlib.import_module("build_semibold")
    bsem.build(os.path.join(out_dir, "base-Regular.ttf"), os.path.join(out_dir, "msyhsc.ttf"))

    print("\n=== 完成 ===")
    total = 0
    for d, _, fs in os.walk(out_dir):
        for f in fs:
            total += os.path.getsize(os.path.join(d, f))
    print("输出目录：%s（%.1f MB）" % (out_dir, total / 1048576.0))
    print("\n下一步：右键 install.cmd →「以管理员身份运行」→ 重启。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--weight", type=int, default=600, choices=[400, 500, 600, 700],
                    help="常规体用哪个 OPPO 字重（默认 600 半粗）")
    args = ap.parse_args()
    build(args.weight)
