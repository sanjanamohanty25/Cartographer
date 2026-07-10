import os
import sys
import subprocess
import threading
import time

# Get absolute paths to directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(SCRIPT_DIR)
NEURO_SAN_STUDIO_DIR = os.path.join(WORKSPACE_DIR, "neuro-san-studio")

# Determine python executable from virtual environment
VENV_PYTHON = os.path.join(WORKSPACE_DIR, ".venv", "Scripts", "python.exe")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = os.path.join(NEURO_SAN_STUDIO_DIR, "venv", "Scripts", "python.exe")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable  # Fallback to current system python

print(f"Using Python executable: {VENV_PYTHON}")

# Set up required environment variables
env = os.environ.copy()
env["AGENT_MANIFEST_FILE"] = os.path.abspath(os.path.join(SCRIPT_DIR, "registries", "manifest.hocon"))
env["AGENT_TOOL_PATH"] = os.path.abspath(os.path.join(SCRIPT_DIR, "coded_tools"))

# Print settings
print("--- Environment Configuration ---")
print(f"AGENT_MANIFEST_FILE: {env['AGENT_MANIFEST_FILE']}")
print(f"AGENT_TOOL_PATH: {env['AGENT_TOOL_PATH']}")
print("---------------------------------")

processes = []
shutdown_flag = False

def log_streamer(pipe, prefix):
    """Reads lines from a pipe and prints them with a prefix."""
    try:
        for line in iter(pipe.readline, ''):
            if shutdown_flag:
                break
            if line:
                print(f"{prefix} {line.strip()}")
    except Exception:
        pass

def run_process(cmd, cwd, prefix):
    """Starts a subprocess and spawns threads to stream its stdout and stderr."""
    global shutdown_flag
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        processes.append(proc)
        
        # Threads to stream output
        t_out = threading.Thread(target=log_streamer, args=(proc.stdout, prefix), daemon=True)
        t_err = threading.Thread(target=log_streamer, args=(proc.stderr, prefix), daemon=True)
        t_out.start()
        t_err.start()
        
        return proc
    except Exception as e:
        print(f"Failed to start process {' '.join(cmd)}: {e}")
        return None

def main():
    global shutdown_flag
    
    print("\nStarting Neuro-SAN Server...")
    # Run Neuro-SAN server (listen on port 8080)
    neuro_san_cmd = [VENV_PYTHON, "-m", "neuro_san_studio", "run", "--server-only"]
    proc_server = run_process(neuro_san_cmd, NEURO_SAN_STUDIO_DIR, "[Neuro-SAN Server]")
    
    # Wait a few seconds for the Neuro-SAN server to start up
    time.sleep(3)
    
    print("\nStarting Gateway REST API...")
    # Run FastAPI Gateway (listen on port 8000)
    gateway_cmd = [VENV_PYTHON, "-m", "uvicorn", "gateway.api.main:app", "--port", "8000"]
    proc_gateway = run_process(gateway_cmd, SCRIPT_DIR, "[Gateway API]")
    
    print("\nStarting Streamlit Dashboard...")
    # Run Streamlit Dashboard
    dashboard_cmd = [VENV_PYTHON, "-m", "streamlit", "run", "dashboard/app.py"]
    proc_dashboard = run_process(dashboard_cmd, SCRIPT_DIR, "[Streamlit Dashboard]")
    
    print("\n" + "="*60)
    print("Project successfully launched!")
    print("- Neuro-SAN Server: http://localhost:8080")
    print("- Gateway API:      http://localhost:8000")
    print("- Streamlit UI:     http://localhost:8501 (or default Streamlit port)")
    print("Press Ctrl+C to stop all services.")
    print("="*60 + "\n")
    
    # Keep main thread alive and monitor processes
    try:
        while True:
            # Check if any process terminated unexpectedly
            for p in processes:
                if p.poll() is not None:
                    print(f"\n[Warning] A process terminated unexpectedly with return code {p.returncode}.")
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down all services...")
        shutdown_flag = True
        
        # Terminate all processes
        for p in processes:
            try:
                # Under Windows, use terminate() or taskkill if needed
                p.terminate()
            except Exception:
                pass
        
        # Wait for processes to exit
        for p in processes:
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:
                    p.kill()
                except Exception:
                    pass
        print("All services stopped.")

if __name__ == "__main__":
    main()
