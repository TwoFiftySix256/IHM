# Deploiement bureau de Yollande

## Windows

Depuis PowerShell, dans `C:\Users\hp\IHM-bot` :

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\create_desktop_shortcut.ps1
powershell -ExecutionPolicy Bypass -File .\ops\windows\install_startup_task.ps1
```

Le raccourci `Yollande.lnk` lance l'assistant sans terminal. La tache planifiee
`YollandeAssistant` lance Yollande automatiquement a l'ouverture de session.

Pour retirer le lancement automatique :

```powershell
powershell -ExecutionPolicy Bypass -File .\ops\windows\uninstall_startup_task.ps1
```

## Linux systemd utilisateur

Copiez le projet dans `/opt/yollande`, adaptez `WorkingDirectory` et `ExecStart`
dans `ops/linux/yollande.service`, puis installez :

```bash
mkdir -p ~/.config/systemd/user
cp ops/linux/yollande.service ~/.config/systemd/user/yollande.service
systemctl --user daemon-reload
systemctl --user enable --now yollande.service
```

## macOS Launchd

Copiez le projet dans `/Applications/Yollande`, adaptez le chemin si besoin,
puis installez :

```bash
cp ops/macos/com.hermes.yollande.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hermes.yollande.plist
```
