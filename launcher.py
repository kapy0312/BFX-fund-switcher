import sys
import os
import threading
import time
import webview
from app import app

PORT = 9528

def start_flask():
    if getattr(sys, 'frozen', False):
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
    app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)

if __name__ == '__main__':
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()
    time.sleep(1.5)
    window = webview.create_window(
        'BFX Fund Switcher',
        f'http://127.0.0.1:{PORT}',
        width=880,
        height=920,
        resizable=True,
        min_size=(600, 600),
    )
    webview.start()