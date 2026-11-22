# 安装：把系统微软雅黑换成 OPPO Sans 4.0（需管理员，重启后生效）
#
# 关键：C:\Windows\Fonts 下的字体被 fontdrvhost.exe 内存映射，运行期间无法改名或覆盖。
# 因此不能直接复制，改用系统自带的重启时替换机制
#   HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\PendingFileRenameOperations
# smss 在加载字体之前执行它，所以重启后文件就被换掉了。
param([string]$Variant = '')

$ErrorActionPreference = 'Stop'

# 任何意外都别让窗口一闪而过（原先异常会让脚本直接退出、窗口秒关）
trap {
    Write-Host ''
    Write-Host ('意外错误：' + $_.Exception.Message) -ForegroundColor Red
    if ($_.ScriptStackTrace) { Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray }
    try { Stop-Transcript | Out-Null } catch { }
    Read-Host '按回车关闭窗口'
    exit 1
}
try { Start-Transcript -Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'last-run.log') -Force | Out-Null } catch { }

$Root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$BakDir  = Join-Path $Root 'backup'
$Fonts   = Join-Path $env:windir 'Fonts'
$Staging = Join-Path $env:windir ("Temp\OPPOSansSwap-" + (Get-Date -Format 'yyyyMMddHHmmss'))
$Files   = @('msyh.ttc', 'msyhbd.ttc', 'msyhl.ttc')
$SegFile = 'SegUIVar.ttf'
$KeyPath = 'SYSTEM\CurrentControlSet\Control\Session Manager'

function Finish([int]$code, [string]$msg) {
    Write-Host ''
    Write-Host $msg
    Read-Host '按回车关闭窗口'
    exit $code
}

# 没指定档位时的判定顺序：标记文件 → 哈希比对 → output 里唯一的档位
# 优先读上次安装留下的标记文件 —— 光靠哈希比对不可靠：
# 包里的字体重建一次哈希就变了，已装的那份会「认不出来」，从而回落到 w400。
if (-not $Variant) {
    $marker = Join-Path $BakDir 'installed-variant.txt'
    if (Test-Path $marker) {
        $v = (Get-Content -LiteralPath $marker -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($v) { $Variant = $v.Trim() }
    }
    if (-not $Variant) {
        $h = $null
        try { $h = (Get-FileHash -LiteralPath (Join-Path $env:windir 'Fonts\msyh.ttc') -Algorithm SHA256).Hash } catch { }
        foreach ($v in @('w700', 'w600', 'w500', 'w400')) {
            $probe = Join-Path $Root "output\$v\msyh.ttc"
            if ((Test-Path $probe) -and $h -and ((Get-FileHash -LiteralPath $probe -Algorithm SHA256).Hash -eq $h)) {
                $Variant = $v
                break
            }
        }
    }
    if (-not $Variant) {
        # 首次安装时系统字体是原版，哈希匹配不上任何档位；
        # 这时按 output\ 里唯一存在的那档来，不要盲目回落到 w400。
        $avail = @(Get-ChildItem -LiteralPath (Join-Path $Root 'output') -Directory -ErrorAction SilentlyContinue |
                   Where-Object { $_.Name -like 'w*' -and (Test-Path (Join-Path $_.FullName 'msyh.ttc')) })
        if ($avail.Count -eq 1) {
            $Variant = $avail[0].Name
            Write-Host "使用唯一可用的档位：$Variant" -ForegroundColor DarkGray
        } elseif ($avail.Count -gt 1) {
            Finish 1 ("检测到多个档位：" + ($avail.Name -join ', ') + "`n请指定一个，例如：install.cmd 不支持参数，请改用 set-weight.cmd，或删掉不用的档位目录。")
        } else {
            Finish 1 'output\ 里没有任何构建产物。请先运行：python src\build.py --weight 600'
        }
    }
}
$SrcDir = Join-Path $Root "output\$Variant"

Write-Host "=== 安装 OPPO Sans 4.0 作为系统字体（$Variant）===" -ForegroundColor Cyan
Write-Host ''

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host ''
    Write-Host '这个脚本必须以管理员身份运行。' -ForegroundColor Red
    Write-Host '做法：右键此 .cmd 文件 -> 「以管理员身份运行」。' -ForegroundColor Yellow
    Write-Host '（直接双击会以普通权限启动，无法改动系统字体）'
    Read-Host '按回车关闭窗口'
    exit 1
}

# 1. 源文件检查
if (-not (Test-Path $SrcDir)) { Finish 1 "找不到字重档位目录：$SrcDir" }
foreach ($f in ($Files + @($SegFile))) {
    $p = Join-Path $SrcDir $f
    if (-not (Test-Path $p)) { Finish 1 "缺少文件：$p" }
}

# 2. 备份原版（复制出来不受占用影响）
if (-not (Test-Path $BakDir)) { New-Item -ItemType Directory -Path $BakDir | Out-Null }
# 备份原版（复制出来不受占用影响）。经典 Segoe 也要备份：# 构建新字体时要以"最初的原版"为度量参照，装了替换版之后系统里的那份已经不是原版了。
$BackupList = $Files + @($SegFile) + @('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf', 'segoeuil.ttf', 'segoeuisl.ttf')
foreach ($f in $BackupList) {
    $bak = Join-Path $BakDir $f
    $sys = Join-Path $Fonts $f
    if (-not (Test-Path $bak) -and (Test-Path $sys)) {
        Copy-Item -LiteralPath $sys -Destination $bak -Force
        Write-Host "已备份 $f -> backup\$f" -ForegroundColor DarkGray
    }
}

# 2.5 创建系统还原点 —— 出问题时可在「系统属性 - 系统保护」里一键退回
try {
    Checkpoint-Computer -Description 'Before OPPO Sans install' -RestorePointType MODIFY_SETTINGS -ErrorAction Stop | Out-Null
    Write-Host '已尝试创建系统还原点' -ForegroundColor DarkGray
} catch {
    Write-Host '  未创建还原点（系统保护可能未开启），建议手动建一个' -ForegroundColor Yellow
}

# 3. 把新字体放到暂存目录（同一卷，重启时的 move 才有效）# 用唯一目录名，避免“删不掉旧目录 -> New-Item 报已存在”的死循环
New-Item -ItemType Directory -Path $Staging -Force | Out-Null
# 顺手清理以前跑剩下的暂存目录（删不掉就跳过，不影响本次）
Get-ChildItem (Join-Path $env:windir 'Temp') -Directory -Filter 'OPPOSansSwap-*' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -ne $Staging } |
    ForEach-Object { try { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop } catch { } }
foreach ($f in $Files) {
    $dst = Join-Path $Staging $f
    $sys = Join-Path $Fonts $f
    Copy-Item -LiteralPath (Join-Path $SrcDir $f) -Destination $dst -Force
    # 关键：显式给足读权限。新文件从 Temp 移进 Fonts 时会继承 Temp 的限制性 ACL
    # （只有 SYSTEM/管理员可读），fontdrvhost 以用户身份读不到，界面就会继续显示旧字体。
    # 注意：不要整份复制系统字体的 ACL —— 那会把所有者改成 TrustedInstaller，
    # 下一轮就删不掉暂存文件了。只补必要授权即可。
    & icacls.exe $dst /grant '*S-1-5-18:(F)'    | Out-Null   # SYSTEM
    & icacls.exe $dst /grant '*S-1-5-32-544:(F)' | Out-Null  # Administrators
    & icacls.exe $dst /grant '*S-1-5-32-545:(RX)' | Out-Null # Users
    & icacls.exe $dst /grant '*S-1-15-2-1:(RX)'  | Out-Null  # 所有应用程序包
}
Write-Host "已暂存到 $Staging（已补读权限）"
foreach ($f in $Files) {
    $h = (Get-FileHash -LiteralPath (Join-Path $Staging $f) -Algorithm SHA256).Hash.Substring(0, 12)
    Write-Host ("  {0}  {1:N1} MB  sha256:{2}" -f $f, ((Get-Item (Join-Path $Staging $f)).Length / 1MB), $h)
}

# 3.5 Segoe UI Variable 走注册表改指向，不替换原文件。
#     实测：这个文件在启动早期就被占用，PendingFileRenameOperations 里那两条会被消费掉，
#     但改名和搬入都没生效（.swapout 根本没出现）。所以改成“装一份副本 + 改注册表指向”。
$segSrc   = Join-Path $SrcDir $SegFile
# 副本按内容哈希命名：已经注册的副本会被系统占用，覆盖不了；
# 每次内容变了就换新文件名，注册表跟着指过去即可。
$segHash  = (Get-FileHash -LiteralPath $segSrc -Algorithm SHA256).Hash.Substring(0, 8).ToLower()
$segName  = "SegUIVarOPPO-$segHash.ttc"
$segDst   = Join-Path $Fonts $segName
$fontsKey = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'
$segChanged = $false
if (Test-Path $segSrc) {
    $needCopy = $true
    if (Test-Path $segDst) {
        try {
            $needCopy = ((Get-FileHash -LiteralPath $segSrc -Algorithm SHA256).Hash -ne
                         (Get-FileHash -LiteralPath $segDst -Algorithm SHA256).Hash)
        } catch { }
    }
    if ($needCopy) {
        Copy-Item -LiteralPath $segSrc -Destination $segDst -Force
        foreach ($sid in @('*S-1-5-18:(F)', '*S-1-5-32-544:(F)', '*S-1-5-32-545:(RX)', '*S-1-15-2-1:(RX)')) {
            & icacls.exe $segDst /grant $sid | Out-Null
        }
        Write-Host ("已复制 {0} 到 Fonts（{1:N2} MB）" -f $segName, ((Get-Item $segDst).Length / 1MB))
    } else {
        Write-Host "  $segName 已是最新" -ForegroundColor DarkGray
    }
    $curVal = (Get-ItemProperty -Path $fontsKey -Name 'Segoe UI Variable (TrueType)' -ErrorAction SilentlyContinue).'Segoe UI Variable (TrueType)'
    $regBak = Join-Path $BakDir 'segoe-registry.txt'
    if ($curVal -ne $segName) {
        # 只在"当前值确实是原版"且"还没备份过"时记录。
        # 之前无条件重写，第二次安装会把我们自己的副本名当成原值存下来，
        # 导致回滚指向一个不存在（或已被删）的文件。
        if ($curVal -and $curVal -notlike 'SegUIVarOPPO*' -and -not (Test-Path $regBak)) {
            Set-Content -Path $regBak -Value $curVal -Encoding ASCII
        }
        Set-ItemProperty -Path $fontsKey -Name 'Segoe UI Variable (TrueType)' -Value $segName
        Write-Host "注册表已指向 $segName（原值：$curVal）" -ForegroundColor Green
        $segChanged = $true
    } else {
        Write-Host "  注册表已指向 $segName" -ForegroundColor DarkGray
    }
}

# 3.6 经典 Segoe UI —— 开始菜单 / 资源管理器 / 网页里指定的英文走这一家。
#     同样用「装副本 + 改注册表指向」，不替换原文件。
$classicMap = @(
    @{ Entry = 'Segoe UI (TrueType)';           File = 'segoeui.ttf' },
    @{ Entry = 'Segoe UI Bold (TrueType)';      File = 'segoeuib.ttf' },
    @{ Entry = 'Segoe UI Semibold (TrueType)';  File = 'seguisb.ttf' },
    @{ Entry = 'Segoe UI Light (TrueType)';     File = 'segoeuil.ttf' },
    @{ Entry = 'Segoe UI Semilight (TrueType)'; File = 'segoeuisl.ttf' }
)
$classicDir = Join-Path $Root 'output\segclassic'
$classicBak = Join-Path $BakDir 'segoe-classic-registry.txt'
$classicChanged = $false
if (Test-Path $classicDir) {
    $lines = @()
    foreach ($m in $classicMap) {
        $srcF = Join-Path $classicDir $m.File
        if (-not (Test-Path $srcF)) { continue }
        $fh = (Get-FileHash -LiteralPath $srcF -Algorithm SHA256).Hash.Substring(0, 8).ToLower()
        $newName = "SegoeUIOppo-$fh-$($m.File)"
        $dst = Join-Path $Fonts $newName
        if (-not (Test-Path $dst)) {
            Copy-Item -LiteralPath $srcF -Destination $dst -Force
            foreach ($sid in @('*S-1-5-18:(F)', '*S-1-5-32-544:(F)', '*S-1-5-32-545:(RX)', '*S-1-15-2-1:(RX)')) {
                & icacls.exe $dst /grant $sid | Out-Null
            }
        }
        $item = Get-ItemProperty -Path $fontsKey -Name $m.Entry -ErrorAction SilentlyContinue
        $cur = $null
        if ($item) { $cur = $item.PSObject.Properties[$m.Entry].Value }
        if ($cur -ne $newName) {
            # 只记真正的原值：当前指向如果已经是我们自己的副本，说明装过一次了，
            # 再记下来会把"自己的副本名"当成原版，回滚时指向一个非原版文件。
            if ($cur -and $cur -notlike 'SegoeUIOppo-*' -and -not (Test-Path $classicBak)) {
                $lines += ($m.Entry + '=' + $cur)
            }
            Set-ItemProperty -Path $fontsKey -Name $m.Entry -Value $newName
            $classicChanged = $true
            Write-Host ("  {0} -> {1}" -f $m.Entry, $newName) -ForegroundColor Green
        }
    }
    if ($lines.Count -gt 0 -and -not (Test-Path $classicBak)) {
        Set-Content -Path $classicBak -Value $lines -Encoding ASCII
    }
    if (-not $classicChanged) { Write-Host '  经典 Segoe UI 已指向副本' -ForegroundColor DarkGray }
}

# 3.7 补一个 Semibold 面。界面标题请求 600，家族里若只有 400/700，
#     DirectWrite 只能落到 700 —— 比手机上的 SemiBold 粗一档。
$semSrc = Join-Path $SrcDir 'msyhsc.ttf'
$semChanged = $false
if (Test-Path $semSrc) {
    $semHash = (Get-FileHash -LiteralPath $semSrc -Algorithm SHA256).Hash.Substring(0, 8).ToLower()
    $semName = "MSYHSC-OPPO-$semHash.ttf"
    $semDst = Join-Path $Fonts $semName
    if (-not (Test-Path $semDst)) {
        Copy-Item -LiteralPath $semSrc -Destination $semDst -Force
        foreach ($sid in @('*S-1-5-18:(F)', '*S-1-5-32-544:(F)', '*S-1-5-32-545:(RX)', '*S-1-15-2-1:(RX)')) {
            & icacls.exe $semDst /grant $sid | Out-Null
        }
        Write-Host "  已安装 Semibold 面：$semName" -ForegroundColor Green
    }
    $semEntry = 'Microsoft YaHei UI Semibold (TrueType)'
    $item = Get-ItemProperty -Path $fontsKey -Name $semEntry -ErrorAction SilentlyContinue
    $cur = $null
    if ($item) { $cur = $item.PSObject.Properties[$semEntry].Value }
    if ($cur -ne $semName) {
        Set-ItemProperty -Path $fontsKey -Name $semEntry -Value $semName
        Write-Host "  已注册 $semEntry -> $semName" -ForegroundColor Green
        $semChanged = $true
    }
} else {
    Write-Host '  未找到 msyhsc.ttf，跳过 Semibold 面（标题仍会落到 700）' -ForegroundColor DarkGray
}

# 3.8 等线（DengXian）——系统里唯一没被换过的西文来源。
#      只换它的拉丁字形，中文和度量原样保留，所以 Office 文档排版不受影响。
$dengMap = @(
    @{ Entry = 'DengXian (TrueType)';       File = 'DengXian.ttf' },
    @{ Entry = 'DengXian Bold (TrueType)';  File = 'DengXianBold.ttf' },
    @{ Entry = 'DengXian Light (TrueType)'; File = 'DengXianLight.ttf' }
)
$dengBak = Join-Path $BakDir 'dengxian-registry.txt'
$dengChanged = $false
foreach ($m in $dengMap) {
    $srcF = Join-Path $classicDir $m.File
    if (-not (Test-Path $srcF)) { continue }
    $fh = (Get-FileHash -LiteralPath $srcF -Algorithm SHA256).Hash.Substring(0, 8).ToLower()
    $newName = "DengXianOPPO-$fh.ttf"
    $dst = Join-Path $Fonts $newName
    if (-not (Test-Path $dst)) {
        Copy-Item -LiteralPath $srcF -Destination $dst -Force
        foreach ($sid in @('*S-1-5-18:(F)', '*S-1-5-32-544:(F)', '*S-1-5-32-545:(RX)', '*S-1-15-2-1:(RX)')) {
            & icacls.exe $dst /grant $sid | Out-Null
        }
    }
    $item = Get-ItemProperty -Path $fontsKey -Name $m.Entry -ErrorAction SilentlyContinue
    $cur = $null
    if ($item) { $cur = $item.PSObject.Properties[$m.Entry].Value }
    if ($cur -ne $newName) {
        if ($cur -and $cur -notlike 'DengXianOPPO*' -and -not (Test-Path $dengBak)) {
            Add-Content -Path $dengBak -Value ($m.Entry + '=' + $cur) -Encoding ASCII
        }
        Set-ItemProperty -Path $fontsKey -Name $m.Entry -Value $newName
        Write-Host ("  {0} -> {1}" -f $m.Entry, $newName) -ForegroundColor Green
        $dengChanged = $true
    }
}

# 4. 只对真正需要替换的文件登记（已经一致的不动，避免把留底的 .swapout 白白删掉）
$needs = @()
foreach ($f in $Files) {
    $sys = Join-Path $Fonts $f
    $stg = Join-Path $Staging $f
    $same = $false
    if ((Test-Path $sys) -and (Test-Path $stg)) {
        try {
            $same = ((Get-FileHash -LiteralPath $sys -Algorithm SHA256).Hash -eq
                     (Get-FileHash -LiteralPath $stg -Algorithm SHA256).Hash)
        } catch { }
    }
    if ($same) { Write-Host "  已一致，跳过 $f" -ForegroundColor DarkGray }
    else { $needs += $f; Write-Host "  待替换 $f" }
}
if ($needs.Count -eq 0) {
    if ($segChanged -or $classicChanged -or $semChanged -or $dengChanged) { Finish 0 '只更新了注册表指向，重启电脑后生效。' }
    Finish 0 '当前已经是最新状态，不需要重启。'
}

# 上次残留的 .swapout 现在就删掉（此时文件没被占用，删得动）。
# 不能把它排进队列——smss 遇到「删除不存在的文件」会失败并停止处理后续项，
# 之前 SegUIVar 就是卡在这一步没换成功。
foreach ($f in $needs) {
    $sw = Join-Path $Fonts ($f + '.swapout')
    if (Test-Path $sw) {
        try { Remove-Item -LiteralPath $sw -Force -ErrorAction Stop }
        catch { Finish 1 "无法删除残留文件 $sw，请手动删掉后重试。已中止，字体没有改动。" }
    }
}

$ops = New-Object System.Collections.Generic.List[string]
foreach ($f in $needs) {
    $ops.Add("\??\$Fonts\$f")
    $ops.Add("\??\$Fonts\$f.swapout")
    $ops.Add("\??\$Staging\$f")
    $ops.Add("\??\$Fonts\$f")
}

$rk = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($KeyPath, $true)
if ($null -eq $rk) { Finish 1 "打不开注册表键：HKLM\$KeyPath" }
$existing = $rk.GetValue('PendingFileRenameOperations', $null,
    [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
$all = New-Object System.Collections.Generic.List[string]
if ($existing) { foreach ($s in [string[]]$existing) { $all.Add($s) } }
foreach ($s in $ops) { $all.Add($s) }
$rk.SetValue('PendingFileRenameOperations', [string[]]$all,
    [Microsoft.Win32.RegistryValueKind]::MultiString)
$rk.Close()

# 5. 读回验证
$rk2 = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($KeyPath, $false)
$back = [string[]]$rk2.GetValue('PendingFileRenameOperations', $null,
    [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
$rk2.Close()
$mine = ($back | Where-Object { $_ -like '*OPPOSansSwap*' -or $_ -like '*.swapout' }).Count
Write-Host ''
if ($mine -lt ($needs.Count * 2)) {
    Finish 1 "替换队列写入异常（读到 $mine 条，应为 $($needs.Count * 2)）。已中止，系统字体没有改动。"
}
Write-Host "替换队列已登记（$mine 条），共 $($back.Count) 条待处理。" -ForegroundColor Green
Write-Host "原版字体已备份在：$BakDir" -ForegroundColor DarkGray
# 记下这次装的档位，下次自动识别用（哈希会因为重建而变化，不可靠）
try { Set-Content -Path (Join-Path $BakDir 'installed-variant.txt') -Value $Variant -Encoding ASCII } catch { }
Write-Host ''
Write-Host '本次会执行的文件操作：' -ForegroundColor DarkGray
for ($i = 0; $i -lt $ops.Count; $i += 2) {
    Write-Host ('   ' + $ops[$i] + '  ->  ' + $ops[$i + 1]) -ForegroundColor DarkGray
}

Finish 0 @'
现在必须重启电脑，字体才会真正换掉。

重启后双击「看看装上了没.cmd」确认是否生效。
如果没变化，或者界面出现异常，双击「还原微软雅黑.cmd」再重启一次即可回到原样。
'@
