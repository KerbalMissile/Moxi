import json
import locale
import os
import platform
import queue
import random
import sys
import threading
import time
from datetime import datetime, timezone

import requests


def _get_data_dir():
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", "")
        if not base:
            base = os.path.expanduser("~\\AppData\\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(base, "Moxi")


DATA_DIR = _get_data_dir()
SETTINGS_PATH = os.path.join(DATA_DIR, "stats_settings.json")
DEBUG_LOG_PATH = os.path.join(DATA_DIR, "stats_debug.log")
DEFAULT_APTABASE_APP_KEY = "A-US-3827570468"
APP_KEY_ENV_NAMES = (
    "MOXI_APTABASE_APP_KEY",
    "APTABASE_APP_KEY",
    "A-US-3827570468",
)
MAX_BATCH_SIZE = 25
FLUSH_INTERVAL_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 5.0
SDK_VERSION = "aptabase-python@0.1.0"


def _load_app_key():
    for env_name in APP_KEY_ENV_NAMES:
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    return DEFAULT_APTABASE_APP_KEY


def _normalized_locale():
    candidates = []
    try:
        current = locale.getlocale()[0]
        if current:
            candidates.append(current)
    except Exception:
        pass
    try:
        default = locale.getdefaultlocale()[0]
        if default:
            candidates.append(default)
    except Exception:
        pass

    for value in candidates:
        normalized = str(value).replace("_", "-").strip()
        if 2 <= len(normalized) <= 10:
            return normalized
        if len(normalized) >= 2:
            short = normalized.split("-", 1)[0]
            if 2 <= len(short) <= 10:
                return short
    return "en-US"


class StatsClient:
    def __init__(self, app_version):
        self._app_version = app_version
        self._app_key = _load_app_key()
        self._is_debug = not bool(getattr(sys, "frozen", False))
        self._session_id = self._new_session_id()
        self._session_started_at = time.time()
        self._session_closed = False
        self._settings = self._load_settings()
        self._http = requests.Session()

        self._events = queue.Queue()
        self._worker = None
        self._worker_lock = threading.Lock()
        self._stop_event = threading.Event()

        self._log_debug(
            f"init app_version={self._app_version} "
            f"app_key_present={bool(self._app_key)} "
            f"consent={self._settings.get('consent')} "
            f"is_debug={self._is_debug} "
            f"host={self._host_from_app_key() if self._app_key else 'n/a'}"
        )

        if self.is_enabled():
            self._ensure_worker()

    def _load_settings(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception as exc:
                self._log_debug(f"failed to read settings: {exc!r}")
        return {"consent": None}

    def _save_settings(self):
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as exc:
            self._log_debug(f"failed to save settings: {exc!r}")

    def _log_debug(self, message):
        line = f"[Moxi Stats] {message}"
        try:
            print(line, flush=True)
        except Exception:
            pass
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"{self._iso_now()} {line}\n")
        except Exception:
            pass

    def has_consent_decision(self):
        return self._settings.get("consent") in (True, False)

    def is_enabled(self):
        return self._settings.get("consent") is True and bool(self._app_key)

    def set_consent(self, accepted):
        accepted = bool(accepted)
        now = self._iso_now()
        self._settings["consent"] = accepted
        self._settings["consent_updated_at"] = now
        if accepted:
            self._settings["consent_accepted_at"] = now
            self._log_debug("consent accepted")
            self._ensure_worker()
        else:
            self._settings["consent_declined_at"] = now
            self._log_debug("consent declined")
            self._stop_worker()
        self._save_settings()

    def track_consent_accepted(self):
        self.track("analytics_consent_accepted")

    def track_app_started(self):
        self.track("app_started")

    def track_mod_install(self, game_key, count):
        if not game_key or count <= 0:
            return
        for _ in range(int(count)):
            self.track(f"{game_key}_mods_installed", {"count": 1})

    def track_mod_deleted(self, game_key, count):
        if not game_key or count <= 0:
            return
        for _ in range(int(count)):
            self.track(f"{game_key}_mods_deleted", {"count": 1})

    def close_session(self):
        if self._session_closed:
            return

        duration_seconds = max(0, int(time.time() - self._session_started_at))
        self._log_debug(f"closing session duration_seconds={duration_seconds}")
        self._session_closed = True
        if self.is_enabled():
            payload = {
                "timestamp": self._iso_now(),
                "sessionId": self._session_id,
                "eventName": "session_ended",
                "systemProps": self._system_props(),
                "props": self._sanitize_props({"duration_seconds": duration_seconds}),
            }
            self._log_debug("sending session_ended synchronously")
            self._flush_batch([payload])
        self._stop_worker()

    def track(self, event_name, props=None):
        if not self.is_enabled():
            self._log_debug(
                f"skipping event={event_name} enabled={self.is_enabled()} "
                f"consent={self._settings.get('consent')} app_key_present={bool(self._app_key)}"
            )
            return
        if not self._ensure_worker():
            self._log_debug(f"worker unavailable for event={event_name}")
            return

        payload = {
            "timestamp": self._iso_now(),
            "sessionId": self._session_id,
            "eventName": event_name,
            "systemProps": self._system_props(),
            "props": self._sanitize_props(props),
        }
        self._events.put(payload)
        self._log_debug(f"queued event={event_name}")

    def _ensure_worker(self):
        if not self.is_enabled() or self._session_closed:
            return False

        with self._worker_lock:
            if self._worker and self._worker.is_alive():
                return True

            self._stop_event = threading.Event()
            self._worker = threading.Thread(
                target=self._worker_main,
                name="moxi-aptabase",
                daemon=True,
            )
            self._worker.start()
            self._log_debug("worker started")
            return True

    def _stop_worker(self):
        with self._worker_lock:
            worker = self._worker
            if not worker:
                return
            self._worker = None
            self._stop_event.set()

        self._events.put(None)
        try:
            worker.join(timeout=10)
        except Exception as exc:
            self._log_debug(f"worker join failed: {exc!r}")

    def _worker_main(self):
        batch = []
        deadline = time.monotonic() + FLUSH_INTERVAL_SECONDS
        self._log_debug("worker loop entered")

        while True:
            timeout = max(0.0, deadline - time.monotonic())
            try:
                item = self._events.get(timeout=timeout)
            except queue.Empty:
                item = None

            if item is None:
                if batch:
                    self._flush_batch(batch)
                    batch = []
                if self._stop_event.is_set():
                    self._log_debug("worker stopping")
                    return
                deadline = time.monotonic() + FLUSH_INTERVAL_SECONDS
                continue

            batch.append(item)
            if len(batch) >= MAX_BATCH_SIZE:
                self._flush_batch(batch)
                batch = []
                deadline = time.monotonic() + FLUSH_INTERVAL_SECONDS

    def _flush_batch(self, batch):
        if not batch:
            return

        url = f"{self._host_from_app_key()}/api/v0/events"
        event_names = [item.get("eventName", "?") for item in batch]
        event_counts = [item.get("props", {}).get("count") for item in batch]
        try:
            response = self._http.post(
                url,
                json=batch[:MAX_BATCH_SIZE],
                headers={
                    "Content-Type": "application/json",
                    "App-Key": self._app_key,
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            self._log_debug(
                f"flushed events count={len(batch)} names={event_names} props_count={event_counts} status={response.status_code}"
            )
        except Exception as exc:
            response_text = ""
            try:
                response_text = response.text
            except Exception:
                response_text = ""
            self._log_debug(
                f"flush failed count={len(batch)} names={event_names} props_count={event_counts} error={exc!r} response={response_text!r}"
            )

    def _host_from_app_key(self):
        return "https://eu.aptabase.com" if "EU" in self._app_key else "https://us.aptabase.com"

    def _system_props(self):
        return {
            "locale": _normalized_locale(),
            "osName": platform.system() or "Windows",
            "osVersion": platform.release() or "",
            "deviceModel": platform.machine() or platform.node() or "unknown",
            "isDebug": self._is_debug,
            "appVersion": self._app_version,
            "sdkVersion": SDK_VERSION,
        }

    def _sanitize_props(self, props):
        if not props:
            return {}

        sanitized = {}
        for key, value in props.items():
            if value is None:
                continue
            if isinstance(value, bool):
                sanitized[str(key)] = int(value)
            elif isinstance(value, (int, float, str)):
                sanitized[str(key)] = value
            else:
                sanitized[str(key)] = str(value)
        return sanitized

    def _new_session_id(self):
        epoch_seconds = int(datetime.now().timestamp())
        random_number = random.randint(0, 99999999)
        return str(epoch_seconds * 100000000 + random_number)

    def _iso_now(self):
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
