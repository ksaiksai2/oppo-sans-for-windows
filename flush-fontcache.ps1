# 清字体缓存 + 删残留副本（需管理员，重启后生效）
#
# 为什么需要：GDI 直接从注册表读字体，每次都准；但 XAML 界面（开始菜单、通知中心、
# 设置）走 DirectWrite，它有自己的字体集合缓存。安装和回滚来回折腾之后，
# 缓存里可能残留旧的族映射，导致同一页面里一部分文字用新映射、一部分用旧缓存。
$ErrorActionPreference = 'Stop'

$Fonts = Join-Path $env:windir 'Fonts'
$Key   = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'

function Finish([int]$code, [string]$msg) {
    Write-Host ''
    Write-Host $msg
    Read-Host '按回车关闭窗口'
    exit $code
}

Write-Host '=== 清字体缓存 ===' -ForegroundColor Cyan
Write-Host ''

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Finish 1 '这个脚本必须以管理员身份运行。请右键此 .cmd 文件 ->「以管理员身份运行」。'
}

# 1. 删掉我们留下的所有副本/残留（正在注册表里用的跳过）
$inUse = @()
foreach ($p in (Get-ItemProperty -Path $Key).PSObject.Properties) { $inUse += $p.Value }
$freed = 0
foreach ($pat in @('SegUIVarOPPO*.ttc', 'SegoeUIOppo-*.ttf', '*.swapout', '*.restoreout')) {
    Get-ChildItem -LiteralPath $Fonts -Filter $pat -File -ErrorAction SilentlyContinue | ForEach-Object {
        if ($inUse -contains $_.Name) { Write-Host ("  跳过（仍在用）：" + $_.Name) -ForegroundColor DarkGray; return }
        try {
            $sz = $_.Length
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop
            $freed += $sz
            Write-Host ("  已删除 {0}  {1:N1} MB" -f $_.Name, ($sz/1MB)) -ForegroundColor Green
        } catch {
            Write-Host ("  删不掉：" + $_.Name) -ForegroundColor Yellow
        }
    }
}

# 2. 停字体缓存服务
Write-Host '停止字体缓存服务...'
try { Stop-Service -Name FontCache -Force -ErrorAction Stop } catch { Write-Host '  （服务未运行，继续）' -ForegroundColor DarkGray }

# 3. 删缓存文件
$targets = @(
    (Join-Path $env:windir 'System32\FNTCACHE.DAT'),
    (Join-Path $env:windir 'ServiceProfiles\LocalService\AppData\Local\FontCache'),
    (Join-Path $env:LOCALAPPDATA 'FontCache')
)
foreach ($t in $targets) {
    if (-not (Test-Path -LiteralPath $t)) { continue }
    if ((Get-Item -LiteralPath $t) -is [System.IO.DirectoryInfo]) {
        Get-ChildItem -LiteralPath $t -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
            try { $sz = $_.Length; Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop; $freed += $sz
                  Write-Host ("  已删除缓存 " + $_.Name) -ForegroundColor Green } catch { }
        }
    } else {
        try { $sz = (Get-Item -LiteralPath $t).Length; Remove-Item -LiteralPath $t -Force -ErrorAction Stop; $freed += $sz
              Write-Host '  已删除 FNTCACHE.DAT' -ForegroundColor Green }
        catch { Write-Host '  FNTCACHE.DAT 被占用（正常，重启会自动重建）' -ForegroundColor DarkGray }
    }
}

try { Start-Service -Name FontCache -ErrorAction Stop } catch { }

Finish 0 ("释放 {0:N1} MB。`n`n请重启电脑，然后看开始菜单 / 通知中心是否还有「一页多种字体」。" -f ($freed/1MB))
