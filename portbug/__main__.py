"""Cross-platform entrypoint: python -m portbug."""

import argparse
from pathlib import Path

from .server import Server
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Portbug Bank Cyber Defense Center • made by Vaibhav Thakur")
    parser.add_argument("--host", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1", help="Keep loopback default; 0.0.0.0 is for an isolated container only")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--data-dir", type=Path, default=Path(".local"))
    parser.add_argument("--backup", type=Path, help="Create a verified local backup in a NEW directory and exit")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    store = Store(args.data_dir)
    if args.backup:
        store.backup(args.backup)
        print(f"Verified local backup created: {args.backup}")
        print("Contains a sensitive local audit key. Keep it private; storage is not encrypted.")
        return
    with Server((args.host, args.port), store) as server:
        print("Portbug Bank | Cyber Defense Center | Made by Vaibhav Thakur", flush=True)
        print("Fictional bank. Synthetic data. Local single-operator simulation.", flush=True)
        print(f"Open http://127.0.0.1:{args.port} — Ctrl+C to stop", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nDefense center stopped.")


if __name__ == "__main__":
    main()
