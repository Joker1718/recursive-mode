[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$Phase,
    [Parameter(Mandatory = $true)][string]$SubagentId,
    [Parameter(Mandatory = $true)][string]$Purpose,
    [string]$ExecutionMode = "review",
    [string]$RepoRoot = (Get-Location).Path,
    [string]$ScaffoldRoot = "",
    [string]$ReviewBundle = "",
    [string]$OutputName = "",
    [switch]$NoAutoUpstream
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $python) {
    Write-Host "[FAIL] Python executable not found in PATH."
    exit 1
}

$scriptPath = Join-Path $PSScriptRoot "recursive-action-record.py"
$argsList = @(
    $scriptPath,
    "--repo-root", $RepoRoot,
    "--run-id", $RunId,
    "--phase", $Phase,
    "--subagent-id", $SubagentId,
    "--purpose", $Purpose,
    "--execution-mode", $ExecutionMode
)
if (-not [string]::IsNullOrWhiteSpace($ScaffoldRoot)) {
    $argsList += @("--scaffold-root", $ScaffoldRoot)
}
if (-not [string]::IsNullOrWhiteSpace($ReviewBundle)) {
    $argsList += @("--review-bundle", $ReviewBundle)
}
if (-not [string]::IsNullOrWhiteSpace($OutputName)) {
    $argsList += @("--output-name", $OutputName)
}
if ($NoAutoUpstream.IsPresent) {
    $argsList += "--no-auto-upstream"
}

& $python @argsList
exit $LASTEXITCODE
