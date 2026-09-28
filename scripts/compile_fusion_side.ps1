. "$PSScriptRoot\..\tools\logger.ps1"
$project = Split-Path $PSScriptRoot -Parent
$uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
Write-Log "ставлю интерпретатор 3.14, если его ещё нет"
& $uv python install 3.14
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$python = & $uv python find 3.14
Write-Log "compileall $python"
& $python -m compileall -q (Join-Path $project "fusion_runtime") (Join-Path $project "models")
if ($LASTEXITCODE -ne 0) {
    Write-Log "compileall не прошёл" "ERROR"
    exit $LASTEXITCODE
}
Write-Log "compileall PASS"
