import subprocess
import sys
import time
import os
import urllib.request
import urllib.error
import webbrowser

def verify_structure():
    required_files = [
        "templates/login.html",
        "static/css/login.css",
        "static/js/login.js",
        "static/videos/background.mp4",
        "sidecar_python/main.py",
        "backend_node/src/server.js",
        "dashboard_react/vite.config.ts"
    ]
    missing = []
    for f in required_files:
        if not os.path.exists(f):
            missing.append(f)
            
    if missing:
        print("\nERROR:")
        for m in missing:
            print(f"  {m} not found.")
        sys.exit(1)

def cleanup_ports(ports=[5000, 8000, 8001, 3000]):
    """Ensure ports are free before starting services."""
    if os.name == "nt":
        for port in ports:
            try:
                out = subprocess.check_output(f'netstat -ano | findstr LISTENING | findstr :{port}', shell=True, text=True, stderr=subprocess.DEVNULL)
                for line in out.strip().splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        if pid.isdigit() and int(pid) != os.getpid():
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
            except Exception:
                pass

def kill_proc_tree(proc):
    if proc.poll() is None:
        if os.name == "nt":
            subprocess.run(f"taskkill /F /T /PID {proc.pid}", shell=True, capture_output=True)
        else:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

def wait_for_ready(url, name, timeout=30):
    print(f"Waiting for {name} to respond on {url}...", end="", flush=True)
    start_time = time.time()
    test_urls = [url]
    if "localhost" in url:
        test_urls.append(url.replace("localhost", "127.0.0.1"))
    elif "127.0.0.1" in url:
        test_urls.append(url.replace("127.0.0.1", "localhost"))

    while time.time() - start_time < timeout:
        for u in test_urls:
            try:
                req = urllib.request.Request(u, headers={'User-Agent': 'MareTide Poller'})
                with urllib.request.urlopen(req, timeout=1) as response:
                    if response.getcode() in [200, 302, 404]:
                        print(" Ready!")
                        return True
            except urllib.error.HTTPError as e:
                # 404/401 is fine, it means the server is running and routing
                if e.code in [404, 401, 400]:
                    print(" Ready!")
                    return True
            except Exception:
                pass
        print(".", end="", flush=True)
        time.sleep(0.5)
    print("\nTimeout: Server did not respond within timeout.")
    return False

def main():
    print("Checking project structure...")
    verify_structure()
    print("Project structure is correct.\n")

    print("Cleaning up old port bindings if any...")
    cleanup_ports([5000, 8000, 8001, 3000])

    print("Starting MareTide React/Node.js Unified Services...")
    python_exe = sys.executable

    # 1. Flask Authentication Server (Port 5000)
    print("Launching Flask Authentication Server on port 5000...")
    flask_proc = subprocess.Popen([python_exe, "-u", "server.py"])
    if not wait_for_ready("http://127.0.0.1:5000/", "Flask Server"):
        kill_proc_tree(flask_proc)
        sys.exit(1)

    # 2. Python FastAPI Sidecar (Port 8001)
    print("Launching Python FastAPI Sidecar on port 8001...")
    sidecar_proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--log-level", "warning"],
        cwd="sidecar_python"
    )
    if not wait_for_ready("http://127.0.0.1:8001/api/vessel-state", "Python Sidecar", timeout=60):
        kill_proc_tree(flask_proc)
        kill_proc_tree(sidecar_proc)
        sys.exit(1)

    # 3. Node.js API Gateway (Port 8000)
    print("Launching Node.js API Gateway on port 8000...")
    node_cmd = ["node", "src/server.js"]
    if os.name == "nt":
        node_proc = subprocess.Popen(node_cmd, cwd="backend_node", shell=True)
    else:
        node_proc = subprocess.Popen(node_cmd, cwd="backend_node")

    if not wait_for_ready("http://127.0.0.1:8000/api/auth/session", "Node.js Gateway"):
        kill_proc_tree(flask_proc)
        kill_proc_tree(sidecar_proc)
        kill_proc_tree(node_proc)
        sys.exit(1)

    # 4. React Frontend Vite Dev Server (Port 3000)
    print("Launching React Dashboard Vite Server on port 3000...")
    vite_cmd = ["npx", "vite", "--port", "3000", "--host", "127.0.0.1"]
    if os.name == "nt":
        vite_proc = subprocess.Popen(vite_cmd, cwd="dashboard_react", shell=True)
    else:
        vite_proc = subprocess.Popen(vite_cmd, cwd="dashboard_react")

    if not wait_for_ready("http://127.0.0.1:3000/", "React Dashboard", timeout=60):
        kill_proc_tree(flask_proc)
        kill_proc_tree(sidecar_proc)
        kill_proc_tree(node_proc)
        kill_proc_tree(vite_proc)
        sys.exit(1)

    print("\nAll MareTide JS Services launched successfully.")
    print("- Authentication Login Portal: http://localhost:5000")
    print("- React Dashboard (Dev): http://localhost:3000")
    print("- Express API Gateway: http://localhost:8000")
    print("- FastAPI Sidecar Engine: http://localhost:8001\n")

    print("Opening browser to http://localhost:5000...")
    webbrowser.open("http://localhost:5000")

    print("\nPress Ctrl+C to stop all services.\n")

    processes = {
        "Flask Server": flask_proc,
        "Python Sidecar": sidecar_proc,
        "Node.js Gateway": node_proc,
        "Vite Frontend": vite_proc
    }

    try:
        while True:
            for name, proc in list(processes.items()):
                exit_code = proc.poll()
                if exit_code is not None:
                    print(f"\n[ERROR] {name} exited unexpectedly with code {exit_code}")
                    sys.exit(1)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        for name, proc in processes.items():
            print(f"Stopping {name}...")
            kill_proc_tree(proc)
        print("All services stopped.")

if __name__ == "__main__":
    main()
