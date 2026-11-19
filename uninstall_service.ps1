# Stops and removes the LLM server Windows service (asks for admin rights itself).
param([string]$Name = "FunctionsServer")
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Name $Name" -Wait
    exit
}
$nssm = Join-Path $env:ProgramData "FunctionsServer\nssm.exe"
if (Get-Service $Name -ErrorAction SilentlyContinue) {
    & $nssm stop $Name
    & $nssm remove $Name confirm
} else {
    Write-Host "Service '$Name' is not installed."
}
Start-Sleep 4
