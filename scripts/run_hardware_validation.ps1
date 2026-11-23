<#
Integrated FPGA hardware verification, to run AFTER programming the local bitstream.
This script is an add-on for the unchanged Full Integrated v0.2 source tree.
Example from project root:
  powershell -ExecutionPolicy Bypass -File .\scripts\run_hardware_validation.ps1 -Port COM6
#>
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^(?i:COM\d+)$')][string]$Port,
    [switch]$SkipVideo
)
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
$root = (Get-Location).Path
$bitstream = Join-Path $root 'hardware\build\maritime_a7.runs\impl_1\arty_a7_maritime_top.bit'
if (-not (Test-Path $bitstream)) { throw "Bitstream not found: $bitstream. Run the integrated Vivado build first." }
foreach ($p in @('host\hardware_smoke.py','host\stabilize_video.py','host\requirements.txt')) {
    if (-not (Test-Path $p)) { throw "Required project file missing: $p" }
}
$evidence = Join-Path $root 'evidence\hardware'
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$transcript = Join-Path $evidence "validation_${stamp}.txt"
$started = $false
$allPassed = $false
try {
    Start-Transcript -Path $transcript | Out-Null
    $started = $true
    Write-Host "PHYSICAL FPGA TEST - PORT $Port"
    Write-Host "Source folder: $root"
    Write-Host "Bitstream exists: $bitstream"
    Write-Host "Programming is a manual prerequisite; this script does NOT program the FPGA."
    & python -c "import serial, cv2, numpy; print('Python serial/OpenCV/NumPy dependencies found')"
    if ($LASTEXITCODE -ne 0) { throw 'Install dependencies: python -m pip install -r host/requirements.txt' }

    Write-Host '[1/2] PHYSICAL UART + FIR numerical verification: impulse, negative DC and mixed-sign samples'
    & python host/hardware_smoke.py --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Hardware smoke FAILED. No hardware success claim is permitted.' }

    if (-not $SkipVideo) {
        Write-Host '[2/2] Physical FPGA-returned motion trajectory verification + before/after video'
        $out = Join-Path $root 'build\maritime_hardware'
        & python host/stabilize_video.py --out $out --port $Port
        if ($LASTEXITCODE -ne 0) { throw 'FPGA video comparison FAILED. Preserve logs and inspect failure.' }
        $metricsFile = Join-Path $out 'metrics.json'
        if (-not (Test-Path $metricsFile)) { throw 'Physical metrics.json not created' }
        $m = Get-Content $metricsFile -Raw | ConvertFrom-Json
        if ($m.mode -ne 'PHYSICAL FPGA - BIT-EXACT VERIFIED') { throw "Unexpected measurement mode: $($m.mode)" }
        if (-not $m.pass_target_30pct) { throw 'Numerical filtering verified, but >=30% shake-reduction target NOT MET' }
        Copy-Item $metricsFile (Join-Path $evidence "metrics_${stamp}.json") -Force
        Write-Host 'PHYSICAL_FPGA_VIDEO_PASS - bit-exact X/Y trajectory checks and shake metric pass'
    } else {
        Write-Host '[2/2] Video intentionally skipped; motion-video release remains UNVERIFIED'
    }
    $reports = Join-Path $root 'hardware\build\reports'
    if (Test-Path $reports) {
        $reportDest = Join-Path $evidence "vivado_reports_${stamp}"
        New-Item -ItemType Directory -Force -Path $reportDest | Out-Null
        Get-ChildItem $reports -Filter '*.rpt' | Copy-Item -Destination $reportDest
        Write-Host "Preserved routed Vivado reports at: $reportDest"
    }
    $allPassed = $true
    Write-Host 'PHYSICAL_FPGA_VALIDATION_PASS - check transcript and retained reports'
}
finally {
    if ($started) { Stop-Transcript | Out-Null }
    Write-Host "Evidence transcript: $transcript"
}
if (-not $allPassed) { throw 'Physical FPGA validation did not complete successfully.' }
