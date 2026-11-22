# 清理系统侧的残留文件（需管理员）
# 1) C:\Windows\Fonts\*.swapout   —— 之前文件替换留下的现场副本，内容其实是我们自己的字体
# 2) C:\Windows\Fonts\SegUIVarOPPO*.ttc —— 过渡期的旧副本，只要不是注册表当前指向的就可以删
# 原版雅黑在 backup\ 里，这份不影响回滚。
$ErrorActionPreference = 'Stop'

$Fonts = Join-Path $env:windir 'Fonts'
$Key   = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'

function Finish([int]$code, [string]$msg) {
    Write-Host ''
    Write-Host $msg
    Read-Host '按回车关闭窗口'
    exit $code
}

Write-Host '=== 清理系统侧残留 ===' -ForegroundColor Cyan
Write-Host ''

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Finish 1 '这个脚本必须以管理员身份运行。请右键此 .cmd 文件 →「以管理员身份运行」。'
}

# 注册表当前正在用的副本，不能删
$inUse = @()
foreach ($e in @('Segoe UI Variable (TrueType)', 'Segoe UI (TrueType)', 'Segoe UI Bold (TrueType)',
                 'Segoe UI Semibold (TrueType)', 'Segoe UI Light (TrueType)', 'Segoe UI Semilight (TrueType)')) {
    $v = $null
    try { $v = (Get-ItemProperty -Path $Key -Name $e -ErrorAction Stop).PSObject.Properties[$e].Value } catch { }
    if ($v) { $inUse += $v }
}

$freed = 0
$items = @()
$items += Get-ChildItem -LiteralPath $Fonts -Filter '*.swapout' -File -ErrorAction SilentlyContinue
$items += Get-ChildItem -LiteralPath $Fonts -Filter '*.restoreout' -File -ErrorAction SilentlyContinue
$items += Get-ChildItem -LiteralPath $Fonts -Filter 'SegUIVarOPPO*.ttc' -File -ErrorAction SilentlyContinue

foreach ($f in $items) {
    if ($inUse -contains $f.Name) {
        Write-Host ("  跳过（正在使用）：" + $f.Name) -ForegroundColor DarkGray
        continue
    }
    try {
        $sz = $f.Length
        Remove-Item -LiteralPath $f.FullName -Force -ErrorAction Stop
        $freed += $sz
        Write-Host ("  已删除 {0}  {1:N1} MB" -f $f.Name, ($sz / 1MB)) -ForegroundColor Green
    } catch {
        Write-Host ("  删不掉：" + $f.Name + "（重启后再试）") -ForegroundColor Yellow
    }
}

Finish 0 ("清理完成，释放 {0:N1} MB。" -f ($freed / 1MB))
