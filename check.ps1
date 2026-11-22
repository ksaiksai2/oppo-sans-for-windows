# 检查：当前系统里装的是原版雅黑还是哪个字重档的替换版（不需要管理员）
$ErrorActionPreference = 'Stop'

$Root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Fonts   = Join-Path $env:windir 'Fonts'
$Files   = @('msyh.ttc', 'msyhbd.ttc', 'msyhl.ttc')
$KeyPath = 'SYSTEM\CurrentControlSet\Control\Session Manager'
$Labels  = @{
    'w400' = 'OPPO Sans 常规 400'
    'w500' = 'OPPO Sans 中粗 500'
    'w600' = 'OPPO Sans 半粗 600'
    'w700' = 'OPPO Sans 最粗 700'
}

function HashOf([string]$p) {
    if (-not (Test-Path -LiteralPath $p)) { return $null }
    try { return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash } catch { return 'DENIED' }
}

Write-Host '=== 当前系统字体状态 ===' -ForegroundColor Cyan
Write-Host ''

$pending = $null
try {
    $rk = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($KeyPath, $false)
    $pending = [string[]]$rk.GetValue('PendingFileRenameOperations', $null,
        [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    $rk.Close()
} catch { }
$mine = @()
if ($pending) { $mine = @($pending | Where-Object { $_ -like '*OPPOSans*' -or $_ -like '*.swapout' -or $_ -like '*.restoreout' }) }

$states = @()
foreach ($f in $Files) {
    $sys = Join-Path $Fonts $f
    $hs  = HashOf $sys
    $state = '未知版本'
    $color = 'Gray'
    if ($null -eq $hs) {
        $state = '文件不存在'; $color = 'Red'
    } elseif ($hs -eq 'DENIED') {
        $state = '没有读取权限（跑 fix-acl.cmd）'; $color = 'Red'
    } else {
        foreach ($v in @('w700', 'w600', 'w500', 'w400')) {
            $vp = Join-Path $Root "output\$v\$f"
            if ((Test-Path $vp) -and (HashOf $vp) -eq $hs) { $state = $Labels[$v]; $color = 'Green'; break }
        }
        if ($state -eq '未知版本' -and (HashOf (Join-Path $Root "backup\$f")) -eq $hs) {
            $state = '微软雅黑原版'; $color = 'DarkGray'
        }
    }
    if ($state -like 'OPPO Sans*') {
        if ($f -eq 'msyhbd.ttc') { $state += '（粗体槽）' }
        elseif ($f -eq 'msyhl.ttc') { $state += '（细体槽）' }
    }
    $states += $state
    Write-Host ("  {0,-12} {1}" -f $f, $state) -ForegroundColor $color
    $len = 0
    try { $len = (Get-Item -LiteralPath $sys -Force).Length / 1MB } catch { }
    $short = if ($hs -and $hs.Length -ge 16) { $hs.Substring(0, 16) } else { $hs }
    Write-Host ("      {0:N2} MB  {1}" -f $len, $short) -ForegroundColor DarkGray
}

# Segoe UI Variable 走注册表指向，单独报告
$fontsKey = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'
$segVal = $null
try { $segVal = (Get-ItemProperty -Path $fontsKey -Name 'Segoe UI Variable (TrueType)' -ErrorAction Stop).'Segoe UI Variable (TrueType)' } catch { }
$segOk = ($segVal -like 'SegUIVarOPPO*.ttc') -and (Test-Path (Join-Path $Fonts $segVal))
Write-Host ("  {0,-12} {1}" -f '界面壳英文', $(if ($segOk) { 'OPPO Sans（已生效）' } else { "未生效（注册表指向 $segVal）" })) -ForegroundColor $(if ($segOk) { 'Green' } else { 'DarkGray' })

# 经典 Segoe UI（开始菜单 / 资源管理器 / 网页里指定的英文）
$classicOk = 0
foreach ($e in @('Segoe UI (TrueType)', 'Segoe UI Bold (TrueType)', 'Segoe UI Semibold (TrueType)', 'Segoe UI Light (TrueType)', 'Segoe UI Semilight (TrueType)')) {
    $v = $null
    try { $v = (Get-ItemProperty -Path $fontsKey -Name $e -ErrorAction Stop).PSObject.Properties[$e].Value } catch { }
    if ($v -like 'SegoeUIOppo-*') { $classicOk++ }
}
$clText = "$classicOk / 5 已替换"
Write-Host ("  {0,-12} {1}" -f '经典Segoe', $clText) -ForegroundColor $(if ($classicOk -eq 5) { 'Green' } else { 'DarkGray' })

Write-Host ''
if ($states -contains '没有读取权限（跑 fix-acl.cmd）') {
    Write-Host '字体文件权限不对，系统读不到，界面会继续显示旧字体。' -ForegroundColor Red
    Write-Host '双击 fix-acl.cmd（管理员），然后重启。' -ForegroundColor Yellow
} elseif ($mine.Count -gt 0) {
    Write-Host "有 $($mine.Count) 条待执行的重启替换记录 —— 已登记但还没重启。" -ForegroundColor Yellow
} elseif ($states[0] -like 'OPPO Sans*') {
    Write-Host ("替换已生效：" + $states[0]) -ForegroundColor Green
    Write-Host '想换粗细：双击 set-weight.cmd'
} else {
    Write-Host '当前是原版雅黑。要换的话双击 install.cmd。'
}

Write-Host ''
Read-Host '按回车关闭窗口'
