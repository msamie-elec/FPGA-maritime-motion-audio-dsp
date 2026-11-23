# Copy ORIGINAL local machine-readable reliability and build summaries into this release.
# Example: powershell -ExecutionPolicy Bypass -File .\scripts\import_local_validation_evidence.ps1 -PreviousProjectRoot 'C:\...\FPGA_Maritime_AV_7'
param([Parameter(Mandatory=$true)][string]$PreviousProjectRoot)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$src=Join-Path $PreviousProjectRoot 'evidence\final_validation'
$dest=Join-Path $root 'evidence\final_validation'
if (!(Test-Path $src -PathType Container)) { throw "No existing evidence dir: $src" }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$count=0
Get-ChildItem $src -Directory | Where-Object {$_.Name -match '^(cold_|reset_|soak_|build_)'} | ForEach-Object {
    $target=Join-Path $dest $_.Name
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    # retain all primary raw CSV, JSON and evidence notes; skip huge bitstreams or archives
    Get-ChildItem $_.FullName -File -ErrorAction SilentlyContinue | Where-Object {$_.Extension -in '.csv','.json','.md','.txt'} | ForEach-Object {
        $out=Join-Path $target $_.Name
        if (Test-Path $out) {
            $old=(Get-FileHash -Algorithm SHA256 $_.FullName).Hash
            $new=(Get-FileHash -Algorithm SHA256 $out).Hash
            if ($old -ne $new) {throw "Different evidence content already exists: $out"}
        } else { Copy-Item $_.FullName $out; $script:count++ }
    }
}
Write-Host "RAW_EVIDENCE_IMPORTED files=$count from=$src"
Write-Host 'Now re-open GUI -> Summary Report -> Refresh evidence.'
