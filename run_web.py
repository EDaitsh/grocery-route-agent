"""נקודת כניסה לממשק ה-Web (agent-web.exe): מפעיל את השרת המקומי ופותח חלון של הממשק.

הרצה:  python run_web.py [--port 8765] [--browser]
  --browser  פתיחה בלשונית רגילה בדפדפן במקום חלון אפליקציה נפרד (Edge --app)
"""
import argparse
import socket
import subprocess
import sys
import threading
import time
import webbrowser


def _free_port(preferred: int) -> int:
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _edge_path() -> str | None:
    if sys.platform != "win32":
        return None
    import winreg
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe") as k:
                return winreg.QueryValue(k, None)
        except OSError:
            continue
    return None


def _open_ui(url: str, plain_browser: bool) -> None:
    time.sleep(1.5)
    edge = None if plain_browser else _edge_path()
    if edge:
        subprocess.Popen([edge, f"--app={url}", "--window-size=1280,860"])
    else:
        webbrowser.open(url)


def main() -> None:
    p = argparse.ArgumentParser(description="Grocery Route Agent - Web UI")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--browser", action="store_true", help="open in a regular browser tab")
    args = p.parse_args()

    import uvicorn
    from agent.server import app

    port = _free_port(args.port)
    url = f"http://127.0.0.1:{port}"
    print(f"Grocery Route Agent is running at {url}")
    print("Close this window (or press Ctrl+C) to stop the agent.")
    threading.Thread(target=_open_ui, args=(url, args.browser), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
