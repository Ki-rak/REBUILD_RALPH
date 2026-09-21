param([Parameter(ValueFromRemainingArguments = $true)][string[]]$PythonArgs)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$configuration = [IO.File]::ReadAllText((Join-Path $projectRoot '.venv\pyvenv.cfg'))
$match = [regex]::Match($configuration, '(?m)^home\s*=\s*(.+)\r?$')
if (-not $match.Success) { throw 'Project virtual environment is not configured.' }
$runtime = Join-Path $match.Groups[1].Value.Trim() 'python.exe'
$sitePackages = Join-Path $projectRoot '.venv\Lib\site-packages'
if (-not (Test-Path -LiteralPath $runtime) -or -not (Test-Path -LiteralPath $sitePackages)) {
    throw 'The configured Python runtime or project packages are unavailable.'
}
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $sitePackages
    & $runtime -X utf8 @PythonArgs
    $pythonExitCode = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
exit $pythonExitCode