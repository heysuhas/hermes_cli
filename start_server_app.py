"""
start_server_app.py - Standalone Web UI Server Launcher with System Tray Icon and logging
"""
import os
import sys

# Crucial fix for windowless (--noconsole) PyInstaller executables:
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# Determine base paths
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))

# Set HERMES_WEB_DIST BEFORE importing web_server to resolve import-order initialization issues
os.environ["HERMES_WEB_DIST"] = os.path.join(app_dir, "web_dist")

# Ensure local directories can be imported by sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# INTERCEPT SUBPROCESS RE-EXECUTION CALLS:
# If the compiled binary is spawned as a child process to run Python modules, scripts, or commands,
# we execute them directly and exit rather than starting another web server and tray icon.
if len(sys.argv) > 1:
    # 1. Module execution: -m <module>
    if sys.argv[1] == "-m" and len(sys.argv) > 2:
        module_name = sys.argv[2]
        sys.argv = [sys.argv[0]] + sys.argv[3:]
        
        if module_name == "hermes_cli.main":
            from hermes_cli.main import main as cli_main
            cli_main()
            sys.exit(0)
        else:
            import runpy
            runpy.run_module(module_name, run_name="__main__", alter_sys=True)
            sys.exit(0)
            
    # 2. Command execution: -c <command>
    elif sys.argv[1] == "-c" and len(sys.argv) > 2:
        cmd_str = sys.argv[2]
        exec(cmd_str)
        sys.exit(0)
        
    # 3. Direct script execution: path/to/script.py
    elif sys.argv[1].endswith(".py") and os.path.exists(sys.argv[1]):
        import runpy
        script_path = sys.argv[1]
        sys.argv = sys.argv[1:]
        runpy.run_path(script_path, run_name="__main__")
        sys.exit(0)

import time
import traceback
import threading
import webbrowser
from PIL import Image, ImageDraw
import pystray

log_dir = os.path.join(app_dir, "data", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "launcher_debug.log")

def write_log(message):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception:
        pass

# Setup top-level exception handler
def handle_exception(exc_type, exc_value, exc_traceback):
    err = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    write_log(f"CRITICAL EXCEPTION:\n{err}")

sys.excepthook = handle_exception

write_log("Launcher process starting...")

try:
    from hermes_cli.web_server import start_server
    write_log("Successfully imported start_server")
except Exception as e:
    write_log(f"Failed to import start_server: {traceback.format_exc()}")

def create_icon_image():
    image = Image.new('RGB', (64, 64), color=(59, 130, 246))
    dc = ImageDraw.Draw(image)
    dc.ellipse([8, 8, 56, 56], fill=(30, 41, 59))
    dc.rectangle([20, 16, 26, 48], fill=(255, 255, 255))
    dc.rectangle([38, 16, 44, 48], fill=(255, 255, 255))
    dc.rectangle([26, 30, 38, 34], fill=(255, 255, 255))
    return image

def launch_dashboard(icon, item):
    write_log("Opening browser dashboard from menu action")
    webbrowser.open("http://127.0.0.1:9119")

def quit_app(icon, item):
    write_log("Exit requested, quitting process")
    icon.stop()
    os._exit(0)

def run_background_server():
    write_log("Starting background server thread...")
    try:
        start_server(host="127.0.0.1", port=9119, open_browser=False)
    except Exception as e:
        write_log(f"FastAPI Server error: {traceback.format_exc()}")

if __name__ == "__main__":
    try:
        # Start the web server in a background thread
        server_thread = threading.Thread(target=run_background_server, daemon=True)
        server_thread.start()
        write_log("Server thread started successfully")

        # Automatically open the web browser on startup after a brief delay
        def auto_open():
            time.sleep(1.5)
            write_log("Auto-opening dashboard browser window")
            webbrowser.open("http://127.0.0.1:9119")
        threading.Thread(target=auto_open, daemon=True).start()

        # Set up the system tray menu
        menu = pystray.Menu(
            pystray.MenuItem("Open Dashboard", launch_dashboard, default=True),
            pystray.MenuItem("Exit", quit_app)
        )

        # Create and run the system tray icon
        icon = pystray.Icon(
            "hermes_agent",
            create_icon_image(),
            "Hermes Agent (Running)",
            menu
        )
        
        write_log("Starting System Tray Icon loop...")
        icon.run()
    except Exception as e:
        write_log(f"Launcher main execution failed: {traceback.format_exc()}")
