"""Small TCP relay used to expose a WSL loopback-only proxy to Docker workers."""

from __future__ import annotations

import argparse
import socket
import socketserver
import threading


def _pump(source: socket.socket, target: socket.socket) -> None:
    try:
        while chunk := source.recv(65536):
            target.sendall(chunk)
    finally:
        try:
            target.shutdown(socket.SHUT_WR)
        except OSError:
            pass


class RelayHandler(socketserver.BaseRequestHandler):
    upstream: tuple[str, int]

    def handle(self) -> None:
        with socket.create_connection(self.upstream, timeout=15) as upstream:
            upstream.settimeout(None)
            outbound = threading.Thread(
                target=_pump,
                args=(self.request, upstream),
                daemon=True,
            )
            outbound.start()
            _pump(upstream, self.request)
            outbound.join(timeout=5)


class ThreadingRelay(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen-host", required=True)
    parser.add_argument("--listen-port", required=True, type=int)
    parser.add_argument("--upstream-host", required=True)
    parser.add_argument("--upstream-port", required=True, type=int)
    args = parser.parse_args()

    RelayHandler.upstream = (args.upstream_host, args.upstream_port)
    with ThreadingRelay((args.listen_host, args.listen_port), RelayHandler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
