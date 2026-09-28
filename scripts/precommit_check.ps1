. "$PSScriptRoot\..\tools\logger.ps1"
$project = Split-Path $PSScriptRoot -Parent
Set-Location $project
$name = Split-Path $env:USERPROFILE -Leaf
$files = git ls-files
if (-not $files) {
    $files = Get-ChildItem -Recurse -File | Where-Object {
        $_.FullName -notmatch '\\(\.git|\.venv|\.runtime|logs)\\'
    } | ForEach-Object { $_.FullName.Substring($project.Length + 1) }
}
$failed = $false
foreach ($relative in $files) {
    if ($relative -match '^(exports|renders|\.runtime|logs)\\') { continue }
    $path = Join-Path $project $relative
    if (-not (Test-Path $path)) { continue }
    $text = Get-Content -Raw -ErrorAction SilentlyContinue -Path $path
    if (-not $text) { continue }
    $tokenPrefix = 'gh' + 'o_'
    $userRoot = 'C:' + '\Users\'
    if ($text.Contains($name) -or $text.Contains($tokenPrefix) -or $text -match '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b') {
        Write-Log "секрет или путь пользователя в $relative" "ERROR"
        $failed = $true
    }
    if ($text.Contains($userRoot)) {
        Write-Log "абсолютный путь пользователя в $relative" "ERROR"
        $failed = $true
    }
}
if ($failed) { exit 1 }
Write-Log "precommit_check PASS"
