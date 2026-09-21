param(
    [ValidateSet('Inventory','Check','Start','Seed','Verify','Login')]
    [string]$Action = 'Inventory',
    [string[]]$Past = @('P01','P06'),
    [switch]$AllPast,
    [string]$Email,
    [switch]$ApprovePast,
    [switch]$WithAI,
    [int]$Port = 8790,
    [int]$VerifyPort = 8792
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $selectedPast = if ($AllPast) { @('all') } else { $Past }
    switch ($Action) {
        'Inventory' { & .\ops\python.ps1 ops/demo.py inventory }
        'Check' { & .\ops\python.ps1 ops/runtime/supabase_live_verify.py }
        'Login' { & npm --prefix server/ai run login }
        'Start' {
            Write-Host "RE:Build Agent: http://127.0.0.1:$Port/ (stop with Ctrl+C)"
            $previousRebuildEnvironment = $env:REBUILD_ENV
            try {
                $env:REBUILD_ENV = 'local'
                & .\ops\python.ps1 -m uvicorn backend.server:app --host 127.0.0.1 --port $Port --no-access-log
            } finally {
                $env:REBUILD_ENV = $previousRebuildEnvironment
            }
        }
        'Seed' {
            $pythonArgs = @('ops/demo.py','seed','--url',"http://127.0.0.1:$Port",'--past') + $selectedPast
            if ($Email) { $pythonArgs += @('--email',$Email) }
            if ($ApprovePast) { $pythonArgs += '--approve-past' }
            & .\ops\python.ps1 @pythonArgs
        }
        'Verify' {
            $pythonArgs = @('ops/demo_live_verify.py','--port',"$VerifyPort",'--past') + $selectedPast
            if ($WithAI) { $pythonArgs += '--with-ai' }
            & .\ops\python.ps1 @pythonArgs
        }
    }
    $demoExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $demoExitCode
