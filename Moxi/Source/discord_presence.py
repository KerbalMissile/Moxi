import threading
import time

try:
    from pypresence import Presence
    from pypresence.exceptions import PyPresenceException
except Exception:
    Presence = None
    PyPresenceException = Exception


MOXI_DISCORD_CLIENT_ID = "1516939730355355728"
RECONNECT_INTERVAL_SECONDS = 15.0
LARGE_IMAGE_KEY = "moxi_logo"


class DiscordPresenceClient:
    """Best-effort Discord Rich Presence client.

    Connects to a locally running Discord client over IPC. If Discord
    isn't running, or pypresence isn't installed, every call here is a
    silent no-op so the rest of Moxi is unaffected.
    """

    def __init__(self, client_id=MOXI_DISCORD_CLIENT_ID):
        self._client_id = client_id
        self._rpc = None
        self._connected = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._start_time = int(time.time())
        self._last_state = None
        self._last_details = None
        self._worker = None

        if Presence is not None and client_id:
            self._worker = threading.Thread(
                target=self._connect_loop, name="moxi-discord-rpc", daemon=True
            )
            self._worker.start()

    def _connect_loop(self):
        while not self._stop_event.is_set():
            if not self._connected:
                self._try_connect()
            self._stop_event.wait(RECONNECT_INTERVAL_SECONDS)

    def _try_connect(self):
        with self._lock:
            if self._connected:
                return
            try:
                rpc = Presence(self._client_id)
                rpc.connect()
                self._rpc = rpc
                self._connected = True
            except Exception:
                self._rpc = None
                self._connected = False
                return

        # Re-apply whatever presence was last requested, now that we're connected.
        if self._last_state is not None or self._last_details is not None:
            self._send_update(self._last_details, self._last_state)

    def _send_update(self, details, state):
        with self._lock:
            if not self._connected or self._rpc is None:
                return
            try:
                self._rpc.update(
                    details=details,
                    state=state,
                    large_image=LARGE_IMAGE_KEY,
                    large_text="Moxi Mod Manager",
                    start=self._start_time,
                )
            except Exception:
                # Connection likely dropped (Discord closed, etc). Mark as
                # disconnected so the reconnect loop will pick it back up.
                self._connected = False
                self._rpc = None

    def set_browsing(self):
        """Generic presence shown on the dashboard / mod database / settings."""
        self._last_details = "Browsing Moxi"
        self._last_state = None
        self._send_update(self._last_details, self._last_state)

    def set_game(self, game_name, installed_count, enabled_count):
        """Presence shown while viewing a specific game's mod list."""
        details = f"Viewing {game_name}"
        if installed_count > 0:
            state = f"{enabled_count}/{installed_count} mods enabled"
        else:
            state = "No mods installed"
        self._last_details = details
        self._last_state = state
        self._send_update(details, state)

    def clear(self):
        with self._lock:
            if self._connected and self._rpc is not None:
                try:
                    self._rpc.clear()
                except Exception:
                    pass

    def close(self):
        self._stop_event.set()
        with self._lock:
            if self._connected and self._rpc is not None:
                try:
                    self._rpc.close()
                except Exception:
                    pass
            self._connected = False
            self._rpc = None
