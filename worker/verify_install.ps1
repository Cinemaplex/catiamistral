# CATIAMISTRAL : verification automatique de l'installation sur le poste.
# Ce script teste chaque composant et, en cas d'anomalie, affiche quoi faire
# (renvoi au chapitre exact du guide).
#
# Usage (dans PowerShell, depuis le dossier du projet) :
#   powershell -ExecutionPolicy Bypass -File worker\verify_install.ps1

$ErrorActionPreference = "SilentlyContinue"

$script:alertes = 0
$script:verifs = 0

function Check {
    param($Titre, $Ok, $Conseil)
    $script:verifs = $script:verifs + 1
    if ($Ok) {
        Write-Host "[OK    ] $Titre" -ForegroundColor Green
    } else {
        $script:alertes = $script:alertes + 1
        Write-Host "[ALERTE] $Titre" -ForegroundColor Yellow
        if ($Conseil) {
            Write-Host "         -> A faire : $Conseil" -ForegroundColor White
        }
    }
}

Write-Host ""
Write-Host "=== CATIAMISTRAL : verification de l'installation ===" -ForegroundColor Cyan
Write-Host ""

# 1. Python
$pyVersion = & python --version 2>&1
Check "Python installe : $pyVersion" ($pyVersion -match "^Python 3\.") `
    "installer Python depuis https://www.python.org/downloads puis relancer ce script (guide, chapitre 5, Etape A)."

# 2. pywin32
$pywin = & python -c "import win32com.client; print('ok')" 2>&1
Check "Bibliotheque pywin32 (pilotage CATIA)" ($pywin -match "ok") `
    "dans PowerShell : pip install pywin32"

# 3. Token GitHub defini
Check "Variable GITHUB_TOKEN definie" (-not [string]::IsNullOrEmpty($env:GITHUB_TOKEN)) `
    "la definir : setx GITHUB_TOKEN <votre-token> (guide, chapitre 4, Etape 2), puis fermer et rouvrir PowerShell."

# 4. Token GitHub valide
$tokenOk = $true
if ([string]::IsNullOrEmpty($env:GITHUB_TOKEN)) {
    $tokenOk = $false
} else {
    try {
        $headers = @{ Authorization = "Bearer " + $env:GITHUB_TOKEN }
        Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $headers -TimeoutSec 15 | Out-Null
    } catch { $tokenOk = $false }
}
Check "Token GitHub accepte par api.github.com" $tokenOk `
    "token invalide ou expire : recreez-en un (https://github.com/settings/personal-access-tokens/new) et refaites setx GITHUB_TOKEN <nouveau>. Pensez aussi au secret Mistral (guide, chapitre 4, Etapes 2-3)."

# 5. Depot accessible
$repo = $env:CATIAMISTRAL_REPO
if (-not $repo) { $repo = "Cinemaplex/catiamistral" }
$repoOk = $false
try {
    $ghRepo = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo" -Headers $headers -TimeoutSec 15
    $repoOk = $true
} catch { }
Check "Depot accessible : github.com/$repo" $repoOk `
    "depot introuvable avec ce token : verifiez que le token a acces au depot (Fine-grained: Repository access) et que CATIAMISTRAL_REPO est correct."

# 6. Dossier jobs/pending (boite aux lettres)
$jobsOk = $false
try {
    Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/contents/jobs/pending" -Headers $headers -TimeoutSec 15 | Out-Null
    $jobsOk = $true
} catch { }
Check "Dossier jobs/pending present (boite aux lettres)" $jobsOk `
    "ce n'est bloquant que si vous deposez les jobs a la main : l'agent cree le dossier au 1er job. Sinon : sur GitHub, Add file -> saisir jobs/pending/.keep -> Commit."

# 7. CATIA installe sur ce poste (COM)
$catiaexo = Test-Path "HKLM:\SOFTWARE\Classes\CATIA.Application"
Check "CATIA V5 detecte sur ce poste (interface COM)" $catiaexo `
    "CATIA.Application introuvable : verifiez que CATIA V5 est installe ET licence sur CE PC, et que vous executez le worker sur ce poste (pas via une session distante franche)."

# 8. Licences declarees
$lic = $env:CATIAMISTRAL_LICENSES
if (-not $lic) { $lic = "MD2,GSD,ST1 (defaut)" }
Write-Host "[INFO  ] Licences declarees : $lic (variable CATIAMISTRAL_LICENSES si a modifier)"
$script:verifs = $script:verifs + 1

# 9. Dossier reseau (optionnel)
if ($env:CATIAMISTRAL_DATA_DIR) {
    Check "Dossier reseau accessible : $($env:CATIAMISTRAL_DATA_DIR)" (Test-Path $env:CATIAMISTRAL_DATA_DIR) `
        "partage reseau injoignable : soit retablir l'acces, soit le desactiver (powershell -Command [Environment]::SetEnvironmentVariable('CATIAMISTRAL_DATA_DIR',$null,'User')) ; sinon le worker retombera sur GitHub."
} else {
    Write-Host "[INFO  ] Dossier reseau non configure : fichiers CAO pris sur GitHub (data/)"
    $script:verifs = $script:verifs + 1
}

# 10. Dossier output inscriptible
$outOk = $false
try {
    New-Item -ItemType Directory -Path ".\output" -Force | Out-Null
    $probe = ".\output\$([guid]::NewGuid().ToString()).tmp"
    Set-Content -Path $probe -Value "test" -ErrorAction Stop
    Remove-Item $probe -Force
    $outOk = $true
} catch { }
Check "Dossier output (output du projet) inscriptible" $outOk `
    "dossier en lecture seule : verifiez les droits Windows sur le dossier du projet, ou lancez PowerShell en tant qu'administrateur une fois pour corriger les droits."

# 11. Worker deja en cours ?
$running = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -match "catia_worker" }
if ($running) {
    Write-Host "[INFO  ] Worker deja en cours d'execution (PID $($running.ProcessId)) : ne pas demarrer un deuxieme."
} else {
    Write-Host "[INFO  ] Worker non lance actuellement : python worker\catia_worker.py (guide, chapitre 5, Etape E)"
}
$script:verifs = $script:verifs + 1

Write-Host ""
if ($script:alertes -eq 0) {
    Write-Host "=== RESULTAT : TOUT EST EN REGLE ($script:verifs verifications) ===" -ForegroundColor Green
    Write-Host "Vous pouvez lancer le worker : python worker\catia_worker.py" -ForegroundColor Green
} else {
    Write-Host "=== RESULTAT : $script:alertes anomalie(s) sur $script:verifs verifications ===" -ForegroundColor Yellow
    Write-Host "Suivez les '-> A faire' ci-dessus, puis relancez ce script jusqu'au vert." -ForegroundColor Yellow
    Write-Host "Aide complete : guide PDF, chapitre 9 (Depannage express)." -ForegroundColor Yellow
}
Write-Host ""
