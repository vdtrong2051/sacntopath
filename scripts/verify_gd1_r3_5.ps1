# R3.5 automated gate. No commit, push, migration, RAW writes or HMI self-approval.
[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [switch]$FullRegression,
    [string]$EvidenceDir
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
Set-Location -LiteralPath $root
if ((git branch --show-current).Trim() -ne 'feat/gd1-desktop-ui') {
    throw 'R3.5 gate: wrong branch (expected feat/gd1-desktop-ui).'
}
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "R3.5 gate: no local Windows Python: $python"
}
if (-not $EvidenceDir) {
    $EvidenceDir = Join-Path (Split-Path -Parent $root) '_setup\ScanToPath_GD1_R3_05_Acceptance'
}
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$evidence = (Resolve-Path -LiteralPath $EvidenceDir).Path
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONUTF8 = '1'

$focused = @(
    'tests/ui/project/test_gd1_r3_1_recent_store.py',
    'tests/ui/project/test_gd1_r3_2_project_dashboard.py',
    'tests/ui/project/test_gd1_r3_2_1_header_density.py',
    'tests/ui/project/test_gd1_r3_3_contextual_inspector.py',
    'tests/ui/project/test_gd1_r3_4_processing_workspace.py',
    'tests/ui/project/test_gd1_r3_5_integrated_ux.py',
    'tests/ui/project/test_gd1_07_8_qt.py',
    'tests/contracts/kien_truc/test_gd1_07_12_architecture.py',
    'tests/ui/project/test_gd1_07_12_qt.py'
)

& $python -X utf8 -c 'import PySide6; import pytest'
if ($LASTEXITCODE -ne 0) { throw 'R3.5 gate requires installed PySide6 and pytest; skips are not proof of PASS.' }
Write-Host 'R3.5: focused Qt + architecture integration gate' 
& $python -X utf8 -m pytest -q @focused "--junitxml=$evidence\r3_5_focused.xml"
if ($LASTEXITCODE -ne 0) { throw "R3.5 focused gate FAILED (exit $LASTEXITCODE)" }
[xml]$report = Get-Content -LiteralPath (Join-Path $evidence 'r3_5_focused.xml') -Raw
$cases = @($report.SelectNodes("//testcase[starts-with(@name, 'test_r35_')]"))
if ($cases.Count -ne 5) { throw "R3.5 gate: expected 5 integrated tests, got $($cases.Count)" }
foreach ($case in $cases) {
    if ($null -ne $case.SelectSingleNode('skipped')) {
        throw "R3.5 gate: mandatory case skipped: $($case.name)"
    }
}

if ($FullRegression) {
    Write-Host 'R3.5: full Python regression'
    & $python -X utf8 -m pytest -q tests "--junitxml=$evidence\r3_5_full.xml"
    if ($LASTEXITCODE -ne 0) { throw "R3.5 full regression FAILED (exit $LASTEXITCODE)" }
}

Write-Host "R3.5 automated tests completed; evidence: $evidence"
Write-Warning 'Automated results do NOT constitute Windows visual/HMI PASS. Complete R3_05 checklist separately.'
