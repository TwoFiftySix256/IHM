$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LaunchScript = (Resolve-Path (Join-Path $ScriptDir "launch_yollande.ps1")).Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Yollande.lnk"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$LaunchScript`""
$Shortcut.WorkingDirectory = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$Shortcut.IconLocation = "$env:SystemRoot\System32\SHELL32.dll,220"
$Shortcut.Description = "Lancer Yollande"
$Shortcut.Save()

Write-Host "Raccourci cree : $ShortcutPath"
