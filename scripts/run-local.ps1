[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AgentArgs
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$srHome = if ($env:SR_HOME) { $env:SR_HOME } else { Join-Path $env:LOCALAPPDATA 'sr' }
$runtimeRoot = Join-Path $srHome 'sr-agent'
$venvRoot = Join-Path $runtimeRoot 'venv'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
$managedUv = Join-Path $srHome 'bin\uv.exe'

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null

if (-not (Test-Path $managedUv)) {
    $installer = Join-Path $repoRoot 'scripts\install.ps1'
    & $installer -Stage uv -SRHome $srHome -InstallDir $runtimeRoot -NonInteractive
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $managedUv)) {
        throw "SR could not install uv at $managedUv."
    }
}

if (-not (Test-Path $venvPython)) {
    & $managedUv venv $venvRoot --python 3.11
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
        throw "SR could not create the managed Python environment at $venvRoot."
    }
}

$previousProjectEnvironment = $env:UV_PROJECT_ENVIRONMENT
$env:UV_PROJECT_ENVIRONMENT = $venvRoot
try {
    & $managedUv sync --project $repoRoot --extra all --extra dev --locked
    if ($LASTEXITCODE -ne 0) {
        throw "SR dependency synchronization failed for $repoRoot."
    }
} finally {
    $env:UV_PROJECT_ENVIRONMENT = $previousProjectEnvironment
}

# Migrate environments created by older checkout instructions. Do this only
# after the shared environment is healthy, so a failed setup never destroys the
# user's only working environment.
foreach ($legacyVenv in @((Join-Path $repoRoot '.venv'), (Join-Path $repoRoot 'venv'))) {
    if ((Test-Path $legacyVenv) -and ([IO.Path]::GetFullPath($legacyVenv) -ne [IO.Path]::GetFullPath($venvRoot))) {
        try {
            Remove-Item -Recurse -Force $legacyVenv
        } catch {
            Write-Warning "Could not remove legacy environment at $legacyVenv; the shared environment is still usable."
        }
    }
}

$env:PYTHONPATH = if ($env:PYTHONPATH) { "$repoRoot;$env:PYTHONPATH" } else { $repoRoot }
& $venvPython -m sr_cli.main @AgentArgs
exit $LASTEXITCODE
