$ErrorActionPreference = "Stop"

$TaskName = "YollandeAssistant"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LaunchScript = (Resolve-Path (Join-Path $ScriptDir "launch_yollande.ps1")).Path

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$LaunchScript`""

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Lance Yollande automatiquement a l'ouverture de session." `
    -Force | Out-Null

Write-Host "Tache de demarrage installee : $TaskName"
