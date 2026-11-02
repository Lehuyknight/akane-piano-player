# Build Admin-required Windows launcher .exe
# Usage (from repo root, venv active):
#   powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$py = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  $py = "python"
}

& $py -m pip install -q pyinstaller customtkinter requests mido pynput

& $py -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name "AkanePianoLauncher" `
  --uac-admin `
  --collect-all customtkinter `
  --hidden-import "pynput.keyboard._win32" `
  --hidden-import "pynput._util.win32" `
  launcher.py

Write-Host ""
Write-Host "Xong. Chạy: .\dist\AkanePianoLauncher\AkanePianoLauncher.exe"
Write-Host "(UAC Admin bắt buộc nhờ --uac-admin)"
