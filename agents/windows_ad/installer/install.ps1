# NetVault Windows AD Agent Installer
# Version 1.0

Write-Host "--- NetVault Windows AD Agent Installer ---" -ForegroundColor Cyan

# 1. Check Prerequisites
Write-Host "[1/6] Checking prerequisites..."
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Error "Python not found. Please install Python 3.11+ and add it to PATH."
  exit 1
}

$pythonVersion = python --version
Write-Host "Found $pythonVersion"

# 2. Create Virtual Environment
Write-Host "[2/6] Creating virtual environment..."
$serviceDir = Join-Path $PSScriptRoot "..\service"
Set-Location $serviceDir

if (!(Test-Path "venv")) {
  python -m venv --help 2>$null
  if ($LASTEXITCODE -ne 0) { Write-Error "Python venv module not available. Please ensure Python is properly installed."; exit 1 }
  python -m venv venv
  if (!(Test-Path ".\venv\Scripts\python.exe")) { Write-Error "venv creation failed"; exit 1 }
}

# 3. Install Dependencies
Write-Host "[3/6] Installing dependencies..."
& ".\venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\venv\Scripts\pip.exe" install -r requirements.txt

# 4. Configure Agent
Write-Host "[4/6] Configuration..."
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

[System.IO.File]::WriteAllText((Join-Path $serviceDir "config.yml"), $configContent, [System.Text.UTF8Encoding]::new($false))

# 5. Register Service (Optional)
Write-Host "[5/6] Registering Windows service via NSSM..."

$registerService = Read-Host "Would you like to register as a Windows Service? (y/n)"
if ($registerService -eq 'y') {
  # Buscar nssm.exe
  $nssmPath = Join-Path $PSScriptRoot "tools\nssm.exe"
  if (!(Test-Path $nssmPath)) {
    # Intentar descargar
    Write-Host "NSSM not found locally, attempting download..."
    $nssmZip = Join-Path $env:TEMP "nssm-2.24.zip"
    try {
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip
      Expand-Archive $nssmZip -DestinationPath $env:TEMP\nssm -Force
      $nssmPath = "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe"
    }
    catch {
      Write-Error "Could not download NSSM. Please download manually from https://nssm.cc and place nssm.exe in $PSScriptRoot\tools\"
      exit 1
    }
  }

  $serviceName = "NetVaultADAgent"
  $pythonPath = (Resolve-Path "$serviceDir\venv\Scripts\python.exe").Path
  $scriptPath = (Resolve-Path "$serviceDir\ad_agent.py").Path

  # Remove existing service if present
  & "$nssmPath" remove $serviceName confirm 2>$null

  # Install new service
  & "$nssmPath" install $serviceName "$pythonPath" "$scriptPath"
  & "$nssmPath" set $serviceName AppDirectory "$serviceDir"
  & "$nssmPath" set $serviceName DisplayName "NetVault Active Directory Agent"
  & "$nssmPath" set $serviceName Description "Collects AD data and reports to NetVault Server"
  & "$nssmPath" set $serviceName Start SERVICE_AUTO_START
  & "$nssmPath" set $serviceName AppStdout "$serviceDir\agent_stdout.log"
  & "$nssmPath" set $serviceName AppStderr "$serviceDir\agent_stderr.log"
  & "$nssmPath" set $serviceName AppRotateFiles 1
  & "$nssmPath" set $serviceName AppRotateBytes 1048576
    
  Write-Host "[6/6] Starting service..."
  & "$nssmPath" start $serviceName

  Start-Sleep -Seconds 3
  $svc = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
  if ($svc -and $svc.Status -eq 'Running') {
    Write-Host "Service is RUNNING" -ForegroundColor Green
    Write-Host ""
    Write-Host "Installation Complete!" -ForegroundColor Green
    Write-Host "Service Name: $serviceName"
    Write-Host "Logs: $serviceDir\agent_stdout.log"
    Write-Host ""
    Write-Host "Useful commands:"
    Write-Host "  Check status:  Get-Service $serviceName"
    Write-Host "  Stop service:  & '$nssmPath' stop $serviceName"
    Write-Host "  Start service: & '$nssmPath' start $serviceName"
    Write-Host "  Restart:       & '$nssmPath' restart $serviceName"
    Write-Host "  Uninstall:     & '$nssmPath' remove $serviceName confirm"
  }
  else {
    Write-Warning "Service installed but failed to start. Check logs at: $serviceDir\agent_stderr.log"
  }
}
else {
  Write-Host "Agent configured successfully."
  Write-Host "To start the agent manually: & "".\venv\Scripts\python.exe"" ad_agent.py"
  Write-Host "`nInstallation Complete!" -ForegroundColor Green
}
