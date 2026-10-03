# orch.ps1 - office orchestrator wrapper (autonomous node): load ~/.bots/env, run orchestrator from target checkout (BOTS_CHECKOUT)
$envfile = Join-Path $env:USERPROFILE ".bots\env"
Get-Content $envfile | ForEach-Object { if ($_ -match '^\s*(\w+)\s*=\s*(.+?)\s*$') { [Environment]::SetEnvironmentVariable($matches[1],$matches[2],"Process") } }
$env:PYTHONPATH = "C:\work\bots-cc"
& python -X utf8 -m orchestrator @args