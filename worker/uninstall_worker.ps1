# Desinstalle proprement tout ce qui a ete installe pour CATIAMISTRAL sur ce PC,
# pour repartir sur une base saine. Ne touche ni a CATIA, ni a Windows, ni a Python.
#
# Usage (dans PowerShell, depuis le dossier du projet) :
#   powershell -ExecutionPolicy Bypass -File worker\uninstall_worker.ps1
# Option :
#   -KeepToken : garde la variable GITHUB_TOKEN (utile pour re-installer vite)

param(
    [switch]$KeepToken
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "=== Desinstallation CATIAMISTRAL ===" -ForegroundColor Cyan

# 1. Arreter tout worker en cours d'execution
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -match "catia_worker" } |
    ForEach-Object {
        Write-Host "Arret du worker en cours (PID $($_.ProcessId))..."
        Stop-Process -Id $_.ProcessId -Force
    }

# 2. Supprimer la tache planifiee (demarrage automatique) si elle existe
Get-ScheduledTask |
    Where-Object {
        ($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -match "catia_worker"
    } |
    ForEach-Object {
        Write-Host "Suppression de la tache planifiee '$($_.TaskName)'..."
        Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false
    }

# 3. Supprimer les variables d'environnement du projet
$variables = @(
    "GITHUB_TOKEN",
    "MISTRAL_API_KEY",
    "CATIAMISTRAL_REPO",
    "CATIAMISTRAL_POLL",
    "CATIAMISTRAL_DRY_RUN",
    "CATIAMISTRAL_OUTPUT",
    "CATIAMISTRAL_LICENSES"
)
foreach ($name in $variables) {
    if ($name -eq "GITHUB_TOKEN" -and $KeepToken) {
        Write-Host "Variable conservee (-KeepToken) : $name"
        continue
    }
    [Environment]::SetEnvironmentVariable($name, $null, "User")
    Write-Host "Variable supprimee : $name"
}

# 4. Desinstaller pywin32 (la seule bibliothèque Python du projet)
Write-Host "Desinstallation de pywin32..."
pip uninstall -y pywin32 2>$null

# 5. Supprimer le dossier du projet (avec confirmation)
$project = Read-Host "Chemin du dossier du projet a supprimer (vide = C:\catiamistral-main)"
if (-not $project) { $project = "C:\catiamistral-main" }
if (Test-Path $project) {
    Write-Host ""
    Write-Host "ATTENTION : ce dossier contient output/ (pieces produites), jobs/ (resultats)" -ForegroundColor Yellow
    Write-Host "et data/ (vos donnees clients). Verifiez que ces fichiers sont sauvegardes." -ForegroundColor Yellow
    $confirm = Read-Host "Supprimer definitivement '$project' ? [oui/non]"
    if ($confirm -eq "oui") {
        Remove-Item -Recurse -Force $project
        Write-Host "Dossier supprime." -ForegroundColor Green
    } else {
        Write-Host "Dossier conserve."
    }
} else {
    Write-Host "Dossier '$project' introuvable : rien a supprimer."
}

Write-Host ""
Write-Host "Termine. Ce qui reste volontairement installe :" -ForegroundColor Cyan
Write-Host " - CATIA V5 et sa licence (produit Dassault, non touche)"
Write-Host " - Python lui-meme (desinstallez-le via Parametres > Applications si souhaite)"
Write-Host " - Le depot GitHub en ligne (supprimez-le web : Settings > Danger Zone > Delete this repository)"
Write-Host ""
Write-Host "Pour repartir proprement, reprenez le guide au chapitre 5 (installer le worker)." -ForegroundColor Cyan
