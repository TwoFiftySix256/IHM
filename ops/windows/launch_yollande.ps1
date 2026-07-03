$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$Pythonw = Join-Path $ProjectRoot "IHM\Scripts\pythonw.exe"
$Python = Join-Path $ProjectRoot "IHM\Scripts\python.exe"

if (Test-Path $Pythonw) {
    $PythonExe = $Pythonw
} elseif (Test-Path $Python) {
    $PythonExe = $Python
} else {
    $PythonExe = "python"
}

if (-not $env:ASSISTANT_REQUIRE_WAKE_WORD) {
    $env:ASSISTANT_REQUIRE_WAKE_WORD = "1"
}
if (-not $env:ASSISTANT_AUTO_LISTEN) {
    $env:ASSISTANT_AUTO_LISTEN = "1"
}
if (-not $env:ASSISTANT_START_MINIMIZED) {
    $env:ASSISTANT_START_MINIMIZED = "1"
}

Start-Process `
    -FilePath $PythonExe `
    -ArgumentList @("run_assistant.py") `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden
