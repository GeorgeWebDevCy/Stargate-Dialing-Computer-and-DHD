param(
    [switch]$SkipExeBuild,
    [string]$AppVersion = '1.0.0'
)

$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$issFile = Join-Path $projectRoot 'installer\StargateDialer.iss'
$localIscc = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'

if (-not (Test-Path $issFile)) {
    throw "Installer script not found: $issFile"
}

if (-not $SkipExeBuild) {
    Write-Host 'Building application EXE first...'
    & (Join-Path $projectRoot 'build_exe.ps1')
}

$exePath = Join-Path $projectRoot 'dist\StargateDialer.exe'
if (-not (Test-Path $exePath)) {
    throw "Expected EXE not found: $exePath"
}

$isccCommand = Get-Command iscc -ErrorAction SilentlyContinue
if ($isccCommand) {
    $isccPath = $isccCommand.Source
} elseif (Test-Path $localIscc) {
    $isccPath = $localIscc
} else {
    throw "ISCC.exe not found. Install Inno Setup 6 first."
}

Write-Host "Using ISCC: $isccPath"
Write-Host 'Building installer...'

Push-Location (Join-Path $projectRoot 'installer')
try {
    & $isccPath "/DAppVersion=$AppVersion" 'StargateDialer.iss'
    if ($LASTEXITCODE -ne 0) {
        throw "ISCC failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$installerOutput = Join-Path $projectRoot 'installer\output'
if (Test-Path $installerOutput) {
    Write-Host 'Installer build complete. Files:'
    Get-ChildItem $installerOutput -File | Select-Object FullName, Length, LastWriteTime
} else {
    throw "Installer output directory not found: $installerOutput"
}
