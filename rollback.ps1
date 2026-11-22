# 还原：把微软雅黑换回官方原版（需管理员，重启后生效）
#
# 与 install.ps1 同一套机制：字体文件被占用，只能登记到重启时替换队列。
# 优先用 backup\ 里的原版；没有的话退而使用 .swapout（安装时现场改名留下的原文件）。
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
$Staging = Join-Path $env:windir ("Temp\OPPOSansRestore-" + (Get-Date -Format 'yyyyMMddHHmmss'))
$Files   = @('msyh.ttc', 'msyhbd.ttc', 'msyhl.ttc')
$KeyPath = 'SYSTEM\CurrentControlSet\Control\Session Manager'

function Finish([int]$code, [string]$msg) {
    Write-Host ''
    Write-Host $msg
    Read-Host '按回车关闭窗口'
    exit $code
}

Write-Host '=== 还原系统微软雅黑 ===' -ForegroundColor Cyan
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

# 0. 还原 Segoe UI Variable 的注册表指向（新版方案，不替换原文件）
$fontsKey = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'
$regBak   = Join-Path $BakDir 'segoe-registry.txt'
$origVal  = 'SegUIVar.ttf'
if (Test-Path $regBak) {
    $t = (Get-Content -LiteralPath $regBak -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($t) { $origVal = $t.Trim() }
}
$curVal = (Get-ItemProperty -Path $fontsKey -Name 'Segoe UI Variable (TrueType)' -ErrorAction SilentlyContinue).'Segoe UI Variable (TrueType)'
if ($curVal -like 'SegUIVarOPPO*.ttc') {
    Set-ItemProperty -Path $fontsKey -Name 'Segoe UI Variable (TrueType)' -Value $origVal
    Write-Host "注册表已还原为 $origVal" -ForegroundColor Green
} else {
    Write-Host "注册表当前指向 $curVal，无需改动" -ForegroundColor DarkGray
}
# 清掉所有自己装的副本（被占用的跳过，重启后手动删）
Get-ChildItem -LiteralPath $Fonts -Filter 'SegUIVarOPPO*.ttc' -ErrorAction SilentlyContinue | ForEach-Object {
    try { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop; Write-Host ("已删除 " + $_.Name) -ForegroundColor Green }
    catch { Write-Host ("  " + $_.Name + " 正在使用，重启后可删") -ForegroundColor Yellow }
}

# 0.5 还原经典 Segoe UI 的注册表指向
$classicBak = Join-Path $BakDir 'segoe-classic-registry.txt'
if (Test-Path $classicBak) {
    foreach ($line in (Get-Content -LiteralPath $classicBak)) {
        if (-not $line) { continue }
        $i = $line.IndexOf('=')
        if ($i -lt 1) { continue }
        $entry = $line.Substring(0, $i)
        $file = $line.Substring($i + 1)
        Set-ItemProperty -Path $fontsKey -Name $entry -Value $file
        Write-Host ("  {0} 还原为 {1}" -f $entry, $file) -ForegroundColor Green
    }
}
Get-ChildItem -LiteralPath $Fonts -Filter 'SegoeUIOppo-*.ttf' -ErrorAction SilentlyContinue | ForEach-Object {
    try { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop; Write-Host ("已删除 " + $_.Name) -ForegroundColor Green }
    catch { Write-Host ("  " + $_.Name + " 正在使用，重启后可删") -ForegroundColor Yellow }
}

# 1. 找原版来源
New-Item -ItemType Directory -Path $Staging -Force | Out-Null
Get-ChildItem (Join-Path $env:windir 'Temp') -Directory -Filter 'OPPOSansRestore-*' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -ne $Staging } |
    ForEach-Object { try { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop } catch { } }
$found = 0
foreach ($f in $Files) {
    $src = $null
    $bak = Join-Path $BakDir $f
    $sw  = Join-Path $Fonts ($f + '.swapout')
    if (Test-Path $bak) { $src = $bak }
    elseif (Test-Path $sw) { $src = $sw }
    if ($src) {
        $dst = Join-Path $Staging $f
        Copy-Item -LiteralPath $src -Destination $dst -Force
        # 关键：必须补读权限。暂存在 C:\Windows\Temp 下，移动进 Fonts 后
        # 会继承 Temp 的限制性 ACL，fontdrvhost 以用户身份读不到 → 中文回落到宋体
        # （表现：字号小一档、纯点阵、带衬线尖角）。install.ps1 一直有这一步，
        # rollback.ps1 之前漏了，导致「看着像没还原」。
        foreach ($sid in @('*S-1-5-18:(F)', '*S-1-5-32-544:(F)', '*S-1-5-32-545:(RX)', '*S-1-15-2-1:(RX)')) {
            & icacls.exe $dst /grant $sid | Out-Null
        }
        $found++
        Write-Host "  来源 $f <- $src"
    } else {
        Write-Host "  找不到 $f 的原版备份" -ForegroundColor Yellow
    }
}
if ($found -eq 0) { Finish 1 '没有任何可用的原版备份，未做任何改动。' }

# 2. 登记重启时替换
foreach ($f in $Files) {
    $ro = Join-Path $Fonts ($f + '.restoreout')
    if (Test-Path $ro) { try { Remove-Item -LiteralPath $ro -Force -ErrorAction SilentlyContinue } catch { } }
}

$ops = New-Object System.Collections.Generic.List[string]
foreach ($f in $Files) {
    if (-not (Test-Path (Join-Path $Staging $f))) { continue }
    $ops.Add("\??\$Fonts\$f")
    $ops.Add("\??\$Fonts\$f.restoreout")
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

$rk2 = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($KeyPath, $false)
$back = [string[]]$rk2.GetValue('PendingFileRenameOperations', $null,
    [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
$rk2.Close()
$mine = ($back | Where-Object { $_ -like '*OPPOSansRestore*' -or $_ -like '*.restoreout' }).Count
if ($mine -lt ($found * 2)) {
    Finish 1 "替换队列写入异常（读到 $mine 条，应为 $($found * 2)）。"
}

Finish 0 @'
已登记还原，重启后生效。

如果重启后字体仍是 OPPO Sans，说明队列没被执行，
可以进安全模式再跑一次本程序（安全模式下字体占用更少）。
'@
