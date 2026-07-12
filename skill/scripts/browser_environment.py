from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Any

SUPPORTED_CHANNELS = {"chromium", "chrome", "msedge", "firefox", "webkit"}


def normalize_browser(value: str) -> str:
    name = value.lower()
    if "edge" in name:
        return "msedge"
    if "chrome" in name:
        return "chrome"
    if "firefox" in name:
        return "firefox"
    if "chromium" in name:
        return "chromium"
    if "safari" in name or "webkit" in name:
        return "webkit"
    return "unknown"


def _windows_default_browser() -> tuple[str, str]:
    try:
        import winreg
    except ImportError:
        return "unknown", "Windows registry module unavailable"
    try:
        path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value = str(winreg.QueryValueEx(key, "ProgId")[0])
        return normalize_browser(value), f"Windows HTTPS association: {value}"
    except (FileNotFoundError, OSError):
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"https\shell\open\command") as key:
            value = str(winreg.QueryValueEx(key, "")[0])
        return normalize_browser(value), f"Windows HTTPS command: {value}"
    except (FileNotFoundError, OSError):
        return "unknown", "Windows HTTPS association unavailable"


def _command_default_browser(command: list[str], source: str) -> tuple[str, str]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=5, check=False)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return "unknown", f"{source} unavailable"
    value = result.stdout.strip()
    return normalize_browser(value), f"{source}: {value}" if value else f"{source} returned no browser"


def detect_default_browser() -> tuple[str, str]:
    system = platform.system()
    if system == "Windows":
        return _windows_default_browser()
    if system == "Linux":
        return _command_default_browser(["xdg-settings", "get", "default-web-browser"], "xdg-settings")
    if system == "Darwin":
        return _command_default_browser(
            ["defaults", "read", "com.apple.LaunchServices/com.apple.launchservices.secure", "LSHandlers"],
            "LaunchServices",
        )
    return "unknown", f"Unsupported operating system: {system}"


def _windows_candidate_paths() -> dict[str, list[Path]]:
    roots = [Path(value) for value in (os.getenv("PROGRAMFILES"), os.getenv("PROGRAMFILES(X86)"), os.getenv("LOCALAPPDATA")) if value]
    return {
        "msedge": [root / "Microsoft/Edge/Application/msedge.exe" for root in roots],
        "chrome": [root / "Google/Chrome/Application/chrome.exe" for root in roots],
        "firefox": [root / "Mozilla Firefox/firefox.exe" for root in roots],
    }


def _mac_candidate_paths() -> dict[str, list[Path]]:
    return {
        "msedge": [Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")],
        "chrome": [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")],
        "firefox": [Path("/Applications/Firefox.app/Contents/MacOS/firefox")],
    }


def _command_paths(names: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    for name in names:
        value = shutil.which(name)
        if value:
            paths.append(Path(value))
    return paths


def _linux_candidate_paths() -> dict[str, list[Path]]:
    return {
        "msedge": _command_paths(("microsoft-edge", "microsoft-edge-stable")),
        "chrome": _command_paths(("google-chrome", "google-chrome-stable")),
        "firefox": _command_paths(("firefox",)),
        "chromium": _command_paths(("chromium", "chromium-browser")),
    }


def _candidate_paths() -> dict[str, list[Path]]:
    system = platform.system()
    if system == "Windows":
        return _windows_candidate_paths()
    if system == "Darwin":
        return _mac_candidate_paths()
    return _linux_candidate_paths()


def installed_branded_channels() -> dict[str, str]:
    result: dict[str, str] = {}
    for channel, candidates in _candidate_paths().items():
        executable = next((path for path in candidates if path.is_file()), None)
        if executable:
            result[channel] = str(executable)
    return result


def playwright_status() -> tuple[bool, str]:
    if importlib.util.find_spec("playwright") is None:
        return False, "not installed"
    try:
        return True, metadata.version("playwright")
    except metadata.PackageNotFoundError:
        return True, "installed"


def bundled_channels() -> dict[str, str]:
    available, _ = playwright_status()
    if not available:
        return {}
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            candidates = {
                "chromium": Path(playwright.chromium.executable_path),
                "firefox": Path(playwright.firefox.executable_path),
                "webkit": Path(playwright.webkit.executable_path),
            }
            return {name: str(path) for name, path in candidates.items() if path.is_file()}
    except Exception:
        return {}


def inspect_browser_environment() -> dict[str, Any]:
    default_browser, default_source = detect_default_browser()
    python_available, playwright_version = playwright_status()
    channels = installed_branded_channels()
    channels.update({name: path for name, path in bundled_channels().items() if name not in channels})
    eligible_default = default_browser in channels and default_browser in SUPPORTED_CHANNELS
    recommended = default_browser if eligible_default else next((name for name in ("msedge", "chrome", "firefox", "chromium", "webkit") if name in channels), "")
    if not python_available:
        readiness = "playwright_python_missing"
    elif not recommended:
        readiness = "eligible_browser_missing"
    else:
        readiness = "ready"
    return {
        "operating_system": platform.system(),
        "default_browser": default_browser,
        "default_browser_source": default_source,
        "default_browser_eligible": eligible_default,
        "playwright_python": playwright_version,
        "installed_channels": channels,
        "recommended_channel": recommended,
        "readiness": readiness,
        "mcp_note": "The local preflight cannot inspect agent MCP tools. Prefer an available browser MCP and verify its configured channel separately.",
    }


def resolve_browser_channel(requested: str, environment: dict[str, Any]) -> str:
    if requested != "auto":
        return requested
    channel = str(environment.get("recommended_channel", ""))
    if not channel:
        raise RuntimeError("No eligible Playwright browser was detected. Install a supported browser or a Playwright browser build.")
    return channel
