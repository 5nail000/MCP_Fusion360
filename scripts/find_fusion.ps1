. "$PSScriptRoot\..\tools\logger.ps1"
$root = Join-Path $env:LOCALAPPDATA "Autodesk\webdeploy\production"
if (-not (Test-Path $root)) {
    Write-Log "webdeploy не найден" "ERROR"
    exit 1
}
$exe = Get-ChildItem -Path $root -Filter Fusion360.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $exe) {
    Write-Log "Fusion360.exe не найден" "ERROR"
    exit 1
}
$shown = $exe.FullName.Replace($env:LOCALAPPDATA, "%LOCALAPPDATA%")
Write-Log "Fusion $shown"
$addins = Join-Path $env:APPDATA "Autodesk\Autodesk Fusion 360\API\AddIns"
Write-Log ("AddIns " + $addins.Replace($env:APPDATA, "%APPDATA%"))
$defs = Join-Path $env:APPDATA "Autodesk\Autodesk Fusion 360\API\Python\defs"
Write-Log ("defs " + $defs.Replace($env:APPDATA, "%APPDATA%"))
