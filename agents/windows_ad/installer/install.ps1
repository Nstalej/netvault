# NetVault Windows AD Agent Installer
# Version 1.0

Write-Host "--- NetVault Windows AD Agent Installer ---" -ForegroundColor Cyan

# 1. Check Prerequisites
Write-Host "[1/5] Checking prerequisites..."
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Please install Python 3.11+ and add it to PATH."
    exit 1
}

$pythonVersion = python --version
Write-Host "Found $pythonVersion"

# 2. Create Virtual Environment
Write-Host "[2/5] Creating virtual environment..."
$serviceDir = Join-Path $PSScriptRoot "..\service"
Set-Location $serviceDir

if (!(Test-Path "venv")) {
    python -m venv venv
}

# 3. Install Dependencies
Write-Host "[3/5] Installing dependencies..."
.\venv\Scripts\python -m pip install --upgrade pip
.\venv\Scripts\pip install -r requirements.txt

# 4. Configure Agent
Write-Host "[4/5] Configuration..."
$serverUrl = Read-Host "Enter NetVault Server URL (e.g., http://192.168.1.10:8000)"
$agentToken = Read-Host "Enter Agent Auth Token"
$adServer = Read-Host "Enter Domain Controller FQDN"
$adUser = Read-Host "Enter AD Query User (e.g., DOMAIN\User)"
$adPass = Read-Host "Enter AD Query Password" -AsSecureString
$baseDn = Read-Host "Enter Base DN (e.g., DC=domain,DC=local)"

# Convert secure string to plain text for config file (simple implementation)
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($adPass)
$plainPass = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)

$configContent = @"
netvault:
  server_url: "$serverUrl"
  agent_token: "$agentToken"
ad:
  server: "$adServer"
  user: "$adUser"
  password: "$plainPass"
  base_dn: "$baseDn"
  use_ssl: true
"@

$configContent | Out-File -FilePath (Join-Path $serviceDir "config.yml") -Encoding utf8

# 5. Register Service (Optional)
Write-Host "[5/5] Finalizing..."
Write-Host "Agent configured successfully."
Write-Host "To start the agent manually: .\venv\Scripts\python ad_agent.py"

$registerService = Read-Host "Would you like to register as a Windows Service? (y/n)"
if ($registerService -eq 'y') {
    Write-Host "Service registration via pywin32 is recommended but requires admin privileges."
    Write-Host "Manual service creation command (example):"
    Write-Host "nssm install NetVaultADAgent (if nssm is available)"
}

Write-Host "`nInstallation Complete!" -ForegroundColor Green
