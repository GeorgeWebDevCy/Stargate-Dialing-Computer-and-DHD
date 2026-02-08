param(
    [switch]$OneDir
)

$ErrorActionPreference = 'Stop'
$iconPath = Join-Path $PSScriptRoot 'assets\stargate_icon.ico'

if (-not (Test-Path $iconPath)) {
    throw "Icon not found: $iconPath"
}

Write-Host 'Installing build dependencies...'
python -m pip install -r requirements-build.txt

$modeArgs = @('--onefile')
if ($OneDir) {
    $modeArgs = @('--onedir')
}

Write-Host 'Building StargateDialer.exe...'
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name StargateDialer `
    --icon $iconPath `
    @modeArgs `
    stargate_app.py

Write-Host "Build complete. Output: dist\\StargateDialer.exe"
