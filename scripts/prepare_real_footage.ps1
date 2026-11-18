param(
  [string]$Ferry = '',
  [string]$Pilot = ''
)
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
if (-not $Ferry -and -not $Pilot) {
  Write-Host 'Download original MP4s from Pexels, then rerun with -Ferry and/or -Pilot:'
  Write-Host 'Ferry: https://www.pexels.com/video/silhouettes-on-ferry-with-cargo-ship-view-28945771/'
  Write-Host 'Pilot: https://www.pexels.com/video/a-boat-sailing-alongside-a-cargo-ship-7397246/'
  exit 0
}
$argsList = @('host/prepare_real_maritime_clips.py')
if ($Ferry) { $argsList += @('--ferry', $Ferry) }
if ($Pilot) { $argsList += @('--pilot', $Pilot) }
$argsList += @('--out', 'build/real_maritime_clips')
& python @argsList
if ($LASTEXITCODE -ne 0) { throw 'Real maritime footage preparation failed.' }
