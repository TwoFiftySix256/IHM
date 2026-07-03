$ErrorActionPreference = "Stop"

$TaskName = "YollandeAssistant"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Tache de demarrage supprimee : $TaskName"
} else {
    Write-Host "Aucune tache de demarrage Yollande n'etait installee."
}
