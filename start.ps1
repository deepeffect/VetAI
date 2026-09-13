# VetAI - backend (FastAPI) ve frontend (Vite) sunucularini
# iki ayri PowerShell penceresinde birlikte baslatir.
#
# Kullanim:  .\start.ps1       veya       npm run dev:all

$kok = $PSScriptRoot

Write-Host ""
Write-Host "  VetAI baslatiliyor..." -ForegroundColor Green
Write-Host ""

# --- Onkosul kontrolleri --------------------------------------------------
if (-not (Test-Path "$kok\backend\vetai.db")) {
    Write-Host "  Veritabani bulunamadi. Once su komutu calistirin:" -ForegroundColor Yellow
    Write-Host "     cd backend; python init_db.py" -ForegroundColor Yellow
    Write-Host ""
}
if (-not (Test-Path "$kok\backend\.env")) {
    Write-Host "  backend\.env yok - Gemini katmani devre disi calisacak." -ForegroundColor Yellow
    Write-Host "     Duzeltmek icin: copy backend\.env.example backend\.env" -ForegroundColor Yellow
    Write-Host ""
}
if (-not (Test-Path "$kok\frontend\node_modules")) {
    Write-Host "  frontend\node_modules yok. Once: cd frontend; npm install" -ForegroundColor Yellow
    Write-Host ""
}

# --- Backend (varsa sanal ortami aktive eder) ------------------------------
$backend = @"
cd '$kok\backend'
if (Test-Path .venv\Scripts\Activate.ps1) { & .\.venv\Scripts\Activate.ps1 }
Write-Host 'VetAI Backend - http://127.0.0.1:8000/docs' -ForegroundColor Cyan
uvicorn main:app --reload
"@

# --- Frontend --------------------------------------------------------------
$frontend = @"
cd '$kok\frontend'
Write-Host 'VetAI Frontend' -ForegroundColor Cyan
npm run dev
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backend
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontend

Write-Host "  Backend  -> http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "  Frontend -> http://localhost:5173  (port doluysa 5174)" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Durdurmak icin acilan iki pencereyi kapatin." -ForegroundColor DarkGray
Write-Host ""
