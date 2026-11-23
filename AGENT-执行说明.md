# Windows 系统字体替换 —— Agent 执行说明

> 目的：把任一中文字体（本文以 OPPO Sans 4.0 为例）完整移植成 Windows 界面字体，包括
> **中文三件套**、**Win11 壳界面英文（Segoe UI Variable）**、**经典英文（Segoe UI 五字重）**，
> 并做到「排版零位移、字面一致、不缺字、可完整回滚」。
>
> 读者是 agent。按顺序执行即可；每步都有**判据**，判据不通过就停下查「失败模式」。
> 全程约 9 次重启中的 3 次是必要的，其余为返工——照本文做可避免返工。

---

## 0. 总览：这套东西由哪几层构成

| 层 | 目标文件 | 作用范围 | 替换方式 |
|---|---|---|---|
| 中文 | `msyh.ttc` / `msyhbd.ttc` / `msyhl.ttc` | 所有中文界面、Office、网页中文 | **文件替换**（重启队列） |
| 壳界面英文 | `SegUIVar.ttf` | 开始菜单、任务栏面板、通知中心、资源管理器 | **副本 + 改注册表指向** |
| 经典英文 | `segoeui/b/sb/l/sl.ttf` | 老程序、网页 `Segoe UI`、部分 XAML | **副本 + 改注册表指向** |

**为什么后两层不能替换文件**：`SegUIVar.ttf` 在启动最早期就被占用，`PendingFileRenameOperations`
里的条目会被 smss 消费掉但改名/搬入**静默失败**（无 `.swapout` 残留）。中文三件套加载晚，可以正常改名。

**为什么必须度量对齐**：直接换字形会出现「字变小、按钮文字顶出、标题折行、行距变宽」。
根因是新旧字体的 em 方块与 advance 不同，不是字号问题。

---

## 1. 前置条件

- Windows 10/11（本项目在 Win11 26300 验证）
- 管理员权限
- Python 3.9+，`pip install fonttools pillow`
- 源字体：目标中文字体的静态字重（OPPO Sans 4.0 为
  `OPPOSans40-{Light,Regular,Medium,SemiBold,Bold}.ttf`，upem=1000）
- **原版参照字体**：`msyh.ttc`、`msyhbd.ttc`、`msyhl.ttc`、`SegUIVar.ttf`、`segoeui*.ttf` 五件

### 1.1 参照字体必须是「从未被替换过」的原版

这是全局最重要的约束。一旦系统里的字体被换过，构建就会**拿自己的产物当参照**，结果是：
`国` 的 bbox 永远「偏差 0」、符号尺寸永远「正常」，问题被掩埋。

取原版的三种途径（优先级从高到低）：

```powershell
# A. 组件库（最可靠，永远是最初的原版）
Get-ChildItem 'C:\Windows\WinSxS' -Filter 'msyh*.ttc' -Recurse -File |
  Where-Object { $_.Length -gt 15MB } | Select-Object FullName, Length

# B. 项目 backup\ 目录（首次安装时抓的）
# C. C:\Windows\Fonts（仅当从未替换过才安全）
```

> 判据：`backup\msyh.ttc` 的 SHA256 应与 WinSxS 里那份**完全一致**。不一致说明备份被污染。

---

## 2. 目录约定

```
项目根\
├─ src\      build.py（入口） + build_replacement/variants/segoe/segoe_classic/semibold/dengxian.py
├─ input\    源字体（Light/Regular/Medium/SemiBold/Bold + Heavy 备用）
├─ output\   w600\ / w700\ + segclassic\
├─ backup\   原版参照 + installed-variant.txt + 注册表备份 + skip-restorepoint.txt
├─ 600\  一键安装.cmd + 完整字体副本（含 segclassic\）
├─ 700\  一键安装.cmd + 完整字体副本（含 segclassic\）
└─ install/rollback/check/fix-acl/cleanup/flush-fontcache/switch-tier/查看还原点  (.ps1 + .cmd)
```

**档位切换**：双击 `600\一键安装.cmd` 或 `700\一键安装.cmd`。`switch-tier.ps1` 把该档字体
同步到 `output\` 再调 `install.ps1`。**segclassic 必须按档位各存一份**——600 档英文常规用
OPPO500、700 档用 OPPO700，共用会字重错位。

**字重声明与字形档位必须解耦**：`segoeui.ttf` 无论用哪档 OPPO 字形，`usWeightClass` 恒为 400。
曾把字形档位 700 直接写进字重声明，产出「subfamily=Regular / wght=600」的矛盾字体，
Windows 选择器跳过它并回退原版——表现为英文观感「退回原版」。

---

## 3. 构建中文三件套（度量对齐）

### 3.1 算法（关键，别改）

```
源字体 S（upem 1000），参照字体 R（upem 2048，微软雅黑 Regular）
k = 2048 / 1000

【逐字对齐】对每个字形 g，用它在 R 里对应码位的 bbox 单独求变换：

  s = S[g].bbox / 1000      r = R[同码位].bbox / 2048
  sx = (r.xMax - r.xMin) / (s.xMax - s.xMin)
  sy = (r.yMax - r.yMin) / (s.yMax - s.yMin)
  dx = r.xMin - s.xMin * sx
  dy = r.yMin - s.yMin * sy

  对 g 应用 ( sx*k, 0, 0, sy*k, dx*2048, dy*2048 )
  R 里没有该码位时，退回用锚点字「国」算出的统一系数。
```

⚠ **不要用「一个锚点字算统一系数套给全部字形」**。这是最初的做法，结果只有「国」
对齐，其余汉字垂直偏 50–90 单位（2.5–4% 字高），浏览器里文字相对图标看着「悬空」。
逐字对齐后 17/17 抽样字与参照逐单位重合。两款字体字面率分布接近（宽比 1.055–1.12、
高比 1.02–1.12），逐字缩放不会把字拉变形。

实现要点：
- 用 `DecomposingRecordingPen` 展开复合字形 → `TransformPen` 变换 → `TTGlyphPen` 重建。
  直接改 `glyf` 坐标会漏掉复合字形。
- **字宽（advance）全部取参照字体**：`hmtx[g].advance = R.hmtx[同码位].advance`。
  这是「排版零位移」的关键，实测整串文字宽度差 = 0。
- 垂直度量（`hhea.ascent/descent/lineGap`、`OS/2.typographic`、`usWinAscent/Descent`）
  全部取参照字体。
- ⚠ **`OS/2.sxHeight` 和 `sCapHeight` 必须复制**（雅黑 1106/1549，Segoe 1024/1434）。
  这两个字段是 DirectWrite/XAML 计算行内视觉中心的依据，漏掉会让 Edge 自带 UI 的文字
  相对图标偏高。网页 CSS 排版不读它们，所以网页对照页测不出来——这是最难查的一个坑。
- `head.unitsPerEm` 设为 2048，`OS/2.usWeightClass` 设为目标值（**见 3.3**）。

### 3.2 两个必须做的修正

**（a）符号尺寸归一**

纯几何符号的画法差异极大。实测 OPPO 与雅黑：`●` 1.64 倍、`○` 1.77 倍、`─` 0.60 倍。
而字宽取的是参照字体的，结果就是「又大又重叠」——**登录界面的密码圆点会爆掉**。

规则：只处理标点/符号区 `U+2000–2BFF`、`U+3000–303F`、`U+FE30–FE6F`、`U+FF00–FF65`，
满足任一条件即整字换成参照字形（设计空间已对齐，直接搬运）：

```
高比 > 1.15  或  宽比 > 1.15  或  字形宽 > advance*0.99  或  高比 < 0.87  或  宽比 < 0.87
```

> 阈值别放宽到 1.12 并套用到全字符集——会替换掉上万个汉字字形，等于把源字体设计抹掉。
> 实测正确命中数：OPPO→雅黑约 **234 个**；OPPO→Segoe 约 **63–70 个/字重**。

**（b）缺字补齐**

源字体缺的字，从参照字体搬（跳过假名/注音/部首，避免引入无关字形）。
OPPO Sans 缺 **1057** 字，补后 cmap 达 **30255**（原版雅黑 29905）。

### 3.3 字重档位映射（按「观感对齐手机」需求）

| 档 | 常规槽 | 粗体槽 | 细体槽 | 适用 |
|---|---|---|---|---|
| w400 | 400 | 700 | 300 | 与原版雅黑同粗细，最保守 |
| w500 | 500 | 700 | 400 | 略重 |
| **w600** | **600** | **700** | **500** | **推荐，观感最接近手机** |
| w700 | 700 | 700 | 600 | 全界面最粗，丢失字重层次 |

⚠ **文件里的 `usWeightClass` 要写 400，不是档位值**。写 700 会让系统只把它用在加粗场景，
正文仍是细的。档位语义是「用哪套字形」，不是「声明什么字重」。

### 3.4 产物

`output\w600\` 下：`msyh.ttc`、`msyhbd.ttc`、`msyhl.ttc`（各约 10MB，双 face TTC：
`微软雅黑` + `Microsoft YaHei UI`）。

### 3.5 判据

```
'国' 外框偏差 = 0 单位（对照参照字体）
全角字宽与参照完全一致
hhea asc/desc = 参照字体值（雅黑 2167/-536）
cmap 字数 ≥ 参照字体
```

---

## 4. 构建 Segoe UI Variable（壳界面英文）

原文件是**真·可变字体**：`upem=2048`，轴 `wght 300–700` + `opsz 5–36`，
family 仅 `Segoe UI Variable`，cmap **2417 字（无中文）**。

做法与中文同（锚点用 `H`），但有两个特殊步骤：

**（a）必须 subset 到原版 cmap**

不 subset 会把 2.9 万汉字带进去（文件 9.9MB），而且 CJK 会被按拉丁设计空间缩放、字面明显偏大。
正确做法：只保留原版覆盖的 2416 个字符，中文继续回落雅黑。

**（b）输出 8 face 的 TTC**

WinUI 部分控件直接请求子族名，原文件只提供 `Segoe UI Variable`，所以一次提供四个族名：

```
Segoe UI Variable / Segoe UI Variable Text / Segoe UI Variable Display / Segoe UI Variable Small
× Regular + Bold  = 8 faces
```

两个面都用粗字形，避免 DirectWrite 在请求 600/700 时对单面字体做**二次合成加粗**（会糊）。

> 坑：Bold 面若沿用 Regular 的名字表，Windows 会当成重复面。必须改 `nameID 2/3/4/6/17`。

### 判据

```
8 个 face 的 'H' 外框与参照完全一致
同一串英文的总 advance 与参照差值 = 0
GDI 能枚举出四个族名（原版只会有 1 个）
```

---

## 5. 构建经典 Segoe UI（五个字重）

按文件名逐个生成，都锚 `H`、字宽取原版：

| 文件 | 子族名 | OS/2 字重 | 用源字体的哪档 |
|---|---|---|---|
| segoeui.ttf | Regular | 400 | **500**（英文比中文轻一档，网页长文更好读） |
| segoeuib.ttf | Bold | 700 | 700 |
| seguisb.ttf | Semibold | 600 | 600 |
| segoeuil.ttf | Light | 300 | 300 |
| segoeuisl.ttf | Semilight | 350 | 400 |

不处理斜体（`segoeuii/z`、`seguisbi`）：源字体无真斜体，做出来是伪斜体更丑。
代价是界面里出现斜体英文时会跳回原字体——日常几乎遇不到。

---

## 6. 安装

### 6.1 中文三件套：重启队列

```
HKLM\SYSTEM\CurrentControlSet\Control\Session Manager
  PendingFileRenameOperations  (REG_MULTI_SZ，追加，不是覆盖)

每个文件 4 条：
  \??\C:\Windows\Fonts\<f>                  -> \??\C:\Windows\Fonts\<f>.swapout
  \??\C:\Windows\Temp\OPPOSansSwap-<时间戳>\<f> -> \??\C:\Windows\Fonts\<f>
```

三条硬性要求：

1. **不要排「删除不存在的文件」这一条**。smss 遇到失败会**停止处理后续项**，
   后面的改名与搬入全部跳过（这是最容易漏的一条：第一次装成功后，再次安装时
   若给新文件排了 delete 操作，就会整批失效）。
   残留的 `.swapout` 应在**安装阶段（管理员、文件未被占用）直接删掉**。
2. **暂存文件必须补 ACL**：`SYSTEM:(F)`、`Administrators:(F)`、`Users:(RX)`、`ALL APPLICATION PACKAGES:(RX)`。
   否则移入 Fonts 后 `fontdrvhost` 以用户身份读不到 → 中文逐字回落**宋体**。
   表现：字号小一档、12–16px 呈点阵状、带衬线尖角。这是最难诊断的故障。
3. 暂存目录用**唯一名**（带时间戳），不要「先删目录再建」——删不掉时 `New-Item` 会报已存在。

### 6.2 SegUIVar / 经典 Segoe：副本 + 注册表指向

```powershell
$fontsKey = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'

# 1) 复制副本，文件名带内容哈希（已注册的副本被锁定，无法覆盖，只能换新名字）
$hash = (Get-FileHash $src -Algorithm SHA256).Hash.Substring(0,8).ToLower()
$name = "SegUIVarOPPO-$hash.ttc"     # 分别对应各目标文件
Copy-Item $src (Join-Path $Fonts $name)
icacls ... (同 6.1 的四条授权)

# 2) 改指向（值就是文件名，不是族名）
Set-ItemProperty $fontsKey -Name 'Segoe UI Variable (TrueType)' -Value $name
Set-ItemProperty $fontsKey -Name 'Segoe UI (TrueType)'  -Value "SegoeUIOppo-$hash-segoeui.ttf"
# 以及 Segoe UI Bold / Semibold / Light / Semilight 四项
```

**备份原值的正确写法**（曾经踩过）：

```powershell
# 只在「当前值确实是原版」且「还没备份过」时记录
if ($curVal -and $curVal -notlike 'SegUIVarOPPO*' -and -not (Test-Path $regBak)) {
    Set-Content $regBak $curVal
}
```

无条件重写会把**自己上一次写的副本名**当成原值存下来，回滚时注册表会指向一个已被删除的文件。

### 6.3 系统还原点：必须询问，不自动建

```powershell
# 默认询问 Y/N；backup\skip-restorepoint.txt 存在时自动跳过
Checkpoint-Computer -Description 'Before font install' -RestorePointType MODIFY_SETTINGS
```

⚠ 不要无条件调用。`Checkpoint-Computer` 有 24 小时频率限制（1440 分钟），每次 install
都偷偷建会刷一堆警告，且用户不知情。系统保护未开启或超频率时只警告、不中断。
`查看还原点.cmd` 供管理员列出全部还原点（注意 CIM DATETIME 是 UTC，必须用
`ManagementDateTimeConverter` 转本地时间，否则显示成「下午三点」）。

### 6.4 脚本自身的三条铁律

- `.cmd` **纯 ASCII + CRLF**。含中文会被 cmd 按 GBK 撕坏（连 `rem` 注释都会变成"不是内部命令"）；
  LF-only 且正文有多行 `if (...)` 块时会解析失败直接退出。
- `.ps1` **必须带 UTF-8 BOM + CRLF**。无 BOM 时 PowerShell 5.1 按 ANSI 读，中文注释会炸。
- 提权判断用 `WindowsPrincipal.IsInRole`，**不要用 `net session`**（依赖 Server 服务，
  服务停用时已提权的窗口会再次自我提权，形成"开一个闪一个"的循环）。

---

## 7. 验证清单（缺一不可）

| 层次 | 检查 | 期望 |
|---|---|---|
| 文件 | `Get-FileHash` 对比 backup | 一致 |
| 权限 | `[System.IO.File]::OpenRead($p)` | 能打开（普通用户身份） |
| 注册表 | 6 个关键项 | 无 `Oppo` 字样或正确指向副本 |
| 字形 | GDI `GetGlyphOutlineW` 取字形 md5 | 原版基准：Segoe `'A'`=`67025b47`，雅黑 `'国'`=`ae52f345` |
| 渲染 | 截图量「墨密度 / 笔画比」 | 中文 `●` 高度 0.464em（雅黑）、Segoe 0.430em |
| 观感 | 开始菜单、通知中心、输入法 | 无宋体回退、无巨大符号 |

> **只看文件哈希是不够的**：文件字节正确、注册表正确、GDI 枚举正确，渲染仍可能因权限问题
> 回落宋体。必须同时验「可读性」与「实际字形」。

---

## 8. 失败模式速查（按踩坑频率排序）

| # | 现象 | 根因 | 处置 |
|---|---|---|---|
| 1 | 界面中文又小又像素、带衬线尖角 | ACL 缺失 → 回落宋体 | 补四条授权（`fix-acl`），重启 |
| 2 | 队列排上了但文件没换、`.swapout` 不存在 | 队列里排了「删除不存在文件」，smss 中断 | 去掉 delete 条目，改在安装阶段删除 |
| 3 | `SegUIVar.ttf` 改名始终失败 | 启动早期被占用 | 改「副本 + 注册表指向」 |
| 4 | 构建结果「国」永远偏差 0、符号永远正常 | 参照字体已被自己替换 | 参照改用 backup / WinSxS |
| 5 | 重建后档位识别失效，装成了别的字重 | 用哈希识别档位 | 用 `backup\installed-variant.txt` 标记 |
| 6 | 回滚后英文界面指向不存在的文件 | 注册表备份被覆盖 | 只写一次备份，且排除自家副本 |
| 7 | 首装报「找不到字重档位目录」 | 哈希匹配不上，回落 w400 | 按 `output\` 里唯一存在的档位推断 |
| 8 | 登录界面密码圆点巨大重叠 | 符号尺寸差 1.6 倍 | 符号区尺寸归一 |
| 9 | 网页/输入法出现方框 | 源字体缺字 | 从参照搬 1057 字 |
| 10 | 改了字体但界面不变 | 字体缓存 | 停 FontCache 服务、删 `FNTCACHE.DAT`，重启 |
| 11 | 脚本双击一闪而过 | 未捕获异常 | 顶层 `trap` + `Start-Transcript` 日志 |
| 12 | Python 路径替换静默失效 | bash heredoc 吃掉反斜杠（`\` → `/`） | 改文件用编辑器，别用 heredoc 传 Windows 路径 |
| 13 | Edge 自带 UI 文字相对图标偏高/悬空 | `sxHeight/sCapHeight` 没复制（成了源字体的 518/725） | 四个构建脚本全部从参照复制这两个字段 |
| 14 | 同一页面里其他汉字垂直不齐，只有锚点「国」对 | 用单锚点统一缩放套全部字形 | 改成逐字 bbox 对齐 |
| 15 | 英文观感「退回原版」 | 字重声明与字形档位画等号，产出矛盾字体 | 字形档位与 `usWeightClass` 解耦 |
| 16 | 英文在应用中比中文轻一档 | 开始菜单应用名走经典 Segoe 而非 Variable | 英文档位跟随中文档位，且两档各存一份 segclassic |

---

## 9. 回滚

三条路径，按可靠性排序：

1. **系统还原点**（安装前自动创建）
2. **`sfc /scannow`**：从组件库换回受保护的系统文件。
   注意它**不管注册表指向**——跑完还要把 `Segoe UI*` 六项改回原文件名
3. **脚本回滚**：还原三个雅黑文件 + 撤销全部注册表指向 + 删除副本，重启生效。
   回滚脚本的暂存文件**同样要补 ACL**（与 6.1 第 2 条一致），否则会重演失败模式 1。

---

## 10. 授权红线

- 目标字体的许可必须逐条核对。OPPO Sans 条款明确：**不对字体进行改编或二次开发**。
  本项目做的事全部落在这一条上，因此：**仅限本机个人使用，禁止分发构建产物**。
- 产物文件名/族名沿用「微软雅黑」，涉及微软商标。个人自用风险低，公开发布风险高。
- 若要开源发布：**只发代码**（不含任何 `.ttf/.ttc`），且把定位改为「任意字体」，
  默认示例换成 SIL OFL 许可的字体（思源黑体、霞鹜文楷、更纱黑体），
  并在 README 注明「仅支持你有权修改的字体」。仓库加 `.gitignore` 屏蔽字体扩展名。

---

## 11. 基准数值（用于快速回归）

```
中文（w600）     upem 2048 / 字形 30479 / cmap 30255
                 '国' bbox (150,-269,1900,1599)   与参照偏差 0（逐字对齐后 17/17 重合）
                 ● 0.464em（= 雅黑原版）
                 OS/2 sxHeight=1106 sCapHeight=1549
SegUIVar         8 faces / 2416 字形 / 文件 0.28~0.54MB
                 'H' 外框与参照一致 / 整串 advance 差 0 / ● 0.430em
                 OS/2 sxHeight=1024 sCapHeight=1434
经典 Segoe 五件   各约 0.10MB / 'A' 字宽与参照一致
原版哈希基准      msyh d79c55e68b11 / msyhbd 4508821b3dff
                 msyhl 7e9bdf90bb5d / SegUIVar 27ca1ab4bd5a
GDI 字形基准       Segoe 'A' = 67025b47  雅黑 '国' = ae52f345
```
