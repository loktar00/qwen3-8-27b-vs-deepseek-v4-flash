# Watchdog for the Qwen-medium reasoning_effort proxy (opencode_medium_proxy.py, :8004 -> :8001).
# Started detached (Start-Process -WindowStyle Hidden). Loops forever: if port 8004 is NOT
# listening, starts the proxy; then sleeps. If the proxy is already up (started by someone else,
# e.g. the calibrator), this script does nothing but keep watching -- it never kills or restarts
# a healthy process, only fills in if the port goes quiet.
#
# Log: D:\dev\style-pilot\labs\qwen38-day0\ab\proxy_8004_supervisor.log

$ErrorActionPreference = "SilentlyContinue"
$scriptDir = "D:\dev\style-pilot\labs\qwen38-day0\ab"
$logFile = Join-Path $scriptDir "proxy_8004_supervisor.log"
$proxyScript = Join-Path $scriptDir "opencode_medium_proxy.py"

function Log($msg) {
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    Add-Content -Path $logFile -Value "$ts $msg"
}

Log "supervisor started (pid $PID)"

while ($true) {
    $listening = Get-NetTCPConnection -LocalPort 8004 -State Listen -ErrorAction SilentlyContinue
    if (-not $listening) {
        Log "port 8004 not listening -- starting proxy"
        Start-Process -FilePath "python" -ArgumentList "`"$proxyScript`"" -WindowStyle Hidden -WorkingDirectory $scriptDir
        Start-Sleep -Seconds 3
        $check = Get-NetTCPConnection -LocalPort 8004 -State Listen -ErrorAction SilentlyContinue
        if ($check) {
            Log "proxy started ok, pid(s): $($check.OwningProcess -join ',')"
        } else {
            Log "proxy start attempted but port still not listening -- will retry"
        }
    }
    Start-Sleep -Seconds 15
}
