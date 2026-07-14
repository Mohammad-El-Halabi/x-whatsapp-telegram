import sys
import os
import webbrowser
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config.settings import DEBUG, HOST, PORT
from src.routes.admin import app


def open_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{PORT}")


if __name__ == '__main__':
    print(f"Starting Admin Panel on http://127.0.0.1:{PORT}")
    threading.Thread(target=open_browser, daemon=True).start()
    if getattr(sys, 'frozen', False):
        from waitress import serve
        serve(app, host=HOST, port=PORT)
    else:
        app.run(debug=DEBUG, host=HOST, port=PORT)
