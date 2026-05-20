param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

if (-not $SkipInstall) {
    py -m pip install -r requirements.txt
    py -m pip install -r requirements-build.txt
}

py -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name AIAgentChatSpellAssistant `
    --collect-data symspellpy `
    spell_overlay.py

Write-Host "Built dist\AIAgentChatSpellAssistant.exe"
