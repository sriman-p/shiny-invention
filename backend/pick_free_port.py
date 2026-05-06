#!/usr/bin/env python3
"""Print the first free TCP listen port in [--start, --start + 9]."""

from __future__ import annotations

import argparse
import socket
import sys


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", port))
        except OSError:
            return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--start",
        type=int,
        default=8000,
        help="Lowest candidate port (default 8000)",
    )
    args = ap.parse_args()

    span = range(args.start, args.start + 10)
    for port in span:
        if port_is_free(port):
            print(port)
            return 0

    print(
        f"No free port in [{args.start}, {args.start + 9}]",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
