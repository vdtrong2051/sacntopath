# ScanToPath R8.4 — bộ kiểm thử hợp nhất, không commit/khởi động camera mặc định.
[CmdletBinding()]
param(
    [ValidateSet('Quick','Full','Acceptance')][string]$Profile = 'Quick',
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$EvidenceDir,
    [switch]$RunNativeProbe,
    [switch]$RunBenchmark
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) { throw "R8.4: Python 3.12 venv missing: $py" }
if ($Profile -ne 'Acceptance' -and ($RunNativeProbe -or $RunBenchmark)) {
    throw 'R8.4: Native probes and benchmark require -Profile Acceptance'
}
$runner = Join-Path $root 'scripts\r8_4_verify.py'
if (-not (Test-Path -LiteralPath $runner)) { throw 'R8.4 runner is missing' }
$runnerArgs = @('-X','utf8',$runner,'--project-root',$root,'--profile',$Profile)
if ($EvidenceDir) { $runnerArgs += @('--evidence-dir',$EvidenceDir) }
if ($RunNativeProbe) { $runnerArgs += '--native-probe' }
if ($RunBenchmark) { $runnerArgs += '--benchmark' }
& $py @runnerArgs
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) { throw "R8.4 VERIFY FAILED: profile=$Profile exit=$exitCode" }
if ($Profile -eq 'Acceptance') {
    Write-Warning 'R8.4 Acceptance: automated gates PASS; OVERALL PENDING until physical HMI/native-busy/GPU/present gates are reviewed.'
}
