from __future__ import annotations

import socket
import json
import threading
import time
import ipaddress
import platform
import re
import subprocess

DISCOVERY_PORT = 37029
DISCOVERY_REQUEST = b"EVENTHUB_DISCOVER_V1"


def _usable_ipv4(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.version == 4 and not address.is_loopback and not address.is_link_local and not address.is_unspecified


def _system_interface_addresses() -> list[tuple[str, str]]:
    """Return (IPv4, interface label) pairs using only operating-system tools."""
    candidates: list[tuple[str, str]] = []
    command = ["ipconfig"] if platform.system() == "Windows" else ["ip", "-4", "-o", "addr", "show"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3)
    except (OSError, subprocess.SubprocessError):
        return candidates
    if result.returncode != 0:
        return candidates
    if platform.system() == "Windows":
        label = ""
        for line in result.stdout.splitlines():
            if line and not line[0].isspace() and line.rstrip().endswith(":"):
                label = line.rstrip().rstrip(":")
            match = re.search(r"IPv4[^:]*:\s*(\d{1,3}(?:\.\d{1,3}){3})", line, re.IGNORECASE)
            if match and _usable_ipv4(match.group(1)):
                candidates.append((match.group(1), label))
    else:
        for line in result.stdout.splitlines():
            match = re.search(r"^\d+:\s+([^\s]+).*?\sinet\s+(\d{1,3}(?:\.\d{1,3}){3})/", line)
            if match and _usable_ipv4(match.group(2)):
                candidates.append((match.group(2), match.group(1)))
    return candidates


def _candidate_score(address: str, label: str = "") -> int:
    """Prefer Windows Mobile Hotspot/ICS above internet and virtual adapters."""
    score = 0
    lowered = label.casefold()
    if address == "192.168.137.1":
        score += 2000  # Windows Internet Connection Sharing default gateway.
    if any(term in lowered for term in ("mobile hotspot", "local area connection*", "lan-verbinding*")):
        score += 1200
    if address.startswith("192.168.137."):
        score += 700
    elif address.startswith("192.168."):
        score += 300
    elif address.startswith("10."):
        score += 220
    elif address.startswith("172."):
        score += 180
    if address.endswith(".1"):
        score += 80
    if any(term in lowered for term in ("virtualbox", "vmware", "docker", "wsl", "vethernet", "hyper-v")):
        score -= 1000
    return score


def local_ip_addresses() -> list[str]:
    """Return usable LAN addresses, ordered with a laptop hotspot first."""
    candidates = _system_interface_addresses()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if _usable_ipv4(address):
                candidates.append((address, "hostname"))
    except OSError:
        pass
    for target in ("192.168.137.2", "8.8.8.8"):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect((target, 9))
            address = sock.getsockname()[0]
            if _usable_ipv4(address):
                candidates.append((address, "route"))
        except OSError:
            pass
        finally:
            sock.close()
    best_labels: dict[str, str] = {}
    for address, label in candidates:
        if address not in best_labels or _candidate_score(address, label) > _candidate_score(address, best_labels[address]):
            best_labels[address] = label
    return sorted(best_labels, key=lambda address: _candidate_score(address, best_labels[address]), reverse=True)


def local_ip_address() -> str:
    addresses = local_ip_addresses()
    return addresses[0] if addresses else "127.0.0.1"


def local_ip_for_peer(peer_address: str) -> str:
    """Pick the interface that can actually answer a discovered client."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((peer_address, 9))
        address = sock.getsockname()[0]
        return address if _usable_ipv4(address) else local_ip_address()
    except OSError:
        return local_ip_address()
    finally:
        sock.close()


def find_free_port(preferred: int = 8080) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return preferred


class HubDiscoveryResponder(threading.Thread):
    """Small UDP responder; it advertises no personal data or session code."""
    def __init__(self, http_port: int, event_name: str, event_date: str = "",
                 source_event_id: str = ""):
        super().__init__(daemon=True)
        self.http_port, self.event_name = http_port, event_name
        self.event_date = str(event_date or "")
        self.source_event_id = str(source_event_id or "")
        self._stop_event = threading.Event()
        self._socket = None

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket = sock
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", DISCOVERY_PORT)); sock.settimeout(.5)
            while not self._stop_event.is_set():
                try: data, address = sock.recvfrom(1024)
                except socket.timeout: continue
                if data == DISCOVERY_REQUEST:
                    advertised_ip = local_ip_for_peer(address[0])
                    payload = json.dumps({
                        "product": "EventHub", "name": self.event_name,
                        "date": self.event_date, "source_event_id": self.source_event_id,
                        "url": f"http://{advertised_ip}:{self.http_port}",
                    }).encode()
                    sock.sendto(payload, address)
        except OSError:
            pass
        finally:
            sock.close()

    def stop(self):
        self._stop_event.set()


def discover_hubs(timeout: float = 1.2) -> list[dict]:
    found = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1); sock.settimeout(.15)
    try:
        sock.bind(("", 0))
        for target in (("255.255.255.255", DISCOVERY_PORT), ("127.0.0.1", DISCOVERY_PORT)):
            try: sock.sendto(DISCOVERY_REQUEST, target)
            except OSError: pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try: data, _ = sock.recvfrom(4096)
            except socket.timeout: continue
            try:
                item = json.loads(data.decode())
                if item.get("product") == "EventHub" and item.get("url"): found[item["url"]] = item
            except (ValueError, UnicodeError): pass
    finally: sock.close()
    return list(found.values())
