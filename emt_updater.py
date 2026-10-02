"""Controleer GitHub Releases en download een gecontroleerde Windows-installer.

De module heeft geen kennis van de interface. Netwerkwerk gebeurt vanuit de
aanroepende worker-thread; de app toont resultaten en voert de installer uit.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GITHUB_RELEASES_API = "https://api.github.com/repos/borisvanderwerff-hub/eventhubrelease/releases?per_page=30"
GITHUB_RELEASES_PAGE = "https://github.com/borisvanderwerff-hub/eventhubrelease/releases"
MAX_INSTALLER_SIZE = 2 * 1024 * 1024 * 1024
_VERSION_PATTERN = re.compile(
    r"^[vV]?(\d+(?:\.\d+)*)(?:[- ]?(alpha|beta|rc)(?:[. -]?(\d+))?)?$",
    re.IGNORECASE,
)
_DIGEST_PATTERN = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


class UpdateDownloadCancelled(Exception):
    """De gebruiker heeft het downloaden geannuleerd."""


def version_key(value: str):
    """Maak een vergelijkbare versievolgorde voor tags als v0.2.2-beta.1."""
    match = _VERSION_PATTERN.fullmatch(str(value or "").strip())
    if not match:
        return None
    numbers = [int(part) for part in match.group(1).split(".")]
    numbers += [0] * (4 - len(numbers))
    suffix = (match.group(2) or "").lower()
    suffix_rank = {"alpha": 0, "beta": 1, "rc": 2, "": 3}[suffix]
    suffix_number = int(match.group(3) or 0)
    return (*numbers[:4], suffix_rank, suffix_number)


def find_latest_update(current_version: str, timeout: float = 6.0):
    """Geef de nieuwste nieuwere release terug, of None als er geen update is."""
    current_key = version_key(current_version)
    if current_key is None:
        raise ValueError(f"Onbekende huidige EventHub-versie: {current_version}")

    request = Request(
        GITHUB_RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "EventHub-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read(4 * 1024 * 1024 + 1).decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("De GitHub-release kon niet worden gecontroleerd.") from exc

    if not isinstance(payload, list):
        raise RuntimeError("GitHub gaf geen geldige releaselijst terug.")

    candidates = []
    for release in payload:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        tag = str(release.get("tag_name", "") or "").strip()
        key = version_key(tag)
        if key is None or key <= current_key:
            continue
        assets = release.get("assets", [])
        if not isinstance(assets, list):
            continue
        installer = next(
            (
                asset for asset in assets
                if isinstance(asset, dict)
                and str(asset.get("name", "")).lower().startswith("eventhub-setup")
                and str(asset.get("name", "")).lower().endswith(".exe")
                and asset.get("state") == "uploaded"
            ),
            None,
        )
        if installer is None:
            continue
        digest = str(installer.get("digest", "") or "")
        if not _DIGEST_PATTERN.fullmatch(digest):
            # Zonder door GitHub gepubliceerde SHA-256-controlesom wordt de
            # installer nooit automatisch uitgevoerd.
            continue
        download_url = str(installer.get("browser_download_url", "") or "")
        if not download_url.startswith("https://github.com/"):
            continue
        try:
            size = int(installer.get("size", 0) or 0)
        except (TypeError, ValueError):
            continue
        if size <= 0 or size > MAX_INSTALLER_SIZE:
            continue
        candidates.append((key, {
            "version": tag.lstrip("vV"),
            "tag": tag,
            "title": str(release.get("name", "") or tag),
            "notes": str(release.get("body", "") or "").strip(),
            "release_url": str(release.get("html_url", "") or GITHUB_RELEASES_PAGE),
            "download_url": download_url,
            "asset_name": Path(str(installer.get("name", ""))).name,
            "size": size,
            "digest": digest.lower(),
        }))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def download_update_installer(update: dict, directory: Path, progress=None, cancel_event=None) -> Path:
    """Download en verifieer de installer; lever een fout bij afwijkende hash."""
    url = str(update.get("download_url", "") or "")
    if not url.startswith("https://github.com/"):
        raise ValueError("De downloadlink is ongeldig.")
    digest_match = _DIGEST_PATTERN.fullmatch(str(update.get("digest", "") or ""))
    if not digest_match:
        raise ValueError("Voor deze release is geen geldige SHA-256-controlesom beschikbaar.")
    expected_hash = digest_match.group(1).lower()
    asset_name = Path(str(update.get("asset_name", ""))).name
    if not asset_name.lower().startswith("eventhub-setup") or not asset_name.lower().endswith(".exe"):
        raise ValueError("De release bevat geen herkenbare EventHub-installer.")
    expected_size = int(update.get("size", 0) or 0)
    if expected_size <= 0 or expected_size > MAX_INSTALLER_SIZE:
        raise ValueError("De installer heeft een ongeldige bestandsgrootte.")

    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / asset_name
    temporary = directory / f"{asset_name}.download"
    request = Request(url, headers={"User-Agent": "EventHub-Updater", "Accept": "application/octet-stream"})
    digest = hashlib.sha256()
    received = 0
    try:
        with urlopen(request, timeout=30) as response, temporary.open("wb") as output:
            if not str(response.geturl()).startswith("https://"):
                raise RuntimeError("De downloadverbinding is niet beveiligd.")
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_INSTALLER_SIZE:
                raise RuntimeError("Het gedownloade bestand is te groot.")
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise UpdateDownloadCancelled()
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                received += len(chunk)
                if received > expected_size or received > MAX_INSTALLER_SIZE:
                    raise RuntimeError("De bestandsgrootte komt niet overeen met de releasegegevens.")
                output.write(chunk)
                digest.update(chunk)
                if progress is not None:
                    progress(min(99, int(received * 100 / expected_size)))
        if received != expected_size:
            raise RuntimeError("De download is onvolledig; de installer is niet uitgevoerd.")
        if cancel_event is not None and cancel_event.is_set():
            raise UpdateDownloadCancelled()
        if digest.hexdigest() != expected_hash:
            raise RuntimeError("De SHA-256-controlesom klopt niet; de installer is niet uitgevoerd.")
        temporary.replace(destination)
        if progress is not None:
            progress(100)
        return destination
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
