# Launch (or focus) PC-DECK 7710. If the server is already up, just opens the
# browser; otherwise starts the Python server in its own window first.
$ErrorActionPreference = 'SilentlyContinue'
$up = $false
try {
  Invoke-WebRequest 'http://127.0.0.1:7710/' -UseBasicParsing -TimeoutSec 1 | Out-Null
  $up = $true
} catch {}
if (-not $up) {
  Start-Process -FilePath 'C:\Python310\python.exe' -ArgumentList 'server.py' -WorkingDirectory 'C:\AI\Pioneer'
  Start-Sleep -Milliseconds 800
}
Start-Process 'http://127.0.0.1:7710/'
