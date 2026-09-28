# VetAI - backend (FastAPI) ve frontend (Vite) sunucularını
# iki ayrı PowerShell penceresinde birlikte başlatır.
#
# Kullanım:  .\start.ps1              veya   npm run dev:all
#            .\start.ps1 -Kontrol     yalnızca ön kontroller (pencere açmaz)

param(
    [switch]$Kontrol
)

$kok = $PSScriptRoot
$sorunVar = $false

Write-Host ""
Write-Host "  VetAI başlatılıyor..." -ForegroundColor Green
Write-Host ""

# --- Portu tutan süreci bulur (yoksa $null) --------------------------------
function Get-PortSahibi {
    param([int]$Port)

    try {
        $baglanti = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
                    Select-Object -First 1
    } catch {
        return $null
    }
    if (-not $baglanti) { return $null }

    $surec = Get-Process -Id $baglanti.OwningProcess -ErrorAction SilentlyContinue
    $ad = "bilinmiyor"
    if ($surec) { $ad = $surec.ProcessName }
    return [pscustomobject]@{ SurecNo = $baglanti.OwningProcess; Ad = $ad }
}

# --- Önkoşul kontrolleri ---------------------------------------------------
if (-not (Test-Path "$kok\backend\.env")) {
    Write-Host "  backend\.env yok - Gemini katmanı devre dışı çalışacak." -ForegroundColor Yellow
    Write-Host "     Düzeltmek için: copy backend\.env.example backend\.env" -ForegroundColor Yellow
    Write-Host ""
}
if (-not (Test-Path "$kok\frontend\node_modules")) {
    Write-Host "  frontend\node_modules yok. Önce: cd frontend; npm install" -ForegroundColor Yellow
    Write-Host ""
    $sorunVar = $true
}
if (-not (Test-Path "$kok\backend\vetai.db")) {
    Write-Host "  Veritabanı yok - sunucu açılışta kendisi oluşturacak (birkaç saniye sürer)." -ForegroundColor DarkGray
    Write-Host ""
}

# --- 8000 portu boş mu? (WinError 10013'ün sebebi) -------------------------
# Windows'ta port başka bir sürecin elindeyken uvicorn "address in use" yerine
# [WinError 10013] "Erişim izinlerince izin verilmeyen bir şekilde bir yuvaya
# erişilmeye çalışıldı" hatası verir; sebebi anlaşılmadığı için burada açıkça
# söylenir. En sık sebep: arka planda unutulmuş eski bir VetAI sunucusu.
$backendPort = 8000
$sahip = Get-PortSahibi -Port $backendPort
if ($sahip) {
    $sorunVar = $true
    Write-Host "  $backendPort portu kullanımda: PID $($sahip.SurecNo) ($($sahip.Ad))." -ForegroundColor Red
    Write-Host "  Backend bu yüzden '[WinError 10013]' verip kapanır." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Zaten çalışan bir VetAI sunucusu olabilir; önce şunu deneyin:" -ForegroundColor Yellow
    Write-Host "     http://127.0.0.1:$backendPort/api/health" -ForegroundColor Yellow
    Write-Host "  Yanıt veriyorsa backend ayakta demektir, yeniden başlatmanıza gerek yok." -ForegroundColor Yellow
    Write-Host "  Eski süreci kapatmak için:" -ForegroundColor Yellow
    Write-Host "     Stop-Process -Id $($sahip.SurecNo)" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "  $backendPort portu boş." -ForegroundColor DarkGray
}

$frontendSahibi = Get-PortSahibi -Port 5173
if ($frontendSahibi) {
    Write-Host "  5173 portu kullanımda (PID $($frontendSahibi.SurecNo)); Vite 5174'e geçecek." -ForegroundColor Yellow
    Write-Host ""
}

if ($Kontrol) {
    Write-Host ""
    if ($sorunVar) {
        Write-Host "  Kontrol bitti: yukarıdaki sorunlar giderilmeli." -ForegroundColor Yellow
    } else {
        Write-Host "  Kontrol bitti: her şey hazır, .\start.ps1 ile başlatabilirsiniz." -ForegroundColor Green
    }
    Write-Host ""
    return
}

if ($sahip) {
    Write-Host "  Backend penceresi açılmadı (port dolu). Frontend başlatılıyor..." -ForegroundColor Yellow
    Write-Host ""
}

# --- Backend (varsa sanal ortamı aktive eder) ------------------------------
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

if (-not $sahip) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backend
    Start-Sleep -Seconds 2
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontend

Write-Host "  Backend  -> http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "  Frontend -> http://localhost:5173  (port doluysa 5174)" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Durdurmak için açılan pencereleri kapatın." -ForegroundColor DarkGray
Write-Host ""
