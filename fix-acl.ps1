# 修复：把已替换的字体文件的权限改回系统标准（需管理员，重启后生效）
#
# 事故原因：新字体从 C:\Windows\Temp 移进 Fonts，继承了 Temp 的限制性 ACL
# （只有 SYSTEM/Administrators 可读）。fontdrvhost.exe 以用户身份运行，
# 读不到文件，于是系统继续用字体缓存里的旧雅黑 —— 看起来就是「没换成功」。
#
# 修法：把原文件（*.swapout）的 ACL 整份复制到新文件上，并把所有者交回 TrustedInstaller。
$ErrorActionPreference = 'Stop'

$Fonts = Join-Path $env:windir 'Fonts'
$Files = @('msyh.ttc', 'msyhbd.ttc', 'msyhl.ttc')

function Finish([int]$code, [string]$msg) {
    Write-Host ''
    Write-Host $msg
    Read-Host '按回车关闭窗口'
    exit $code
}

Write-Host '=== 修复字体文件权限 ===' -ForegroundColor Cyan
Write-Host ''

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Finish 1 '需要管理员权限。请右键本程序，选择「以管理员身份运行」。'
}

$ok = $true
foreach ($f in $Files) {
    $sys = Join-Path $Fonts $f
    $ref = $sys + '.swapout'
    Write-Host "处理 $f"
    if (-not (Test-Path $sys)) { Write-Host '  文件不存在，跳过' -ForegroundColor Yellow; continue }
    $hasRef = Test-Path $ref
    if (-not $hasRef) { Write-Host '  没有 .swapout 可参照，直接补标准授权' -ForegroundColor DarkGray }
    try {
        & takeown.exe /f $sys /a | Out-Null
        & icacls.exe $sys /grant '*S-1-5-32-544:F' | Out-Null

        # 有参照文件就整份复制它的 ACL（含 TrustedInstaller 所有者）；没有就跳过
        if ($hasRef) {
            try {
                $acl = Get-Acl -LiteralPath $ref
                Set-Acl -LiteralPath $sys -AclObject $acl
            } catch {
                Write-Host ('  ACL 复制失败（' + $_.Exception.Message + '），改用显式授权') -ForegroundColor Yellow
            }
        }

        # 双保险：显式补上用户组与应用包组的读取权限
        & icacls.exe $sys /grant '*S-1-5-32-545:(RX)' | Out-Null
        & icacls.exe $sys /grant '*S-1-15-2-1:(RX)' | Out-Null
        & icacls.exe $sys /setowner 'NT SERVICE\TrustedInstaller' | Out-Null

        $txt = (& icacls.exe $sys | Out-String)
        if ($txt -match 'Users|用户') {
            Write-Host '  权限已修好（含有用户读取权限）' -ForegroundColor Green
        } else {
            Write-Host '  权限可能仍不完整，请把上面的 icacls 输出发给开发者' -ForegroundColor Yellow
            $ok = $false
        }
    } catch {
        Write-Host ('  失败：' + $_.Exception.Message) -ForegroundColor Red
        $ok = $false
    }
}

# 清掉字体缓存，逼系统重新读文件
Write-Host '清理字体缓存...'
try { Stop-Service -Name FontCache -Force -ErrorAction Stop } catch { }
$cacheDirs = @(
    (Join-Path $env:windir 'ServiceProfiles\LocalService\AppData\Local\FontCache'),
    (Join-Path $env:LOCALAPPDATA 'FontCache'),
    (Join-Path $env:windir 'System32\FNTCACHE.DAT')
)
foreach ($d in $cacheDirs) {
    if (Test-Path $d -PathType Container) {
        try { Get-ChildItem -LiteralPath $d -File -Force | Remove-Item -Force -ErrorAction SilentlyContinue } catch { }
    } elseif (Test-Path $d) {
        try { Remove-Item -LiteralPath $d -Force -ErrorAction SilentlyContinue } catch { }
    }
}
try { Start-Service -Name FontCache -ErrorAction Stop } catch { }

if ($ok) {
    Finish 0 @'
权限已修复。请重启电脑，系统会重新读取字体文件。

重启后双击 check.cmd 确认；界面应该变成 OPPO Sans 了。
'@
} else {
    Finish 1 @'
部分文件没修成功。系统字体功能可能异常，
建议先双击 rollback.cmd 还原，再联系开发者。
'@
}
