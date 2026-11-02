"""Start Portbug Bank with Python alone on Windows, macOS, or Linux."""

import argparse
from pathlib import Path

from .server import Server
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Portbug Bank · Made by Vaibhav Thakur")
    parser.add_argument("--host", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--data-dir", type=Path, default=Path(".local-banking"))
    parser.add_argument("--backup", type=Path, help="Back up the complete workspace to a NEW directory and exit")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    try:
        store = Store(args.data_dir)
        if args.backup:
            store.backup(args.backup)
            print("Complete local banking backup created. It contains sensitive local account data and keys; keep it private.")
            return
        with Server((args.host, args.port), store) as server:
            print("Portbug Bank · Zurich · Made by Vaibhav Thakur", flush=True)
            print(f"Open http://127.0.0.1:{args.port} and create your local account.", flush=True)
            print("Fictional banking workspace. Synthetic money. Ctrl+C to stop.", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print("\nBanking workspace stopped.")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Startup failed: {exc}\n")


if __name__ == "__main__":
    main()
