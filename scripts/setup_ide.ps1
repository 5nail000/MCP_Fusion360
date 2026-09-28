. "$PSScriptRoot\..\tools\logger.ps1"
$defs = Join-Path $env:APPDATA "Autodesk\Autodesk Fusion 360\API\Python\defs"
$vscode = Join-Path (Split-Path $PSScriptRoot -Parent) ".vscode"
New-Item -ItemType Directory -Force -Path $vscode | Out-Null
$settings = @{
    "python.analysis.extraPaths" = @($defs)
    "python.defaultInterpreterPath" = (Join-Path (Split-Path $PSScriptRoot -Parent) ".venv\Scripts\python.exe")
}
$dest = Join-Path $vscode "settings.json"
$settings | ConvertTo-Json | Set-Content -Path $dest -Encoding utf8
Write-Log "записал локальный .vscode/settings.json (в git не входит)"
