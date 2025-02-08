import streamlit as st
import subprocess
import os
import time
import psutil

class ProcessManager:
    def __init__(self):
        self.exec_path = '/usr/bin/node'
        self.daemon_path = os.path.join(os.getcwd(), 'node_modules/.bin/pm2')
        self.proc_mem_limits = (20 * 1024 * 1024, 120 * 1024 * 1024)  
        self.protected_pids = {7}

    def verify_environment(self):
        try:
            result = subprocess.run(
                "command -v node",
                shell=True,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.exec_path = result.stdout.strip()
                ver_check = subprocess.run(
                    f"{self.exec_path} --version",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if ver_check.returncode == 0:
                    st.success(f"✔ Node.js {ver_check.stdout.strip()}")
                    return True
            st.error("❌ Node.js not found")
            return False
        except Exception as e:
            st.error(f"Environment check error: {str(e)}")
            return False

    def setup_daemon(self):
        if not os.path.exists('package.json'):
            subprocess.run("npm init -y --silent", shell=True, check=True)

        if not os.path.exists('node_modules/pm2'):
            with st.spinner("Installing Process Manager..."):
                result = subprocess.run(
                    "npm install pm2@5.2.2 --save --silent",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    st.error(f"Installation failed: {result.stderr}")
                    return False
                st.success("✅ Process Manager installed")

        return True

    def scan_processes(self):
        app_processes = []
        aux_processes = []

        try:
            for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline', 'create_time']):
                if proc.info['pid'] in self.protected_pids:
                    continue

                mem_usage = proc.info['memory_info'].rss
                cmdline = proc.info['cmdline']

                if 'node' in proc.info['name'].lower() and 'index.js' in ' '.join(cmdline or []):
                    app_processes.append(proc)
                elif self.proc_mem_limits[0] <= mem_usage <= self.proc_mem_limits[1]:
                    aux_processes.append(proc)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        return app_processes, aux_processes

    def monitor_processes(self):
        app_processes, aux_processes = self.scan_processes()

        st.subheader("🔄 Process Monitor")
        st.write(f"Node.js Processes: {len(app_processes)}")
        st.write(f"Auxiliary Processes: {len(aux_processes)}")

        st.write("Active Node.js Processes:")
        for proc in app_processes:
            st.write(f"PID: {proc.pid}, Name: {proc.name()}, Memory: {proc.memory_info().rss / 1024 / 1024:.2f} MB")

        st.write("Active Auxiliary Processes:")
        for proc in aux_processes:
            st.write(f"PID: {proc.pid}, Name: {proc.name()}, Memory: {proc.memory_info().rss / 1024 / 1024:.2f} MB")

        self.cleanup_redundant(aux_processes)

        if len(app_processes) == 1 and (len(aux_processes) == 2 or 2 < len(aux_processes) <= 5):
            st.success("System status normal")
            return

        st.warning("Process count mismatch, restarting service...")
        self.reload_service()

    def cleanup_redundant(self, processes):
        active_procs = {}
        for proc in processes:
            if proc.name() not in active_procs:
                active_procs[proc.name()] = proc
            else:
                if proc.create_time() > active_procs[proc.name()].create_time():
                    active_procs[proc.name()].terminate()
                    active_procs[proc.name()] = proc
                else:
                    proc.terminate()

    def reload_service(self):
        self.reset_daemon()
        self.terminate_processes()

        work_dir = os.getcwd()
        service_path = os.path.join(work_dir, "index.js")

        if not os.path.exists(service_path):
            st.error("❌ Service file missing")
            return

        result = subprocess.run(
            f"{self.daemon_path} start {service_path} --name nodejs-server -f",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            st.error(f"❌ Service start failed: {result.stderr}")
        else:
            st.success("✅ Service restarted")
            subprocess.run(f"{self.daemon_path} save", shell=True, capture_output=True)

    def terminate_processes(self):
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['pid'] in self.protected_pids:
                    continue
                try:
                    cmdline = proc.info['cmdline']
                    if 'node' in proc.info['name'].lower() and 'index.js' in ' '.join(cmdline or []):
                        proc.terminate()
                    elif self.proc_mem_limits[0] <= proc.memory_info().rss <= self.proc_mem_limits[1]:
                        proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            time.sleep(3)
        except Exception as e:
            st.error(f"Process termination error: {str(e)}")

    def reset_daemon(self):
        try:
            subprocess.run(f"{self.daemon_path} delete all", shell=True, check=True)
            subprocess.run(f"{self.daemon_path} kill", shell=True, check=True)
            time.sleep(3)
            st.success("♻️ Process Manager reset complete")
        except Exception as e:
            st.error(f"Reset failed: {str(e)}")

def main():
    st.set_page_config(page_title="Process Management", layout="wide")
    
    if 'manager' not in st.session_state:
        st.session_state.manager = ProcessManager()
    manager = st.session_state.manager

    st.title("🚀 Process Management System")
    
    with st.container():
        st.header("🛠️ Environment Check")
        if not manager.verify_environment():
            return
        
        if not manager.setup_daemon():
            st.error("Environment setup failed")
            return

        st.header("🛡️ Service Management")
        manager.monitor_processes()

        st.header("📁 Directory Contents")
        st.write(os.listdir())

    time.sleep(30)
    st.rerun()

if __name__ == "__main__":
    main()
