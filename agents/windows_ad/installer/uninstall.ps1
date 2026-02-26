# NetVault AD Agent Uninstaller
$serviceName = "NetVaultADAgent"
$nssmPath = Join-Path $PSScriptRoot "tools\nssm.exe"

# Stop service
Write-Host "Stopping service..."
& "$nssmPath" stop $serviceName 2>$null
Start-Sleep -Seconds 2

# Remove service
Write-Host "Removing service..."
& "$nssmPath" remove $serviceName confirm

Write-Host "Service removed. Agent files remain in the service directory."
Write-Host "To fully remove, delete the agent folder manually."
