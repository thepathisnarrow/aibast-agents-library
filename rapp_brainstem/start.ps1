# start.ps1 — Windows launcher for RAPP Brainstem
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Refresh PATH so newly-installed tools (gh, python) are found
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

# Ensure UTF-8 output from Python
$env:PYTHONUTF8 = "1"

# Check Python is available
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "ERROR: Python not found on PATH. Install Python 3.10+ from https://python.org" -ForegroundColor Red
    exit 1
}

# Install deps if needed
try {
    python -c "import flask, requests, dotenv" 2>$null
} catch {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt -q
}
# Double-check after install
$depCheck = python -c "import flask, requests, dotenv" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt -q
}

# ── MEA (Managed Environment Admin) Login ─────────────────────────────────────
# The MEA is the tenant-native admin account required for capacity/admin operations.
# Guest users (#EXT#) cannot perform Fabric capacity assignments, so we login as MEA.

function Get-MeaAdmin {
    # Read MEA admin UPN from env.yaml
    $envYaml = Join-Path $PSScriptRoot "env.yaml"
    if (-not (Test-Path $envYaml)) {
        return $null
    }
    $content = Get-Content $envYaml -Raw
    if ($content -match 'mea_admin:\s*"?([^"\r\n]+)"?') {
        return $matches[1].Trim()
    }
    # Fallback: derive from tenant domain
    if ($content -match 'domain:\s*"?([^"\r\n]+)"?') {
        $domain = $matches[1].Trim()
        if ($domain -ne "MngEnvMCAPXXXXXX.onmicrosoft.com") {
            return "admin@$domain"
        }
    }
    return $null
}

function Confirm-MeaLogin {
    param([string]$MeaAdmin)
    
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkCyan
    Write-Host "  MEA (Managed Environment Admin) Authentication" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkCyan
    Write-Host "  Admin operations (Fabric capacity, workspace assignment)" -ForegroundColor Gray
    Write-Host "  require the tenant-native admin account." -ForegroundColor Gray
    Write-Host ""
    Write-Host "  MEA Account: " -NoNewline -ForegroundColor White
    Write-Host $MeaAdmin -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkCyan
    Write-Host ""
    
    # Check if already logged in as MEA
    try {
        $acct = az account show 2>$null | ConvertFrom-Json
        if ($acct.user.name -eq $MeaAdmin) {
            Write-Host "  Already authenticated as MEA." -ForegroundColor Green
            Write-Host ""
            return $true
        }
        Write-Host "  Currently logged in as: $($acct.user.name)" -ForegroundColor DarkYellow
    } catch {
        Write-Host "  No active Azure CLI session." -ForegroundColor DarkYellow
    }
    
    Write-Host ""
    Write-Host "  Login as MEA for admin operations? (Y/n): " -NoNewline -ForegroundColor White
    $response = Read-Host
    if ($response -and $response.ToLower() -ne "y") {
        Write-Host "  Skipping MEA login — admin operations may be limited." -ForegroundColor Yellow
        Write-Host ""
        return $false
    }
    
    # Extract tenant domain for --tenant flag
    $tenant = ($MeaAdmin -split "@")[1]
    
    Write-Host ""
    Write-Host "  Launching Azure CLI login for MEA..." -ForegroundColor Cyan
    Write-Host "  A browser window will open. Sign in as: $MeaAdmin" -ForegroundColor Gray
    Write-Host ""
    
    az login --tenant $tenant --allow-no-subscriptions 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  MEA login failed. Continuing without admin privileges." -ForegroundColor Red
        return $false
    }
    
    # Verify
    $acct = az account show 2>$null | ConvertFrom-Json
    if ($acct.user.name -eq $MeaAdmin) {
        Write-Host "  MEA authenticated successfully." -ForegroundColor Green
        Write-Host ""
        return $true
    } else {
        Write-Host "  Warning: Logged in as $($acct.user.name) (expected $MeaAdmin)" -ForegroundColor Yellow
        return $false
    }
}

$meaAdmin = Get-MeaAdmin
if ($meaAdmin) {
    $meaOk = Confirm-MeaLogin -MeaAdmin $meaAdmin
    if ($meaOk) {
        $env:BRAINSTEM_MEA_AUTHENTICATED = "true"
    }
} else {
    Write-Host "No MEA configured — set mea_admin in env.yaml for admin operations." -ForegroundColor DarkYellow
}

# Check gh CLI (optional — the web login flow works without it)
$gh = Get-Command gh -ErrorAction SilentlyContinue
if ($gh) {
    Write-Host "gh CLI found — token will be auto-detected if you're logged in." -ForegroundColor Green
} else {
    Write-Host "gh CLI not found — you can authenticate via the web UI at http://localhost:7071" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting RAPP Brainstem..." -ForegroundColor Cyan
python brainstem.py
