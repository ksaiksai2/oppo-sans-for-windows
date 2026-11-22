# 从 600\ 或 700\ 目录把字体同步到 output\，然后调用安装脚本。
# 由两个文件夹里的「一键安装.cmd」传入档位号（600 或 700）。
param([Parameter(Mandatory=$true)][string]$Tier)

$ErrorActionPreference = 'Stop'
$Repo   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $Repo $Tier
$Out    = Join-Path $Repo 'output'
$Variant = "w$Tier"

if (-not (Test-Path $Source)) { Write-Host "找不到档位目录：$Source" -ForegroundColor Red; Read-Host '按回车关闭'; exit 1 }

Write-Host "=== 切换到 $Variant ===" -ForegroundColor Cyan
Write-Host ''

# 1) 把该档的主文件放进 output\w<Tier>
$dst = Join-Path $Out $Variant
New-Item -ItemType Directory -Path $dst -Force | Out-Null
foreach ($f in @('msyh.ttc','msyhbd.ttc','msyhl.ttc','SegUIVar.ttf','msyhsc.ttf')) {
    $srcF = Join-Path $Source $f
    if (-not (Test-Path $srcF)) { Write-Host "  缺少 $f，中止" -ForegroundColor Red; Read-Host '按回车关闭'; exit 1 }
    Copy-Item -LiteralPath $srcF -Destination (Join-Path $dst $f) -Force
}
Write-Host "  主文件已同步到 output\$Variant" -ForegroundColor DarkGray

# 2) 把该档的英文三件套同步到 output\segclassic
$segSrc = Join-Path $Source 'segclassic'
$segDst = Join-Path $Out 'segclassic'
New-Item -ItemType Directory -Path $segDst -Force | Out-Null
Get-ChildItem -LiteralPath $segSrc -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $segDst $_.Name) -Force
}
Write-Host "  英文字体已同步到 output\segclassic（$Tier 档映射）" -ForegroundColor DarkGray

# 3) 写档位标记
$marker = Join-Path $Repo 'backup\installed-variant.txt'
New-Item -ItemType Directory -Path (Split-Path $marker) -Force | Out-Null
Set-Content -Path $marker -Value $Variant -Encoding ASCII

Write-Host ''
Write-Host '=== 调用安装脚本 ===' -ForegroundColor Cyan
& (Join-Path $Repo 'install.ps1')
exit $LASTEXITCODE
