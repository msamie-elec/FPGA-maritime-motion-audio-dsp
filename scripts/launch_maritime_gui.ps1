<# Launch the standalone interactive Windows GUI. Run in the project root:
   powershell -ExecutionPolicy Bypass -File .\scripts\launch_maritime_gui.ps1
   If PIL / pyserial not found: python -m pip install -r host/requirements.txt
#>
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
& python -c "import tkinter, cv2, PIL, matplotlib, serial, numpy; print('GUI dependencies ready')"
if ($LASTEXITCODE -ne 0) { throw 'Install Python dependencies: python -m pip install -r host/requirements.txt' }
& python host/maritime_gui.py
if ($LASTEXITCODE -ne 0) { throw 'Maritime GUI exited with an error' }
