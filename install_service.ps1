# Installs (or re-installs) the LLM server as a Windows service using NSSM.
#
#   Right-click > Run with PowerShell   (it asks for admin rights itself)
#   or:  powershell -ExecutionPolicy Bypass -File install_service.ps1 [-TestRestart]
#
# What you get: starts at boot (before anyone logs in), restarts 5 seconds after
# any crash or exit, output goes to logs\server.log (rotated at 5 MB).
param(
    [string]$Name = "FunctionsServer",
    [switch]$TestRestart
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- elevate ---------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    $args2 = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Name $Name"
    if ($TestRestart) { $args2 += " -TestRestart" }
    Start-Process powershell -Verb RunAs -ArgumentList $args2 -Wait
    exit
}

New-Item -ItemType Directory -Force "$root\logs" | Out-Null
Start-Transcript -Path "$root\logs\install_service.log" -Force | Out-Null
try {
    $python = Join-Path $root "venv\Scripts\python.exe"
    if (-not (Test-Path $python)) { throw "Missing $python - create the venv first." }
    if (-not (Test-Path (Join-Path $root "server\api_key.py"))) { throw "Missing server\api_key.py" }

    # --- get nssm.exe (stable copy in ProgramData so winget upgrades can't break the service)
    $svcDir = Join-Path $env:ProgramData "FunctionsServer"
    $nssm = Join-Path $svcDir "nssm.exe"
    if (-not (Test-Path $nssm)) {
        $found = (Get-Command nssm -ErrorAction SilentlyContinue).Source
        if (-not $found) {
            Write-Host "Installing NSSM with winget..."
            winget install --id NSSM.NSSM -e --accept-package-agreements --accept-source-agreements | Out-Host
            $found = (Get-Command nssm -ErrorAction SilentlyContinue).Source
            if (-not $found) {
                $found = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages", "$env:ProgramFiles\WinGet\Packages" -Recurse -Filter nssm.exe -ErrorAction SilentlyContinue |
                    Where-Object { $_.FullName -match "win64" } | Select-Object -First 1 -ExpandProperty FullName
            }
        }
        if (-not $found) { throw "Could not find nssm.exe after install." }
        New-Item -ItemType Directory -Force $svcDir | Out-Null
        Copy-Item $found $nssm -Force
    }
    Write-Host "Using $nssm"

    # --- (re)create the service
    if (Get-Service $Name -ErrorAction SilentlyContinue) {
        Write-Host "Removing existing '$Name' service..."
        $hostPid = (Get-CimInstance Win32_Service -Filter "Name='$Name'").ProcessId
        $stopper = Start-Process $nssm -ArgumentList "stop", $Name -PassThru -WindowStyle Hidden
        if (-not $stopper.WaitForExit(30000)) {
            Write-Host "Service did not stop in 30 s; killing its host process."
            $stopper | Stop-Process -Force -ErrorAction SilentlyContinue
            if ($hostPid) { taskkill /F /PID $hostPid | Out-Null }
        }
        & $nssm remove $Name confirm | Out-Null
        Start-Sleep 2
    }
    & $nssm install $Name $python "run_server.py" | Out-Host
    & $nssm set $Name AppDirectory $root | Out-Null            # run_server.py uses relative paths
    & $nssm set $Name DisplayName "Functions LLM Server" | Out-Null
    & $nssm set $Name Description "Firestore tunnel server that answers prompts through OpenAI (OpenRouter as fallback)." | Out-Null
    & $nssm set $Name Start SERVICE_DELAYED_AUTO_START | Out-Null
    & $nssm set $Name AppEnvironmentExtra "PYTHONUNBUFFERED=1" "PYTHONIOENCODING=utf-8" | Out-Null
    & $nssm set $Name AppStdout "$root\logs\server.log" | Out-Null
    & $nssm set $Name AppStderr "$root\logs\server.log" | Out-Null
    & $nssm set $Name AppRotateFiles 1 | Out-Null
    # Rotate only when the service (re)starts. Online rotation routes output through a pipe
    # thread inside nssm.exe, and with it the service host hung after the server exited
    # (no restart, stop stuck in StopPending).
    & $nssm set $Name AppRotateOnline 0 | Out-Null
    & $nssm set $Name AppRotateBytes 5242880 | Out-Null
    & $nssm set $Name AppExit Default Restart | Out-Null      # any exit, even a clean one, restarts it
    & $nssm set $Name AppRestartDelay 5000 | Out-Null
    & $nssm set $Name AppThrottle 5000 | Out-Null
    & $nssm set $Name AppStopMethodConsole 10000 | Out-Null    # Ctrl+C first, so shutdown is clean

    & $nssm start $Name | Out-Host
    Start-Sleep 10
    Get-Service $Name | Format-Table Name, Status, StartType -AutoSize | Out-Host
    Write-Host "--- last log lines"
    Get-Content "$root\logs\server.log" -Tail 8 -ErrorAction SilentlyContinue | Out-Host

    if ($TestRestart) {
        Write-Host "--- restart test: killing the server's python processes"
        $before = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*run_server.py*" } | Select-Object -ExpandProperty ProcessId
        # taskkill (exit code 1) behaves like a real crash. PowerShell's Stop-Process kills with
        # exit code -1, which NSSM treats as "no exit code" and does not restart on.
        $before | ForEach-Object { taskkill /F /PID $_ | Out-Null }
        Start-Sleep 20
        $after = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*run_server.py*" } | Select-Object -ExpandProperty ProcessId
        Write-Host ("old PIDs: {0}   new PIDs: {1}   service: {2}" -f ($before -join ","), ($after -join ","), (Get-Service $Name).Status)
        if ($after -and -not ($after | Where-Object { $before -contains $_ })) { Write-Host "RESTART TEST PASSED" } else { Write-Host "RESTART TEST FAILED" }
    }
    Write-Host "Done. Manage with:  Start-Service / Stop-Service / Restart-Service $Name   (logs: $root\logs\server.log)"
}
catch {
    Write-Host "FAILED: $_" -ForegroundColor Red
}
finally {
    Stop-Transcript | Out-Null
    Start-Sleep 6
}
