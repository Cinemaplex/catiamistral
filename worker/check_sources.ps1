# CATIAMISTRAL : indique d'ou viennent le code et les donnees (web GitHub ou
# reseau local), et teste les deux chemins. Script de diagnostic pour debutants.
#
# Usage (dans PowerShell, depuis le dossier du projet) :
#   powershell -ExecutionPolicy Bypass -File worker\check_sources.ps1

$ErrorActionPreference = "SilentlyContinue"

$repo = $env:CATIAMISTRAL_REPO
if (-not $repo) { $repo = "Cinemaplex/catiamistral" }
$dataDir = $env:CATIAMISTRAL_DATA_DIR
$output = $env:CATIAMISTRAL_OUTPUT
if (-not $output) { $output = ".\output (dossier du projet)" }

Write-Host ""
Write-Host "=== CATIAMISTRAL : origine du code et des donnees ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. CODE DU PROJET + FILE D'ATTENTE (jobs) : toujours GitHub" -ForegroundColor White
Write-Host "   Depot : github.com/$repo"
try {
    Invoke-WebRequest -Uri "https://api.github.com" -UseBasicParsing -TimeoutSec 10 | Out-Null
    Write-Host "   Acces GitHub : OK (connexion sortante https, aucune porte ouverte)" -ForegroundColor Green
} catch {
    Write-Host "   Acces GitHub : ECHEC ($($_.Exception.Message))" -ForegroundColor Yellow
}
if ($env:GITHUB_TOKEN) {
    Write-Host "   Token GITHUB_TOKEN : defini" -ForegroundColor Green
} else {
    Write-Host "   Token GITHUB_TOKEN : ABSENT (le worker ne peut pas fonctionner)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "2. FICHIERS CAO DU RELEVE (avant-projet) : reseau d'abord si configure" -ForegroundColor White
if ($dataDir) {
    Write-Host "   Dossier reseau configure : $dataDir"
    if (Test-Path $dataDir) {
        Write-Host "   Chemin reseau : OK (accessible depuis ce PC)" -ForegroundColor Green
    } else {
        Write-Host "   Chemin reseau : INTROUVABLE (le worker reviendra automatiquement sur GitHub)" -ForegroundColor Yellow
    }
} else {
    Write-Host "   Dossier reseau : non configure (tout vient de GitHub, dossier data/)"
    Write-Host "   Pour activer : setx CATIAMISTRAL_DATA_DIR \\serveur\donnees"
}

Write-Host ""
Write-Host "3. PIECES PRODUITES (output) : $output" -ForegroundColor White
Write-Host "   (un chemin reseau UNC est accepte, ex \\serveur\sortie)"

Write-Host ""
Write-Host "Regle appliquee par le worker : reseau local si configure et present, sinon" -ForegroundColor White
Write-Host "GitHub. Aucune action de votre part : l'origine de chaque fichier est tracee" -ForegroundColor White
Write-Host "dans result.json (champ 'origin') et affichee par l'agent dans ses comptes rendus." -ForegroundColor White
Write-Host ""
