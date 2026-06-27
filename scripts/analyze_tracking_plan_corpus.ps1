$script = Join-Path (Split-Path -Parent $PSScriptRoot) "skill\scripts\analyze_tracking_plan_corpus.ps1"
& $script @args
