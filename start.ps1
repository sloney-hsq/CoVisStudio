param([int]$Port = 8066, [string]$EnvFile)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$studioArgs = @('-m', 'backend', '--port', $Port)
if ($EnvFile) { $studioArgs += @('--env-file', $EnvFile) }
& "$PSScriptRoot\.venv\Scripts\python.exe" @studioArgs
