#requires -Version 5
# ============================================================
# CI/CD Intelligence Layer - unified launcher
# Starts: Neuro-SAN server (8080), Gateway API (8000), React/Vite dashboard (5173).
# Loads .env and passes it to all child processes. Ctrl+C stops everything.
# ============================================================
$ErrorActionPreference = "Stop"
$ScriptDir   = $PSScriptRoot
$Workspace   = Split-Path $ScriptDir -Parent
$NeuroStudio = Join-Path $Workspace "neuro-san-studio"
$DashDir     = Join-Path $ScriptDir "dashboard-web"

# --- Load .env into this process (children inherit) ---
$envFile = Join-Path $ScriptDir ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            $k = $line.Substring(0, $idx).Trim()
            $v = $line.Substring($idx + 1).Trim()
            [Environment]::SetEnvironmentVariable($k, $v, "Process")
        }
    }
    Write-Host "[env] Loaded .env"
} else {
    Write-Warning "[env] .env not found at $envFile - using defaults."
}

# --- Neuro-SAN agent discovery env ---
$env:AGENT_MANIFEST_FILE = Join-Path $ScriptDir "registries\manifest.hocon"
# AGENT_TOOL_PATH must be the RELATIVE package name "coded_tools" (no separators):
# neuro-san then imports tools as coded_tools.<network>.<tool>. Giving an absolute
# path triggers a PYTHONPATH-prefix resolver that collapses the module to just
# "coded_tools" and fails. Package root goes on PYTHONPATH (prepended, so OUR
# coded_tools wins over neuro-san-studio's).
$env:AGENT_TOOL_PATH = "coded_tools"
# Neuro-SAN runs with CWD = our package root (so `import coded_tools` = OURS, not
# neuro-san-studio's). Studio stays importable via PYTHONPATH so `-m neuro_san_studio` works.
$sep = [IO.Path]::PathSeparator
$existingPP = [Environment]::GetEnvironmentVariable("PYTHONPATH", "Process")
$env:PYTHONPATH = "$ScriptDir$sep$NeuroStudio" + $(if ($existingPP) { "$sep$existingPP" } else { "" })

# --- Locate Python (prefer workspace venv) ---
$py = Join-Path $Workspace ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = Join-Path $NeuroStudio "venv\Scripts\python.exe" }
if (-not (Test-Path $py)) { $py = "python" }
Write-Host "[python] $py"

if (-not $env:NVIDIA_API_KEY) {
    Write-Warning "[llm] NVIDIA_API_KEY is empty — agent network will use the deterministic fallback draft."
}

$hasNode = [bool](Get-Command node -ErrorAction SilentlyContinue)
if (-not $hasNode) { Write-Warning "[node] Node.js not found - the dashboard will not start." }

$procs = @()
function Start-Svc($name, $file, [string[]]$svcArgs, $cwd) {
    Write-Host "[start] $name"
    $p = Start-Process -FilePath $file -ArgumentList $svcArgs -WorkingDirectory $cwd -NoNewWindow -PassThru
    $script:procs += $p
    return $p
}

try {
    Start-Svc "Neuro-SAN server (8080)" $py @("-m", "neuro_san_studio", "run", "--server-only") $ScriptDir | Out-Null
    Start-Sleep -Seconds 5
    Start-Svc "Gateway API (8000)" $py @("-m", "uvicorn", "gateway.api.main:app", "--port", "8000") $ScriptDir | Out-Null
    Start-Sleep -Seconds 2
    if ($hasNode) {
        if (-not (Test-Path (Join-Path $DashDir "node_modules"))) {
            Write-Host "[npm] installing dashboard deps (first run)..."
            Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm install" -WorkingDirectory $DashDir -NoNewWindow -Wait
        }
        Start-Svc "Dashboard / Vite (5173)" "cmd.exe" @("/c", "npm run dev") $DashDir | Out-Null
    }

    Write-Host ""
    Write-Host "===================================================="
    Write-Host " Neuro-SAN:  http://localhost:8080"
    Write-Host " Gateway:    http://localhost:8000/docs"
    if ($hasNode) { Write-Host " Dashboard:  http://localhost:5173" }
    Write-Host " Press Ctrl+C to stop all services."
    Write-Host "===================================================="
    Write-Host ""

    while ($true) {
        Start-Sleep -Seconds 1
        foreach ($p in $procs) {
            if ($p.HasExited) {
                Write-Warning "[monitor] PID $($p.Id) exited (code $($p.ExitCode)). Shutting down."
                throw "child-exited"
            }
        }
    }
} finally {
    Write-Host "`n[shutdown] Stopping all services..."
    foreach ($p in $procs) {
        if ($p -and -not $p.HasExited) {
            try { & taskkill /PID $p.Id /T /F 2>$null | Out-Null } catch {}
        }
    }
    Write-Host "[shutdown] Done."
}
