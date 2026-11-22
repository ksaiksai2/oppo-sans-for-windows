# 查看系统还原点（需管理员）
$ErrorActionPreference = 'Continue'
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host '请右键此 .cmd 文件 →「以管理员身份运行」' -ForegroundColor Red
    Read-Host '按回车关闭'
    exit 1
}

Write-Host '=== 系统还原点 ===' -ForegroundColor Cyan
Write-Host ''
$pts = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue)
if ($pts.Count -eq 0) {
    Write-Host '  没有还原点，或系统保护未开启。' -ForegroundColor Yellow
} else {
    Write-Host ("  共 {0} 个：" -f $pts.Count)
    foreach ($p in $pts) {
        $t = $p.CreationTime
        if ($t -is [string]) { try { $t = [datetime]::Parse($t) } catch { } }
        $ts = if ($t -is [datetime]) { $t.ToString('yyyy-MM-dd HH:mm:ss') } else { [string]$t }
        Write-Host ("  #{0,-4} {1}  {2}" -f $p.SequenceNumber, $ts, $p.Description)
    }
}
Write-Host ''
$sp = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore' -ErrorAction SilentlyContinue
Write-Host ("  创建频率限制：{0} 分钟" -f $sp.SystemRestorePointCreationFrequency)
Read-Host '按回车关闭窗口'
