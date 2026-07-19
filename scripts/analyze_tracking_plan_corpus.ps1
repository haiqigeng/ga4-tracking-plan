$script = Join-Path (Split-Path -Parent $PSScriptRoot) "maintenance\scripts\analyze_tracking_plan_corpus.ps1"
& $script @args
