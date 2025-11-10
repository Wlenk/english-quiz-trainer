import uvicorn
from app import app
import argparse
import webbrowser
import socket

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    # 如果 host 是 0.0.0.0，浏览器使用 localhost
    browser_host = args.host
    if browser_host == "0.0.0.0":
        browser_host = "localhost"

    url = f"http://{browser_host}:{args.port}"
    webbrowser.open(url)

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
