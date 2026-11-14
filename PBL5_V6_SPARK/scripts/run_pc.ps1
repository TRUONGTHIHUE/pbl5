param([string]$Port = "COM4", [switch]$WifiOnly)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Create .venv and install requirements first. See README.md." }
$Arguments = @((Join-Path $Root "pc\app.py"), "--port", $Port)
if ($WifiOnly) { $Arguments += "--wifi-only" }
& $Python @Arguments
exit $LASTEXITCODE
