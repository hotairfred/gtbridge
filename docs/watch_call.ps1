# watch_call.ps1 — Monitor CWSL_DIGI output for your callsign
# Handles mode switching (day/night/day_rare/night_rare) and serves
# filtered output on a TCP port for remote monitoring.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File C:\CWSL_DIGI\watch_call.ps1 -Mode night
#   powershell -ExecutionPolicy Bypass -File C:\CWSL_DIGI\watch_call.ps1 -Mode day_rare
#
# Connect from any machine: telnet 192.168.1.230 7777
#
# To switch modes: kill this script (Ctrl+C), rerun with new -Mode

param(
    [string]$Call = "WF8Z",
    [int]$Port = 7777,
    [string]$Mode = "night",
    [string]$DigiDir = "C:\CWSL_DIGI"
)

$DigiExe = Join-Path $DigiDir "CWSL_DIGI.exe"
$ConfigSrc = Join-Path $DigiDir "config_$Mode.ini"
$ConfigDst = Join-Path $DigiDir "config.ini"

# Kill any existing CWSL_DIGI
Write-Host "Stopping any existing CWSL_DIGI..."
Get-Process -Name "CWSL_DIGI" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

# Copy mode config
if (Test-Path $ConfigSrc) {
    Copy-Item $ConfigSrc $ConfigDst -Force
    Write-Host "Loaded config: config_$Mode.ini"
} else {
    Write-Host "WARNING: $ConfigSrc not found, using existing config.ini" -ForegroundColor Yellow
}

# Start TCP listener
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Port)
$listener.Start()
Write-Host "Listening on port $Port for connections..."
Write-Host "Watching CWSL_DIGI output for '$Call'"
Write-Host "Mode: $Mode"
Write-Host ""

$clients = [System.Collections.ArrayList]::new()

# Start CWSL_DIGI with redirected output
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $DigiExe
$psi.WorkingDirectory = $DigiDir
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $false
$proc = [System.Diagnostics.Process]::Start($psi)

Write-Host "CWSL_DIGI started (PID: $($proc.Id))"
Write-Host "-------------------------------------------"

while (-not $proc.HasExited) {
    # Accept new connections (non-blocking)
    if ($listener.Pending()) {
        $client = $listener.AcceptTcpClient()
        $stream = $client.GetStream()
        $writer = New-Object System.IO.StreamWriter($stream)
        $writer.AutoFlush = $true
        $writer.WriteLine("=== CWSL_DIGI Call Monitor ===")
        $writer.WriteLine("Mode: $Mode | Watching for: $Call")
        $writer.WriteLine("==============================")
        $writer.WriteLine("")
        [void]$clients.Add(@{ client = $client; writer = $writer })
        Write-Host "Client connected from $($client.Client.RemoteEndPoint)"
    }

    # Read CWSL_DIGI output
    $line = $proc.StandardOutput.ReadLine()
    if ($null -eq $line) { continue }

    # Always show on local console
    Write-Host $line

    # Check if line contains our callsign
    if ($line -match $Call) {
        # Highlight locally
        Write-Host ">>> MATCH: $line <<<" -ForegroundColor Red -BackgroundColor Yellow

        # Send to all connected clients with ANSI color highlight
        # Red background, white bold text
        $esc = [char]27
        $alert = "${esc}[1;37;41m>>> $line <<<${esc}[0m"
        $deadClients = @()

        for ($i = 0; $i -lt $clients.Count; $i++) {
            try {
                if ($clients[$i].client.Connected) {
                    $clients[$i].writer.WriteLine($alert)
                } else {
                    $deadClients += $i
                }
            } catch {
                $deadClients += $i
            }
        }

        # Clean up disconnected clients
        foreach ($idx in ($deadClients | Sort-Object -Descending)) {
            try { $clients[$idx].client.Close() } catch {}
            $clients.RemoveAt($idx)
        }
    }
}

$listener.Stop()
Write-Host "CWSL_DIGI exited."
