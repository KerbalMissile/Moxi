import os
import sys
import json
import io
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageOps, ImageTk
import threading
import queue
import requests
from urllib.parse import urljoin

from mod_manager import ModConflictError, ModManager, SteamScanner, THUNDERSTORE_CONFIGS
from stats import StatsClient

DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Moxi")
APP_SETTINGS_PATH = os.path.join(DATA_DIR, "app_settings.json")

SUPPORTED_GAMES = {
    "1284190": {"name": "Planet Crafter",        "supported": True, "game_key": "planet_crafter"},
    "1696810": {"name": "Railroads Online",      "supported": True, "game_key": "railroads_online"},
    "2009350": {"name": "Out Of Ore",            "supported": True, "game_key": "out_of_ore"},
    "264710":  {"name": "Subnautica",             "supported": True, "game_key": "subnautica"},
    "848450":  {"name": "Subnautica: Below Zero", "supported": True, "game_key": "subnautica_bz"},
    "1962700":  {"name": "Subnautica 2",          "supported": True, "game_key": "subnautica_2"},
    "433340":  {"name": "Slime Rancher",          "supported": True, "game_key": "slime_rancher"},
    "1657630": {"name": "Slime Rancher 2",        "supported": True, "game_key": "slime_rancher_2"},
    "2709570": {"name": "Supermarket Together",  "supported": True, "game_key": "supermarket_together"},
    "1366540": {"name": "Dyson Sphere Program",   "supported": True, "game_key": "dyson_sphere"},
    "1625450": {"name": "Muck",                   "supported": True, "game_key": "muck"},
    "632360":  {"name": "Risk of Rain 2",         "supported": True, "game_key": "risk_of_rain_2"},
    "823500":  {"name": "BONEWORKS",              "supported": True, "game_key": "boneworks"},
    "3527290": {"name": "PEAK",                   "supported": True, "game_key": "peak"},
    "3164500": {"name": "Schedule I",              "supported": True, "game_key": "schedule_i"},
    "1592190": {"name": "BONELAB",                "supported": True, "game_key": "bonelab"},
    "892970":  {"name": "Valheim",                 "supported": True, "game_key": "valheim"},
    "387990":  {"name": "Scrap Mechanic",          "supported": True, "game_key": "scrap_mechanic"},
}

CUSTOM_ART_URLS = {
    "3527290": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/3527290/31bac6b2eccf09b368f5e95ce510bae2baf3cfcd/header.jpg?t=1773856924",
}

CURATED_MODS_REPO_URL = "https://github.com/KerbalMissile/MoxiDefaultMods"

THUNDERSTORE_GAMES = {"dyson_sphere", "muck", "risk_of_rain_2", "boneworks", "peak", "schedule_i", "bonelab", "supermarket_together", "valheim", "scrap_mechanic"}

NEWLY_ADDED = {"subnautica_2"}

THUNDERSTORE_BLOCKLIST = {
    "schedule_i":    {"LavaGang-MelonLoader", "ebkr-r2modman", "Kesomannen-GaleModManager"},
    "dyson_sphere":  {"ebkr-r2modman", "xiaoye97-BepInEx", "CapsaicinBunny-BepInEx_LTS", "Kesomannen-GaleModManager"},
    "muck":          {"BepInEx-BepInExPack_Muck", "ebkr-r2modman", "Kesomannen-GaleModManager"},
    "boneworks":     {"LavaGang-MelonLoader", "ebkr-r2modman", "Kesomannen-GaleModManager"},
    "peak":          {"BepInEx-BepInExPack_PEAK", "ebkr-r2modman", "Kesomannen-GaleModManager"},
    "risk_of_rain_2": {"bbepis-BepInExPack", "ebkr-r2modman", "Kesomannen-GaleModManager"},
    "bonelab":       {"LavaGang-MelonLoader", "ebkr-r2modman", "Kesomannen-GaleModManager"},
    "supermarket_together": {"BepInEx-BepInExPack", "ebkr-r2modman", "Kesomannen-GaleModManager"},
    "valheim":       {"denikson-BepInExPack_Valheim", "ebkr-r2modman", "Kesomannen-GaleModManager"},
    "scrap_mechanic": {"ebkr-r2modman", "Kesomannen-GaleModManager"},
}

GAME_KEY_TO_NAME    = {v["game_key"]: v["name"] for v in SUPPORTED_GAMES.values()}
GAME_NAMES          = [v["name"] for v in SUPPORTED_GAMES.values() if v["supported"]]
GAME_NAMES_ALL      = [v["name"] for v in SUPPORTED_GAMES.values()]

MOXI_VERSION = "2.6.1"
MOXI_REPO    = "KerbalMissile/Moxi"

BG       = "#111111"
ACCENT   = "#FF0051"
CARD_BG  = "#1a1a1a"
NAV_BG   = "#0d0d0d"
TEXT_DIM = "#888888"
TEXT_ON  = "#ffffff"
GLOW_CLR = "#FF0051"

CARD_W = 320
CARD_H = 210
ART_W  = 300
ART_H  = 140
DASH_CARD_W = ART_W




def _assets_dir():
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "assets")
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "assets")


def _glow_on_hover(widget, targets=None, bg_normal=None, bg_hover="#222222", is_btn=False):
    targets   = targets or [widget]
    bg_normal = bg_normal or widget.cget("fg_color")
    # Track hover state to avoid redundant configure calls
    state = {"hovered": False}

    if is_btn:
        def enter(e):
            if state["hovered"]:
                return
            state["hovered"] = True
            try:
                widget.configure(border_width=2, border_color=GLOW_CLR)
            except Exception:
                pass
        def leave(e):
            if not state["hovered"]:
                return
            state["hovered"] = False
            try:
                widget.configure(border_width=0)
            except Exception:
                pass
    else:
        def enter(e):
            if state["hovered"]:
                return
            state["hovered"] = True
            try:
                widget.configure(fg_color=bg_hover, border_width=2, border_color=GLOW_CLR)
            except Exception:
                pass
        def leave(e):
            if not state["hovered"]:
                return
            state["hovered"] = False
            try:
                widget.configure(fg_color=bg_normal, border_width=0)
            except Exception:
                pass

    for t in targets:
        try:
            t.bind("<Enter>", enter)
            t.bind("<Leave>", leave)
        except Exception:
            pass


class MoxiApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("")
        self.geometry("1200x750")
        self.minsize(950, 620)
        self.configure(fg_color=BG)
        self.after(50, self._apply_titlebar_color)
        self._set_window_icon()

        self._logo_img       = None
        self._art_cache      = {}
        self._art_photo_cache = {}
        self._art_load_queue = queue.Queue()
        self._art_loader_started = False
        self._art_loader_lock = threading.Lock()
        self._art_thread_sem = threading.Semaphore(4)  # cap concurrent image fetches
        self._app_settings = self._load_app_settings()
        self._mod_icon_cache = {}
        self._mod_icon_loading = set()
        self._mod_icon_lock    = threading.Lock()
        self._mod_icon_sem     = threading.Semaphore(6)  # cap concurrent icon fetches
        self._detected       = []
        self._detected_inner = None
        self._active_frame   = None

        self._mod_manager    = ModManager()
        self._mod_index      = {}
        self._detected_map   = {}
        self._index_loading  = False
        self._selected_game       = GAME_NAMES[0]
        self._recently_played     = self._load_recently_played()
        self._recently_played_row = None
        self._game_index          = {}
        self._coming_soon_row     = None
        self._pending_update      = None
        self._news_cache          = None
        self._thunderstore_cache  = {}
        self._ts_loading          = set()
        self._current_page        = None
        self._available_mods_cache = {}
        self._dismissed_warnings  = self._mod_manager.load_dismissed_warnings()
        self._stats = StatsClient(MOXI_VERSION)
        self._stats_consent_required = not self._stats.has_consent_decision()

        self._load_logo()
        self._ensure_art_loader()
        self._build_topbar()
        self._build_content_area()
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)
        self._show_page("stats_consent" if self._stats_consent_required else "dashboard")
        if not self._stats_consent_required:
            self._stats.track_app_started()

        threading.Thread(target=self._scan_steam, daemon=True).start()
        threading.Thread(target=self._do_fetch_index, daemon=True).start()
        threading.Thread(target=self._do_fetch_game_index, daemon=True).start()
        threading.Thread(target=self._check_app_update_startup, daemon=True).start()
        self.after(200, self._check_post_update)

    def _load_recently_played(self):
        path = os.path.join(DATA_DIR, "recently_played.json")
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_recently_played(self):
        path = os.path.join(DATA_DIR, "recently_played.json")
        try:
            with open(path, "w") as f:
                json.dump(self._recently_played, f, indent=2)
        except Exception:
            pass

    def _load_app_settings(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(APP_SETTINGS_PATH):
            try:
                with open(APP_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {"staggered_loading": True}

    def _save_app_settings(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(APP_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._app_settings, f, indent=2)
        except Exception:
            pass

    def _is_staggered_loading_enabled(self):
        return self._app_settings.get("staggered_loading", True) is True

    def _set_staggered_loading_enabled(self, enabled):
        self._app_settings["staggered_loading"] = bool(enabled)
        self._save_app_settings()

    def _record_play(self, game):
        self._recently_played = [g for g in self._recently_played if g["appid"] != game["appid"]]
        self._recently_played.insert(0, game)
        self._recently_played = self._recently_played[:5]
        self._save_recently_played()
        self._refresh_recently_played_row()

    def _refresh_recently_played_row(self):
        row = self._recently_played_row
        if row is None:
            return
        try:
            for w in row.winfo_children():
                w.destroy()
            for game in self._recently_played:
                self._make_game_card(row, game)
        except Exception:
            pass

    def _get_available_mods_for_game(self, game_key, fetch_thunderstore=False):
        curated_raw = self._mod_index.get("games", {}).get(game_key, {}).get("mods", [])
        curated = [{**m, "source": m.get("source", "curated")} for m in curated_raw]
        curated_ids = {m["id"] for m in curated}

        thunderstore_mods = []
        if game_key in THUNDERSTORE_GAMES:
            ts_cached = self._thunderstore_cache.get(game_key)
            if ts_cached is None and fetch_thunderstore:
                try:
                    ts_cached = self._mod_manager.fetch_thunderstore_packages(game_key)
                except Exception:
                    ts_cached = []
                self._thunderstore_cache[game_key] = ts_cached
            elif ts_cached is None:
                ts_cached = []

            blocked = THUNDERSTORE_BLOCKLIST.get(game_key, set())
            thunderstore_mods = [
                m for m in ts_cached
                if m["id"] not in curated_ids and m["id"] not in blocked
            ]

        manual_mods_raw = self._mod_manager.get_manual_mods(game_key)
        available_ids = curated_ids | {m["id"] for m in thunderstore_mods}
        manual_mods = [
            m for m in manual_mods_raw
            if m["id"] not in available_ids
        ]

        signature = (
            tuple((m.get("id"), m.get("version"), m.get("source")) for m in curated),
            tuple((m.get("id"), m.get("version"), m.get("source")) for m in thunderstore_mods),
            tuple((m.get("id"), m.get("version"), m.get("source")) for m in manual_mods),
        )
        cached = self._available_mods_cache.get(game_key)
        if cached and cached[0] == signature:
            return cached[1]

        combined = curated + thunderstore_mods + manual_mods
        self._available_mods_cache[game_key] = (signature, combined)
        return combined

    def _build_search_index(self, mods):
        search_index = []
        for mod in mods:
            name = mod.get("name", "")
            mod_id = mod.get("id", "")
            words = set()
            for word in name.lower().split():
                words.add(word.strip(".,!?-"))
            for part in mod_id.lower().replace("-", "_").split("_"):
                if part:
                    words.add(part)
            for tag in mod.get("tags", []):
                words.add(tag.lower())
            blob = " ".join([
                name,
                mod.get("author", ""),
                mod.get("description", ""),
                mod_id.replace("_", " ").replace("-", " "),
            ]).lower()
            search_index.append((words, blob))
        return search_index

    def _source_url_for_mod(self, game_key, mod):
        source = mod.get("source", "curated")
        if source == "curated":
            return CURATED_MODS_REPO_URL
        if source == "thunderstore":
            package_url = mod.get("package_url")
            if package_url:
                return package_url
            community = THUNDERSTORE_CONFIGS.get(game_key, {}).get("community")
            author = mod.get("author")
            name = mod.get("name")
            if community and author and name:
                return f"https://thunderstore.io/c/{community}/p/{author}/{name}/"
            return None
        if source in {"github", "website"}:
            for file_entry in mod.get("files", []):
                page_url = file_entry.get("page_url")
                if page_url:
                    return page_url
                file_url = file_entry.get("url")
                if not file_url:
                    continue
                if "/releases/download/" in file_url:
                    prefix, remainder = file_url.split("/releases/download/", 1)
                    tag = remainder.split("/", 1)[0]
                    return f"{prefix}/releases/tag/{tag}"
                return file_url
        return None

    def _icon_source_for_mod(self, mod):
        icon = mod.get("icon")
        if not icon:
            return None
        if icon.startswith(("http://", "https://")):
            return icon

        base_url = mod.get("__base_url")
        if base_url:
            return urljoin(base_url, icon)

        if os.path.isabs(icon) and os.path.exists(icon):
            return icon

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        for candidate in (
            os.path.join(repo_root, icon),
            os.path.join(_assets_dir(), icon),
        ):
            if os.path.exists(candidate):
                return candidate
        return None

    def _load_mod_icon(self, mod, label, size=40):
        source = self._icon_source_for_mod(mod)
        if not source:
            def _clear(lbl=label):
                try:
                    lbl._moxi_icon_request = None
                    lbl.configure(image=None, text="")
                    lbl.image = None
                except Exception:
                    pass
            label.after(0, _clear)
            return

        cache_key = (source, size)
        label._moxi_icon_request = cache_key

        def _clear(lbl=label, expected=cache_key):
            try:
                if getattr(lbl, "_moxi_icon_request", None) != expected:
                    return
                lbl.configure(image=None, text="")
                lbl.image = None
            except Exception:
                pass

        def _apply_cached(lbl=label, expected=cache_key):
            photo = self._mod_icon_cache.get(expected)
            if photo is None:
                return False
            try:
                if getattr(lbl, "_moxi_icon_request", None) != expected:
                    return True
                lbl.configure(image=photo, text="")
                lbl.image = photo
                return True
            except Exception:
                return True

        if _apply_cached():
            return

        label.after(0, _clear)

        with self._mod_icon_lock:
            if cache_key in self._mod_icon_loading:
                try:
                    label.after(150, _apply_cached)
                except Exception:
                    pass
                return
            self._mod_icon_loading.add(cache_key)

        def _fetch_icon(expected=cache_key):
            img = None
            with self._mod_icon_sem:
                try:
                    if source.startswith(("http://", "https://")):
                        r = requests.get(source, timeout=8)
                        r.raise_for_status()
                        img = Image.open(io.BytesIO(r.content))
                    else:
                        img = Image.open(source)
                    img = img.resize((size, size), Image.LANCZOS)
                except Exception:
                    img = None

            def _finish(img=img):
                with self._mod_icon_lock:
                    self._mod_icon_loading.discard(expected)

                if img is None:
                    _clear()
                    return

                try:
                    photo = ImageTk.PhotoImage(img)
                    self._mod_icon_cache[expected] = photo
                except Exception:
                    _clear()
                    return

                _apply_cached()

            try:
                self.after(0, _finish)
            except Exception:
                with self._mod_icon_lock:
                    self._mod_icon_loading.discard(expected)

        threading.Thread(target=_fetch_icon, daemon=True).start()

    def _load_logo(self):
        assets = _assets_dir()
        for name in ("MoxiLogo.png", "MoxiLogo.ico", "logo.png", "logo.ico"):
            path = os.path.join(assets, name)
            if os.path.exists(path):
                try:
                    img = Image.open(path).resize((30, 30), Image.LANCZOS)
                    self._logo_img = ImageTk.PhotoImage(img)
                except Exception:
                    pass
                break

    def _set_window_icon(self):
        assets = _assets_dir()
        for name in ("MoxiLogo.ico", "logo.ico", "blank.ico"):
            path = os.path.join(assets, name)
            if os.path.exists(path):
                try:
                    self.iconbitmap(path)
                except Exception:
                    pass
                return

    def _apply_titlebar_color(self):
        try:
            from ctypes import windll, byref, c_int, sizeof
            DWMWA_CAPTION_COLOR = 35
            hwnd  = windll.user32.GetParent(self.winfo_id())
            color = c_int(0x00111111)
            windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, byref(color), sizeof(color))
        except Exception:
            pass

    def _check_app_update_startup(self):
        try:
            tag, changelog, dl_url = self._mod_manager.check_for_app_update()
            from packaging.version import Version
            if Version(tag) > Version(MOXI_VERSION):
                self._pending_update = {"version": tag, "changelog": changelog, "dl_url": dl_url}
                self.after(0, self._show_update_banner)
        except Exception:
            pass

    def _show_update_banner(self):
        if not hasattr(self, "_update_banner_shown"):
            self._update_banner_shown = False
        if self._update_banner_shown or not self._pending_update:
            return
        self._update_banner_shown = True
        u = self._pending_update

        banner = ctk.CTkFrame(self, fg_color="#0a1a0a", height=38, corner_radius=0)
        banner.pack(side="top", fill="x", before=self._content)
        banner.pack_propagate(False)

        ctk.CTkLabel(
            banner,
            text=f"Moxi v{u['version']} is available.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#44cc88", anchor="w"
        ).pack(side="left", padx=14)

        def start_update():
            banner.destroy()
            self._show_page("settings")
            self.after(100, self._trigger_settings_update)

        ctk.CTkButton(
            banner, text="Update Now",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#1a4a1a", hover_color="#226622",
            text_color="#44cc88", corner_radius=4,
            border_width=0, width=90, height=26,
            command=start_update
        ).pack(side="right", padx=(0, 10))

        def dismiss():
            banner.destroy()

        ctk.CTkButton(
            banner, text="Dismiss",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="transparent", hover_color="#1a2a1a",
            text_color="#666666", corner_radius=4,
            border_width=0, width=70, height=26,
            command=dismiss
        ).pack(side="right", padx=(0, 4))

    def _trigger_settings_update(self):
        pass

    def _do_download_update(self, version, changelog, dl_url, progress_bar, btn, status):
        import webbrowser
        webbrowser.open(f"https://github.com/{MOXI_REPO}/releases/latest")

    def _check_post_update(self):
        data = self._mod_manager.read_and_clear_updated_flag()
        if data:
            self._show_changelog_overlay(data["version"], data["changelog"])

    def _show_changelog_overlay(self, version, changelog):
        overlay = ctk.CTkFrame(self, fg_color="#000000", corner_radius=0)
        overlay.place(x=0, y=0, relwidth=1, relheight=1)
        overlay.configure(fg_color="#000000")
        overlay.tkraise()

        try:
            overlay.configure(fg_color="#11111188")
        except Exception:
            pass

        card = ctk.CTkFrame(overlay, fg_color="#1a1a1a", corner_radius=12, width=540, height=420)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        ctk.CTkLabel(
            card,
            text=f"Updated to v{version}",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=ACCENT
        ).pack(pady=(28, 4))

        ctk.CTkLabel(
            card,
            text="Here's what's new:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_DIM
        ).pack(pady=(0, 10))

        log_box = ctk.CTkScrollableFrame(card, fg_color="#111111", corner_radius=8, height=240)
        log_box.pack(fill="x", padx=24)

        ctk.CTkLabel(
            log_box,
            text=changelog if changelog else "No changelog provided.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_ON,
            wraplength=460, justify="left", anchor="w"
        ).pack(anchor="w", padx=10, pady=10)

        ctk.CTkButton(
            card, text="Let's go",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=ACCENT, hover_color="#cc0040",
            text_color="#ffffff", corner_radius=8,
            width=140, height=36,
            command=overlay.destroy
        ).pack(pady=(18, 0))

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=NAV_BG, height=52, corner_radius=0)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", padx=(16, 0))

        if self._logo_img:
            tk.Label(
                left, image=self._logo_img,
                bg=NAV_BG, bd=0, highlightthickness=0
            ).pack(side="left", pady=11)

        ctk.CTkLabel(
            left, text="Moxi",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=ACCENT
        ).pack(side="left", padx=(8, 0))

        nav_frame = ctk.CTkFrame(bar, fg_color="transparent")
        nav_frame.pack(side="right", padx=18)

        self._nav_buttons = {}
        for label, key in [("Dashboard", "dashboard"), ("Mod Database", "mod_database"), ("Settings", "settings")]:
            btn = ctk.CTkButton(
                nav_frame, text=label,
                font=ctk.CTkFont(family="Segoe UI", size=13),
                fg_color="transparent",
                text_color=TEXT_DIM,
                hover_color="#1a1a1a",
                corner_radius=6,
                border_width=0,
                width=115, height=34,
                command=lambda k=key: self._show_page(k)
            )
            btn.pack(side="left", padx=3)
            self._nav_buttons[key] = btn
            _glow_on_hover(btn, targets=[btn], is_btn=True)
        self._refresh_nav_state()

    def _build_content_area(self):
        self._content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._content.pack(fill="both", expand=True)
        self._build_footer()

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color=NAV_BG, height=36, corner_radius=0)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)

        left_links = ctk.CTkFrame(footer, fg_color="transparent")
        left_links.pack(side="left", padx=14)

        right_links = ctk.CTkFrame(footer, fg_color="transparent")
        right_links.pack(side="right", padx=14)

        community_links = [
            ("support", None),
            ("issue", "https://github.com/KerbalMissile/Moxi/issues"),
            ("pr", "https://github.com/KerbalMissile/Moxi/pulls"),
            ("dev_info", None),
        ]

        links = [
            ("website",  "https://kerbalmissile.github.io/MoxiWebsite/"),
            ("github",   "https://github.com/KerbalMissile/Moxi"),
            ("discord",  "https://discord.com/invite/Y53vwvQRDc"),
        ]

        for kind, url in community_links:
            if kind == "support":
                self._make_nav_link(left_links, "Support Moxi <3", lambda: self._show_page("support_moxi"))
            elif kind == "dev_info":
                self._make_nav_link(left_links, "Dev Info", lambda: self._show_page("dev_info"))
            else:
                self._make_icon_btn(left_links, kind, url)

        for kind, url in links:
            self._make_icon_btn(right_links, kind, url)

    def _make_icon_btn(self, parent, kind, url):
        import webbrowser

        labels = {
            "website": "Website",
            "github": "GitHub",
            "discord": "Discord",
            "issue": "Report an Issue",
            "pr": "Submit a Pull Request",
        }

        lbl = tk.Label(
            parent,
            text=labels[kind],
            fg="#555555", bg=NAV_BG,
            font=("Segoe UI", 9),
            bd=0, highlightthickness=0,
            cursor="hand2"
        )
        lbl.pack(side="left", padx=8, pady=10)

        lbl.bind("<Enter>",    lambda e: lbl.configure(fg=ACCENT))
        lbl.bind("<Leave>",    lambda e: lbl.configure(fg="#555555"))
        lbl.bind("<Button-1>", lambda e: webbrowser.open(url))

    def _make_nav_link(self, parent, text, command):
        lbl = tk.Label(
            parent,
            text=text,
            fg="#555555", bg=NAV_BG,
            font=("Segoe UI", 9),
            bd=0, highlightthickness=0,
            cursor="hand2"
        )
        lbl.pack(side="left", padx=8, pady=10)

        lbl.bind("<Enter>", lambda e: lbl.configure(fg=ACCENT))
        lbl.bind("<Leave>", lambda e: lbl.configure(fg="#555555"))
        lbl.bind("<Button-1>", lambda e: command())

    def _show_page(self, key):
        if self._stats_consent_required and key != "stats_consent":
            key = "stats_consent"

        if self._active_frame:
            self._active_frame.destroy()
            self._active_frame   = None
            self._detected_inner = None

        self._current_page = key

        for k, btn in self._nav_buttons.items():
            btn.configure(text_color=ACCENT if k == key else TEXT_DIM)

        frame = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        frame.pack(fill="both", expand=True)
        self._active_frame = frame

        {
            "dashboard":    self._build_dashboard,
            "mod_database": self._build_mod_database,
            "settings":     self._build_settings,
            "support_moxi": self._build_support_moxi,
            "dev_info":     self._build_dev_info,
            "stats_consent": self._build_stats_consent,
        }[key](frame)

        # Scroll all CTkScrollableFrames on this page back to the top
        def _scroll_to_top():
            try:
                for w in frame.winfo_children():
                    if isinstance(w, ctk.CTkScrollableFrame):
                        w._parent_canvas.yview_moveto(0)
            except Exception:
                pass
        self.after(0, _scroll_to_top)

    def _refresh_nav_state(self):
        state = "disabled" if getattr(self, "_stats_consent_required", False) else "normal"
        for btn in getattr(self, "_nav_buttons", {}).values():
            try:
                btn.configure(state=state)
            except Exception:
                pass

    def _on_app_close(self):
        try:
            self._stats.close_session()
        except Exception:
            pass
        self.destroy()

    def _do_fetch_index(self, on_done=None):
        if self._index_loading:
            return
        self._index_loading = True
        try:
            self._mod_index = self._mod_manager.fetch_mod_index()
            try:
                games = self._mod_index.get("games", {})
                counts = {key: len(value.get("mods", [])) for key, value in games.items()}
                print(f"[Moxi Mods] mod index loaded games={len(games)} counts={counts}", flush=True)
            except Exception:
                pass
        except Exception as exc:
            self._mod_index = {}
            try:
                print(f"[Moxi Mods] mod index fetch failed: {exc!r}", flush=True)
            except Exception:
                pass
        finally:
            self._index_loading = False
        if on_done:
            try:
                on_done()
            except Exception:
                pass

    def _do_fetch_game_index(self):
        try:
            self._game_index = self._mod_manager.fetch_game_index()
            try:
                print(f"[Moxi Mods] game index loaded entries={len(self._game_index.get('games', []))}", flush=True)
            except Exception:
                pass
        except Exception as exc:
            self._game_index = {}
            try:
                print(f"[Moxi Mods] game index fetch failed: {exc!r}", flush=True)
            except Exception:
                pass
        if self._active_frame:
            self._active_frame.after(0, self._refresh_coming_soon)

    def _refresh_coming_soon(self):
        if hasattr(self, "_coming_soon_row") and self._coming_soon_row is not None:
            try:
                for w in self._coming_soon_row.winfo_children():
                    w.destroy()
                coming = self._get_coming_soon_games()
                if coming:
                    for g in coming:
                        self._make_game_card(self._coming_soon_row, g)
                else:
                    import customtkinter as ctk
                    ctk.CTkLabel(
                        self._coming_soon_row, text="Nothing here yet.",
                        font=ctk.CTkFont(family="Segoe UI", size=12),
                        text_color=TEXT_DIM
                    ).pack(side="left", padx=16, pady=30)
            except Exception:
                pass

    def _get_coming_soon_games(self):
        coming = []
        for entry in self._game_index.get("coming_soon", []):
            coming.append({
                "appid":       entry.get("appid", "0"),
                "name":        entry.get("name", "Unknown"),
                "supported":   False,
                "game_key":    entry.get("game_key", ""),
                "coming_date": entry.get("coming_date", ""),
            })
        return coming

    def _build_dashboard(self, parent):
        body = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        body.pack(fill="both", expand=True)

        sidebar = ctk.CTkFrame(body, fg_color=NAV_BG, corner_radius=0, width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        self._build_sidebar(sidebar)

        divider = ctk.CTkFrame(body, fg_color="#1e1e1e", corner_radius=0, width=1)
        divider.pack(side="left", fill="y")

        scroll = ctk.CTkScrollableFrame(body, fg_color=BG, corner_radius=0)
        scroll.pack(side="left", fill="both", expand=True)

        self._recently_played_row = self._build_section(scroll, "Recently Played", self._recently_played if self._recently_played else [])

        newly = [
            {"appid": appid, "name": v["name"], "supported": v["supported"], "game_key": v["game_key"]}
            for appid, v in SUPPORTED_GAMES.items()
            if v["game_key"] in NEWLY_ADDED
        ]
        newly.sort(key=lambda g: g["name"].lower())
        self._build_section(scroll, "Newly Added to Moxi", newly)

        coming = self._get_coming_soon_games()
        self._coming_soon_row = self._build_section(scroll, "Coming Soon", coming)

        self._detected_inner = self._build_section(scroll, "Detected Supported Games", None)
        self._populate_detected_cards()

    def _build_sidebar(self, parent):
        def section_label(text):
            ctk.CTkLabel(
                parent, text=text.upper(),
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                text_color="#444444", anchor="w"
            ).pack(anchor="w", padx=16, pady=(16, 4))

        def divider():
            ctk.CTkFrame(parent, fg_color="#1e1e1e", height=1, corner_radius=0).pack(fill="x", padx=12, pady=(0, 8))

        section_label("Stats")
        divider()

        total_installed = sum(
            len(v) for v in self._mod_manager.installed.values()
        )

        stat_rows = {}
        for label in ("Mods Installed", "Games Detected"):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(
                row, text=label,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=TEXT_DIM, anchor="w"
            ).pack(side="left")
            val_lbl = ctk.CTkLabel(
                row, text="...",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=TEXT_ON, anchor="e"
            )
            val_lbl.pack(side="right")
            stat_rows[label] = val_lbl

        def _update_stats():
            try:
                stat_rows["Mods Installed"].configure(
                    text=str(sum(len(v) for v in self._mod_manager.installed.values()))
                )
                stat_rows["Games Detected"].configure(
                    text=str(len(self._detected))
                )
            except Exception:
                pass

        _update_stats()
        self._sidebar_update_stats = _update_stats

        if self._mod_manager.installed:
            section_label("Mods Per Game")
            divider()
            for game_key, mods in self._mod_manager.installed.items():
                if not mods:
                    continue
                game_name = GAME_KEY_TO_NAME.get(game_key, game_key.replace("_", " ").title())
                row = ctk.CTkFrame(parent, fg_color="transparent")
                row.pack(fill="x", padx=16, pady=2)
                ctk.CTkLabel(
                    row, text=game_name,
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    text_color=TEXT_DIM, anchor="w",
                    wraplength=140
                ).pack(side="left")
                ctk.CTkLabel(
                    row, text=str(len(mods)),
                    font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                    text_color=ACCENT, anchor="e"
                ).pack(side="right")

        section_label("News")
        divider()

        news_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent", corner_radius=0)
        news_frame.pack(fill="both", expand=True, padx=0)

        loading_lbl = ctk.CTkLabel(
            news_frame, text="Loading...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#444444"
        )
        loading_lbl.pack(pady=12)

        def _load_news():
            if self._news_cache is not None:
                _render_news(self._news_cache)
                return
            try:
                r = requests.get(
                    f"https://api.github.com/repos/{MOXI_REPO}/releases",
                    timeout=8
                )
                r.raise_for_status()
                self._news_cache = r.json()
                news_frame.after(0, lambda: _render_news(self._news_cache))
            except Exception:
                news_frame.after(0, lambda: loading_lbl.configure(text="Failed to load news."))

        def _render_news(releases):
            try:
                loading_lbl.destroy()
            except Exception:
                pass
            for release in releases[:5]:
                tag  = release.get("tag_name", "")
                body = release.get("body", "No changelog provided.") or "No changelog provided."
                card = ctk.CTkFrame(news_frame, fg_color="#141414", corner_radius=6)
                card.pack(fill="x", padx=10, pady=(0, 8))
                ctk.CTkLabel(
                    card, text=f"Moxi {tag}",
                    font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                    text_color=ACCENT, anchor="w"
                ).pack(anchor="w", padx=10, pady=(8, 2))
                ctk.CTkLabel(
                    card, text=body,
                    font=ctk.CTkFont(family="Segoe UI", size=10),
                    text_color=TEXT_DIM, anchor="w",
                    wraplength=170, justify="left"
                ).pack(anchor="w", padx=10, pady=(0, 8))

        threading.Thread(target=_load_news, daemon=True).start()

    def _build_section(self, parent, title, games):
        wrapper = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        wrapper.pack(fill="x", pady=(28, 0), padx=28)

        ctk.CTkLabel(
            wrapper, text=title,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=TEXT_ON, anchor="w"
        ).pack(anchor="w", pady=(0, 8))

        ctk.CTkFrame(wrapper, fg_color="#252525", height=1, corner_radius=0).pack(fill="x", pady=(0, 14))

        row = ctk.CTkScrollableFrame(
            wrapper, fg_color=BG, corner_radius=0,
            orientation="horizontal", height=CARD_H + 16
        )
        row.pack(fill="x")

        if games is not None:
            if games:
                for g in games:
                    self._make_game_card(row, g)
            else:
                ctk.CTkLabel(
                    row, text="Nothing here yet.",
                    font=ctk.CTkFont(family="Segoe UI", size=12),
                    text_color=TEXT_DIM
                ).pack(side="left", padx=16, pady=30)

        return row

    def _populate_detected_cards(self):
        if self._detected_inner is None:
            return
        for w in self._detected_inner.winfo_children():
            w.destroy()
        if not self._detected:
            ctk.CTkLabel(
                self._detected_inner,
                text="Scanning for games...",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=TEXT_DIM
            ).pack(side="left", padx=16, pady=30)
        else:
            self._render_detected_cards()

    def _render_detected_cards(self):
        if self._detected_inner is None:
            return
        for w in self._detected_inner.winfo_children():
            w.destroy()
        if not self._detected:
            ctk.CTkLabel(
                self._detected_inner,
                text="No supported games found on this machine.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=TEXT_DIM
            ).pack(side="left", padx=16, pady=30)
            return
        for game in sorted(self._detected, key=lambda g: g.get("name", "").lower()):
            self._make_game_card(self._detected_inner, game)

    def _make_game_card(self, parent, game):
        import webbrowser
        appid     = game["appid"]
        name      = game["name"]
        game_key  = game.get("game_key", "")
        live_info = SUPPORTED_GAMES.get(appid, {})
        supported = live_info.get("supported", game.get("supported", False))
        detected  = self._detected_map.get(game_key)
        install_dir = detected.get("install_dir") if detected else None
        has_install_dir = bool(install_dir and os.path.isdir(install_dir))

        card = ctk.CTkFrame(
            parent, fg_color=CARD_BG, corner_radius=10,
            width=DASH_CARD_W, height=CARD_H, border_width=0
        )
        card.pack(side="left", padx=(0, 14), pady=4)
        card.pack_propagate(False)

        art_frame = ctk.CTkFrame(card, fg_color="#1e1e1e", corner_radius=8, width=ART_W, height=ART_H)
        art_frame.pack()
        art_frame.pack_propagate(False)

        art_label = ctk.CTkLabel(
            art_frame, text="Loading...",
            text_color=TEXT_DIM,
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        art_label.place(relx=0.5, rely=0.5, anchor="center")

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="x", padx=10, pady=(6, 6))

        name_row = ctk.CTkFrame(info, fg_color="transparent")
        name_row.pack(fill="x")

        name_lbl = ctk.CTkLabel(
            name_row, text=name,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=TEXT_ON, wraplength=260, anchor="w", justify="left"
        )
        name_lbl.pack(side="left", anchor="w")

        bottom = ctk.CTkFrame(info, fg_color="transparent")
        bottom.pack(fill="x", pady=(4, 0))

        game_info   = SUPPORTED_GAMES.get(appid, {})
        coming_date = game.get("coming_date") or game_info.get("coming_date")

        if supported:
            badge_text  = "Supported"
            badge_color = ACCENT
        elif coming_date:
            badge_text  = f"Coming {coming_date}"
            badge_color = "#666666"
        else:
            badge_text  = "Coming Soon"
            badge_color = "#444444"

        badge_lbl = ctk.CTkLabel(
            bottom,
            text=badge_text,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=badge_color, anchor="w"
        )
        badge_lbl.pack(side="left", anchor="center")

        play_btn = ctk.CTkButton(
            bottom, text="Play",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#2a2a2a",
            hover_color="#333333",
            text_color=TEXT_ON,
            corner_radius=4,
            border_width=0,
            width=48, height=24,
            command=lambda: self._launch_game(game)
        )
        play_btn.pack(side="right", anchor="center")
        _glow_on_hover(play_btn, targets=[play_btn], is_btn=True)

        if has_install_dir:
            open_folder_btn = ctk.CTkButton(
                bottom, text="Open Folder",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color="#2a2a2a",
                hover_color="#333333",
                text_color=TEXT_ON,
                corner_radius=4,
                border_width=0,
                width=90, height=24,
                command=lambda path=install_dir: os.startfile(path)
            )
            open_folder_btn.pack(side="right", anchor="center", padx=(0, 6))
            _glow_on_hover(open_folder_btn, targets=[open_folder_btn], is_btn=True)

        def on_card_click(e):
            if isinstance(getattr(e, "widget", None), ctk.CTkButton):
                return
            self._selected_game = name
            g = {"appid": appid, "name": name, "game_key": game_key, "supported": supported}
            self._show_game_mods(g)

        for widget in (card, art_frame, art_label, info, name_row, name_lbl, bottom, badge_lbl):
            widget.bind("<Button-1>", on_card_click)

        _glow_on_hover(card, targets=[card, art_frame, art_label, info, bottom], bg_normal=CARD_BG, bg_hover="#222222")
        self._queue_art_load(appid, art_label)

    def _launch_game(self, game):
        import webbrowser
        game_key = game.get("game_key", "")
        if game_key not in self._detected_map:
            return
        webbrowser.open(f"steam://rungameid/{game['appid']}")
        self._record_play(game)

    def _all_descendants(self, widget):
        result = []
        try:
            for child in widget.winfo_children():
                result.append(child)
                result.extend(self._all_descendants(child))
        except Exception:
            pass
        return result

    def _load_art(self, appid, label, width=ART_W, height=ART_H):
        cache_key = (appid, width, height)
        img = self._art_cache.get(cache_key)
        if img is None:
            img = self._fetch_cdn_art(appid, width, height)
        if img is None:
            def _set_no_icon(lbl=label):
                try:
                    lbl.configure(text="No Icon Found", text_color=TEXT_DIM)
                except Exception:
                    pass
            label.after(0, _set_no_icon)
            return
        self._art_cache[cache_key] = img
        # PhotoImage must be created on the main thread to avoid Tk threading issues
        def apply(img=img, lbl=label, key=cache_key):
            try:
                photo = self._art_photo_cache.get(key)
                if photo is None:
                    photo = ImageTk.PhotoImage(img)
                    self._art_photo_cache[key] = photo
                lbl.configure(image=photo, text="")
                lbl.image = photo
            except Exception:
                pass
        try:
            label.after(0, apply)
        except Exception:
            pass

    def _ensure_art_loader(self):
        with self._art_loader_lock:
            if self._art_loader_started:
                return
            self._art_loader_started = True
        threading.Thread(target=self._art_loader_loop, daemon=True, name="moxi-art-loader").start()

    def _queue_art_load(self, appid, label, width=ART_W, height=ART_H):
        request_key = (appid, width, height)
        try:
            label._moxi_art_request = request_key
        except Exception:
            pass
        if not self._is_staggered_loading_enabled():
            def _throttled_load(appid=appid, label=label, width=width, height=height):
                with self._art_thread_sem:
                    self._load_art(appid, label, width, height)
            threading.Thread(target=_throttled_load, daemon=True).start()
            return
        self._art_load_queue.put((appid, label, width, height, request_key))

    def _art_loader_loop(self):
        while True:
            appid, label, width, height, request_key = self._art_load_queue.get()
            try:
                if getattr(label, "_moxi_art_request", None) != request_key:
                    continue
            except Exception:
                continue
            self._load_art(appid, label, width, height)

    def _fetch_cdn_art(self, appid, width=ART_W, height=ART_H):
        url = CUSTOM_ART_URLS.get(str(appid)) or f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/header.jpg"
        try:
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content))
                fitted = ImageOps.contain(img, (width, height), Image.LANCZOS)
                canvas = Image.new("RGBA", (width, height), "#1e1e1e")
                x = (width - fitted.width) // 2
                y = (height - fitted.height) // 2
                canvas.paste(fitted, (x, y))
                return canvas
        except Exception:
            pass
        return None

    def _scan_steam(self):
        scanner            = SteamScanner(SUPPORTED_GAMES)
        results            = scanner.scan()
        self._detected     = results
        self._detected_map = {g["game_key"]: g for g in results}
        if self._active_frame:
            self._active_frame.after(0, self._render_detected_cards)
            if hasattr(self, "_sidebar_update_stats"):
                self._active_frame.after(0, self._sidebar_update_stats)

    def _build_mod_database(self, parent):
        """Game-grid landing page for the Mod Database."""
        def _format_count_text(total_count, installed_count, loading=False):
            if loading:
                return "Loading..."
            return f"{total_count} mods  ·  {installed_count} installed"

        scroll = ctk.CTkScrollableFrame(parent, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True)

        header = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=0)
        header.pack(fill="x", padx=28, pady=(24, 0))

        ctk.CTkLabel(
            header, text="Mod Database",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=TEXT_ON, anchor="w"
        ).pack(side="left")

        ctk.CTkFrame(scroll, fg_color="#252525", height=1, corner_radius=0).pack(fill="x", padx=28, pady=(10, 20))

        grid_frame = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=0)
        grid_frame.pack(fill="x", padx=28)

        gap = 14
        min_card_w = 360
        art_ratio = 215 / 460
        available_width = max(max(parent.winfo_width(), self.winfo_width()) - 90, min_card_w * 3)
        COLS = max(3, min(4, available_width // min_card_w))
        card_w = max(min_card_w, (available_width - gap * (COLS - 1)) // COLS)
        art_h = max(140, round(card_w * art_ratio))

        all_games = [
            {"appid": appid, "name": v["name"], "game_key": v["game_key"], "supported": v["supported"]}
            for appid, v in SUPPORTED_GAMES.items()
            if v["supported"]
        ]
        all_games.sort(key=lambda g: g["name"].lower())

        for i, game in enumerate(all_games):
            game_key  = game["game_key"]
            appid     = game["appid"]
            name      = game["name"]

            installed_count = len(self._mod_manager.installed.get(game_key, {}))
            curated_raw   = self._mod_index.get("games", {}).get(game_key, {}).get("mods", [])
            curated_ids   = {m.get("id") for m in curated_raw if m.get("id")}
            curated_count = len(curated_raw)
            ts_cached     = self._thunderstore_cache.get(game_key) if game_key in THUNDERSTORE_GAMES else []

            if game_key in THUNDERSTORE_GAMES and ts_cached is None:
                total_count = None
            else:
                blocked    = THUNDERSTORE_BLOCKLIST.get(game_key, set())
                ts_count   = len([
                    m for m in (ts_cached or [])
                    if m.get("id") not in curated_ids and m.get("id") not in blocked
                ])
                total_count = curated_count + ts_count

            col = i % COLS
            row = i // COLS

            card = ctk.CTkFrame(grid_frame, fg_color=CARD_BG, corner_radius=10, border_width=0)
            card.grid(row=row, column=col, padx=(0, gap), pady=(0, 14), sticky="nsew")
            grid_frame.columnconfigure(col, weight=1, uniform="moddb")

            art_frame = ctk.CTkFrame(card, fg_color="#1e1e1e", corner_radius=8, height=art_h)
            art_frame.pack(fill="x")
            art_frame.pack_propagate(False)

            art_label = ctk.CTkLabel(
                art_frame, text="Loading...",
                text_color=TEXT_DIM,
                font=ctk.CTkFont(family="Segoe UI", size=11)
            )
            art_label.place(relx=0.5, rely=0.5, anchor="center")

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(fill="x", padx=12, pady=(8, 10))

            ctk.CTkLabel(
                info, text=name,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=TEXT_ON, anchor="w"
            ).pack(anchor="w")

            count_row = ctk.CTkFrame(info, fg_color="transparent")
            count_row.pack(fill="x", pady=(4, 0))

            mod_count_lbl = ctk.CTkLabel(
                count_row,
                text=_format_count_text(total_count or 0, installed_count, loading=(total_count is None)),
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=TEXT_DIM, anchor="w"
            )
            mod_count_lbl.pack(side="left")

            if game_key in THUNDERSTORE_GAMES and ts_cached is None and game_key not in self._ts_loading:
                self._ts_loading.add(game_key)

                def _fetch_ts_count(gk=game_key, lbl=mod_count_lbl, installed=installed_count,
                                    curated=curated_count, curated_mod_ids=curated_ids):
                    fetch_failed = False
                    try:
                        pkgs = self._mod_manager.fetch_thunderstore_packages(gk)
                        self._thunderstore_cache[gk] = pkgs
                    except Exception:
                        fetch_failed = True
                    finally:
                        self._ts_loading.discard(gk)

                    if fetch_failed:
                        if self._active_frame and self._current_page == "mod_database":
                            lbl.after(0, lambda: lbl.configure(text=_format_count_text(curated, installed)))
                        return

                    blocked = THUNDERSTORE_BLOCKLIST.get(gk, set())
                    ts_count_done = len([
                        m for m in self._thunderstore_cache.get(gk, [])
                        if m.get("id") not in curated_mod_ids and m.get("id") not in blocked
                    ])
                    total_done = curated + ts_count_done

                    if self._active_frame and self._current_page == "mod_database":
                        lbl.after(0, lambda total=total_done, inst=installed: lbl.configure(
                            text=_format_count_text(total, inst)
                        ))

                threading.Thread(target=_fetch_ts_count, daemon=True).start()
            def _open(g=game, lbl=mod_count_lbl):
                self._selected_game = g["name"]
                self._show_game_mods(g)

            for w in [card, art_frame, art_label, info, count_row, mod_count_lbl]:
                try:
                    w.bind("<Button-1>", lambda e, fn=_open: fn())
                except Exception:
                    pass

            _glow_on_hover(card, targets=[card, art_frame, art_label, info, count_row, mod_count_lbl],
                           bg_normal=CARD_BG, bg_hover="#222222")

            self._queue_art_load(appid, art_label, card_w, art_h)

    def _show_game_mods(self, game):
        """Replace the content area with the per-game mod view."""
        game_key = game["game_key"]
        if game_key == "valheim":
            self._mod_manager.invalidate_thunderstore_cache(game_key)
            self._thunderstore_cache.pop(game_key, None)

        if self._active_frame:
            self._active_frame.destroy()
            self._active_frame   = None
            self._detected_inner = None

        self._current_page = "game_mods"

        frame = ctk.CTkFrame(self._content, fg_color=BG, corner_radius=0)
        frame.pack(fill="both", expand=True)
        self._active_frame = frame

        self._build_game_mod_view(frame, game)

    def _build_game_mod_view(self, parent, game):
        """Per-game view with the mod list."""
        name = game["name"]

        # ── Top bar ──────────────────────────────────────────────────────────
        topbar = ctk.CTkFrame(parent, fg_color=NAV_BG, height=54, corner_radius=0)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        back_btn = ctk.CTkButton(
            topbar, text="← Back",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent", hover_color="#1a1a1a",
            text_color=TEXT_DIM, corner_radius=6,
            border_width=0, width=70, height=32,
            command=lambda: self._show_page("mod_database")
        )
        back_btn.pack(side="left", padx=(12, 0), pady=11)
        _glow_on_hover(back_btn, targets=[back_btn], is_btn=True)

        ctk.CTkLabel(
            topbar, text=name,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=TEXT_ON
        ).pack(side="left", padx=(12, 0))

        ctk.CTkFrame(parent, fg_color="#1e1e1e", height=1, corner_radius=0).pack(fill="x")

        content = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        content.pack(fill="both", expand=True)
        self._build_mod_list(content, game)

    def _build_mod_list(self, parent, game):
        """The original mod list UI, adapted to sit inside the per-game view."""
        PAGE_SIZE = 20
        game_key  = game["game_key"]
        modpacks_enabled = False
        modpack_state = {
            "packs": [],
            "active_pack_id": None,
            "refresh_mods": lambda: None,
            "refresh_modpacks": lambda: None,
            "switch_tab": lambda tab: None,
        }

        def _refresh_shared_modpacks():
            return []

        def _get_active_pack():
            return None

        def _pack_mod_ids(pack=None):
            return set()

        def _installed_entry(mod_id):
            return self._mod_manager.installed.get(game_key, {}).get(mod_id)

        def _is_visible_installed(mod_id):
            return _installed_entry(mod_id) is not None

        def _refresh_pack_controls():
            return

        state = {
            "page": 0, "all_mods": [], "filtered_mods": None, "game_key": game_key,
            "search_after": None, "suppress_search": False,
            "search_index": [], "search_gen": 0, "row_pool": [],
            "updates_available": {},
            "config_paths": {},
        }

        # ── Action bar ───────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(parent, fg_color=NAV_BG, height=46, corner_radius=0)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        status_lbl = ctk.CTkLabel(
            toolbar, text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_DIM
        )
        status_lbl.pack(side="left", padx=16)

        detected_game = self._detected_map.get(game_key)
        detected_install_dir = detected_game.get("install_dir") if detected_game else None
        mods_folder_path = None
        if detected_install_dir and os.path.isdir(detected_install_dir):
            mods_folder_path = os.path.join(detected_install_dir, self._mod_manager.get_mod_dest(game_key))

        add_a_mod_btn = ctk.CTkButton(
            toolbar, text="Add A Mod",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#1e1e1e", hover_color="#2a2a2a",
            text_color=TEXT_DIM, corner_radius=6,
            border_width=0, width=100, height=30,
            command=lambda: __import__("webbrowser").open("https://github.com/KerbalMissile/Moxi/blob/main/README.md#for-mod-authors")
        )
        add_a_mod_btn.pack(side="right", padx=(0, 8), pady=8)
        _glow_on_hover(add_a_mod_btn, targets=[add_a_mod_btn], is_btn=True)

        if mods_folder_path:
            open_mods_folder_btn = ctk.CTkButton(
                toolbar, text="Open Mods Folder",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color="#1e1e1e", hover_color="#2a2a2a",
                text_color=TEXT_DIM, corner_radius=6,
                border_width=0, width=130, height=30,
                command=lambda path=mods_folder_path: os.startfile(path)
            )
            open_mods_folder_btn.pack(side="right", padx=(0, 8), pady=8)
            _glow_on_hover(open_mods_folder_btn, targets=[open_mods_folder_btn], is_btn=True)

        import_file_btn = ctk.CTkButton(
            toolbar, text="Import File",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#1e1e1e", hover_color="#2a2a2a",
            text_color=TEXT_DIM, corner_radius=6,
            border_width=0, width=100, height=30
        )
        import_file_btn.pack(side="right", padx=(0, 8), pady=8)
        _glow_on_hover(import_file_btn, targets=[import_file_btn], is_btn=True)

        import_folder_btn = ctk.CTkButton(
            toolbar, text="Import Folder",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#1e1e1e", hover_color="#2a2a2a",
            text_color=TEXT_DIM, corner_radius=6,
            border_width=0, width=110, height=30
        )
        import_folder_btn.pack(side="right", padx=(0, 8), pady=8)
        _glow_on_hover(import_folder_btn, targets=[import_folder_btn], is_btn=True)

        refresh_btn = ctk.CTkButton(
            toolbar, text="Refresh",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#1e1e1e", hover_color="#2a2a2a",
            text_color=TEXT_DIM, corner_radius=6,
            border_width=0, width=80, height=30,
            command=lambda: _do_refresh()
        )
        refresh_btn.pack(side="right", padx=(0, 16), pady=8)
        _glow_on_hover(refresh_btn, targets=[refresh_btn], is_btn=True)

        update_all_btn = ctk.CTkButton(
            toolbar, text="Update All",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=ACCENT, hover_color="#cc0040",
            text_color="#ffffff", corner_radius=6,
            border_width=0, width=100, height=30,
            command=lambda: _do_update_all()
        )
        _glow_on_hover(update_all_btn, targets=[update_all_btn], is_btn=True)

        sort_var = ctk.StringVar(value="Alphabetical")
        ctk.CTkOptionMenu(
            toolbar,
            variable=sort_var,
            values=["Alphabetical", "Author Name", "Installed First", "Curated First"],
            fg_color="#1e1e1e",
            button_color="#2a2a2a",
            button_hover_color="#333333",
            dropdown_fg_color="#1a1a1a",
            dropdown_hover_color="#252525",
            text_color=TEXT_ON,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            width=160,
            command=lambda val: _apply_sort()
        ).pack(side="right", padx=(0, 8), pady=8)

        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            toolbar, textvariable=search_var,
            placeholder_text="Search mods...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#1e1e1e", border_color="#2a2a2a",
            text_color=TEXT_ON, width=200, height=30
        )
        search_entry.pack(side="left", padx=(0, 0), pady=8)

        ctk.CTkFrame(parent, fg_color="#1e1e1e", height=1, corner_radius=0).pack(fill="x")

        notif_bar = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0, height=0)
        notif_bar.pack(fill="x")
        notif_bar.pack_propagate(False)

        config_panel = ctk.CTkFrame(parent, fg_color="#141414", corner_radius=0, height=0)
        config_panel.pack(fill="x")
        config_panel.pack_propagate(False)

        config_state = {"mod_id": None, "path": None}

        config_header = ctk.CTkFrame(config_panel, fg_color="#141414", corner_radius=0)
        config_title = ctk.CTkLabel(
            config_header, text="",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_ON, anchor="w"
        )
        config_title.pack(side="left", padx=(16, 8), pady=10)

        config_path_lbl = ctk.CTkLabel(
            config_header, text="",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=TEXT_DIM, anchor="w"
        )
        config_path_lbl.pack(side="left", padx=(0, 8), pady=10)

        config_status_lbl = ctk.CTkLabel(
            config_header, text="",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=TEXT_DIM, anchor="w"
        )
        config_status_lbl.pack(side="left", padx=(0, 8), pady=10)

        config_close_btn = ctk.CTkButton(
            config_header, text="Close",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1e1e1e", hover_color="#2a2a2a",
            text_color=TEXT_DIM, corner_radius=6,
            border_width=0, width=70, height=28
        )
        config_close_btn.pack(side="right", padx=(0, 8), pady=8)
        _glow_on_hover(config_close_btn, targets=[config_close_btn], is_btn=True)

        config_save_btn = ctk.CTkButton(
            config_header, text="Save",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=ACCENT, hover_color="#cc0040",
            text_color="#ffffff", corner_radius=6,
            border_width=0, width=70, height=28
        )
        config_save_btn.pack(side="right", padx=(0, 8), pady=8)
        _glow_on_hover(config_save_btn, targets=[config_save_btn], is_btn=True)

        config_reload_btn = ctk.CTkButton(
            config_header, text="Reload",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1e1e1e", hover_color="#2a2a2a",
            text_color=TEXT_DIM, corner_radius=6,
            border_width=0, width=80, height=28
        )
        config_reload_btn.pack(side="right", padx=(0, 8), pady=8)
        _glow_on_hover(config_reload_btn, targets=[config_reload_btn], is_btn=True)

        config_editor = ctk.CTkTextbox(
            config_panel,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#101010",
            text_color=TEXT_ON,
            border_color="#1e1e1e",
            height=240
        )

        def _hide_config_panel():
            config_state["mod_id"] = None
            config_state["path"] = None
            config_status_lbl.configure(text="")
            try:
                config_header.pack_forget()
                config_editor.pack_forget()
            except Exception:
                pass
            config_panel.configure(height=0)

        def _load_config_into_panel(mod, path):
            config_state["mod_id"] = mod["id"]
            config_state["path"] = path
            try:
                text = self._mod_manager.read_text_file(path)
            except Exception:
                config_status_lbl.configure(text="Failed to load config", text_color="#cc4444")
                return

            config_title.configure(text=f"{mod['name']} Config")
            config_path_lbl.configure(text=path, text_color=TEXT_DIM)
            config_status_lbl.configure(text="", text_color=TEXT_DIM)
            config_panel.configure(height=320)
            config_header.pack(fill="x")
            config_editor.pack(fill="x", padx=16, pady=(0, 12))
            config_editor.delete("1.0", "end")
            config_editor.insert("1.0", text)

        def _reload_config_panel():
            path = config_state["path"]
            mod_id = config_state["mod_id"]
            if not path or not mod_id:
                return
            mod = next((m for m in state["all_mods"] if m["id"] == mod_id), None)
            if mod is not None:
                _load_config_into_panel(mod, path)

        def _save_config_panel():
            path = config_state["path"]
            if not path:
                return
            try:
                self._mod_manager.write_text_file(path, config_editor.get("1.0", "end-1c"))
                config_status_lbl.configure(text="Saved", text_color="#44cc88")
            except Exception:
                config_status_lbl.configure(text="Save failed", text_color="#cc4444")

        config_close_btn.configure(command=_hide_config_panel)
        config_reload_btn.configure(command=_reload_config_panel)
        config_save_btn.configure(command=_save_config_panel)

        list_container = ctk.CTkScrollableFrame(parent, fg_color=BG, corner_radius=0)
        list_container.pack(fill="both", expand=True)

        pager = ctk.CTkFrame(parent, fg_color=NAV_BG, height=40, corner_radius=0)
        pager.pack(fill="x", side="bottom")
        pager.pack_propagate(False)

        prev_btn = ctk.CTkButton(
            pager, text="< Prev",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent", hover_color="#1e1e1e",
            text_color=TEXT_DIM, corner_radius=4,
            border_width=0, width=70, height=28,
            command=lambda: _go_page(state["page"] - 1)
        )
        prev_btn.pack(side="left", padx=12, pady=6)
        _glow_on_hover(prev_btn, targets=[prev_btn], is_btn=True)

        page_lbl = ctk.CTkLabel(
            pager, text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_DIM
        )
        page_lbl.pack(side="left", padx=8)

        next_btn = ctk.CTkButton(
            pager, text="Next >",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent", hover_color="#1e1e1e",
            text_color=TEXT_DIM, corner_radius=4,
            border_width=0, width=70, height=28,
            command=lambda: _go_page(state["page"] + 1)
        )
        next_btn.pack(side="left", padx=0, pady=6)
        _glow_on_hover(next_btn, targets=[next_btn], is_btn=True)

        msg_lbl = ctk.CTkLabel(
            list_container, text="",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=TEXT_DIM
        )

        def _show_message(text):
            for r in state["row_pool"]:
                r["frame"].pack_forget()
            msg_lbl.configure(text=text)
            msg_lbl.pack(pady=60)

        def _hide_message():
            msg_lbl.pack_forget()

        def _build_row_pool():
            pool = []
            for _ in range(PAGE_SIZE):
                frame = ctk.CTkFrame(list_container, fg_color=CARD_BG, corner_radius=8, height=88)
                frame.pack_propagate(False)

                icon_wrap = ctk.CTkFrame(frame, fg_color="transparent", width=48, height=48)
                icon_wrap.pack_propagate(False)
                icon_lbl = ctk.CTkLabel(icon_wrap, text="")
                icon_lbl.place(relx=0.5, rely=0.5, anchor="center")

                left = ctk.CTkFrame(frame, fg_color="transparent")
                left.pack(side="left", fill="both", expand=True, padx=(16, 8), pady=10)

                top_line = ctk.CTkFrame(left, fg_color="transparent")
                top_line.pack(fill="x")

                name_lbl   = ctk.CTkLabel(top_line, text="", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=TEXT_ON, anchor="w")
                name_lbl.pack(side="left")
                ver_lbl    = ctk.CTkLabel(top_line, text="", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_DIM, anchor="w")
                ver_lbl.pack(side="left", padx=(8, 0))
                author_lbl = ctk.CTkLabel(top_line, text="", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#666666", anchor="w")
                author_lbl.pack(side="left", padx=(10, 0))
                source_lbl = ctk.CTkLabel(top_line, text="", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=TEXT_DIM, anchor="w")
                source_lbl.pack(side="left", padx=(10, 0))

                desc_lbl = ctk.CTkLabel(left, text="", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_DIM, anchor="w", wraplength=700, justify="left")
                desc_lbl.pack(anchor="w", pady=(3, 0))

                right = ctk.CTkFrame(frame, fg_color="transparent", width=330)
                right.pack(side="right", padx=16, pady=10)
                right.pack_propagate(False)

                inst_lbl = ctk.CTkLabel(right, text="", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_DIM)
                inst_lbl.pack(anchor="e", pady=(0, 4))

                btn_row = ctk.CTkFrame(right, fg_color="transparent")
                btn_row.pack(anchor="e")

                toggle_canvas = tk.Canvas(btn_row, width=44, height=22, bg=CARD_BG, bd=0, highlightthickness=0)

                config_btn = ctk.CTkButton(
                    btn_row, text="Config",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    fg_color="#1e1e1e", hover_color="#2a2a2a",
                    text_color=TEXT_DIM, corner_radius=6,
                    border_width=0, width=72, height=28
                )
                _glow_on_hover(config_btn, targets=[config_btn], is_btn=True)

                support_btn = ctk.CTkButton(
                    btn_row, text="Support",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    fg_color="#1e1e1e", hover_color="#2a2a2a",
                    text_color=TEXT_DIM, corner_radius=6,
                    border_width=0, width=78, height=28
                )
                _glow_on_hover(support_btn, targets=[support_btn], is_btn=True)

                action_btn = ctk.CTkButton(
                    btn_row, text="Install",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    fg_color=ACCENT, hover_color="#cc0040",
                    text_color="#ffffff", corner_radius=6,
                    border_width=0, width=80, height=28
                )
                action_btn.pack(side="left")
                _glow_on_hover(action_btn, targets=[action_btn], is_btn=True)

                update_btn = ctk.CTkButton(
                    btn_row, text="Update",
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    fg_color="#1a3a1a", hover_color="#226622",
                    text_color="#44cc88", corner_radius=6,
                    border_width=0, width=80, height=28
                )
                _glow_on_hover(update_btn, targets=[update_btn], is_btn=True)

                pool.append({
                    "frame": frame, "name_lbl": name_lbl, "ver_lbl": ver_lbl,
                    "author_lbl": author_lbl, "source_lbl": source_lbl,
                    "desc_lbl": desc_lbl, "inst_lbl": inst_lbl, "left": left,
                    "icon_wrap": icon_wrap, "icon_lbl": icon_lbl,
                    "btn_row": btn_row,
                    "toggle_canvas": toggle_canvas, "config_btn": config_btn, "support_btn": support_btn, "action_btn": action_btn,
                    "update_btn": update_btn,
                    "mod": [None], "bound_game_key": [None],
                })
            return pool

        state["row_pool"] = _build_row_pool()

        def _draw_toggle(canvas, enabled):
            canvas.delete("all")
            bg_color = "#44cc88" if enabled else "#cc4444"
            x0, y0, x1, y1 = 0, 2, 44, 20
            r = 9
            canvas.create_arc(x0, y0, x0+r*2, y1, start=90,  extent=180, fill=bg_color, outline=bg_color)
            canvas.create_arc(x1-r*2, y0, x1, y1, start=270, extent=180, fill=bg_color, outline=bg_color)
            canvas.create_rectangle(x0+r, y0, x1-r, y1, fill=bg_color, outline=bg_color)
            cx = 32 if enabled else 12
            canvas.create_oval(cx-8, 3, cx+8, 19, fill="white", outline="white")

        def _bind_row(slot, mod, gk):
            import webbrowser
            slot["mod"][0]            = mod
            slot["bound_game_key"][0] = gk
            entry       = _installed_entry(mod["id"])
            installed   = _is_visible_installed(mod["id"])
            mod_enabled = [entry.get("enabled", True) if entry and installed else True]
            has_update  = mod["id"] in state["updates_available"]
            active_pack = _get_active_pack()
            in_active_pack = active_pack is not None and mod["id"] in _pack_mod_ids(active_pack)
            slot["config_btn"].pack_forget()
            slot["support_btn"].pack_forget()
            slot["icon_wrap"].pack_forget()

            slot["name_lbl"].configure(text=mod["name"])
            version_text = mod.get("version", "")
            slot["ver_lbl"].configure(text=f"v{version_text}" if version_text else "")
            slot["author_lbl"].configure(text=f"by {mod['author']}")

            icon_source = self._icon_source_for_mod(mod)
            if icon_source:
                slot["icon_wrap"].pack(side="left", padx=(16, 0), pady=10, before=slot["left"])
                self._load_mod_icon(mod, slot["icon_lbl"], size=40)
            else:
                try:
                    slot["icon_lbl"].configure(image=None, text="")
                    slot["icon_lbl"].image = None
                except Exception:
                    pass

            source = mod.get("source", "curated")
            if source == "thunderstore":
                slot["source_lbl"].configure(text="Thunderstore", text_color="#4a9eff")
            elif source == "manual":
                slot["source_lbl"].configure(text="Manual", text_color="#d6b36a")
            elif source == "github":
                slot["source_lbl"].configure(text="GitHub", text_color="#8ab4ff")
            elif source == "website":
                slot["source_lbl"].configure(text="Website", text_color="#7fc8a9")
            elif source == "curated":
                slot["source_lbl"].configure(text="Curated", text_color=ACCENT)
            else:
                slot["source_lbl"].configure(text="")

            slot["source_lbl"].unbind("<Button-1>")
            slot["source_lbl"].unbind("<Enter>")
            slot["source_lbl"].unbind("<Leave>")
            source_url = self._source_url_for_mod(gk, mod)
            if source_url and slot["source_lbl"].cget("text"):
                slot["source_lbl"].configure(cursor="hand2")
                slot["source_lbl"].bind("<Button-1>", lambda e, url=source_url: webbrowser.open(url))
                slot["source_lbl"].bind("<Enter>", lambda e, lbl=slot["source_lbl"]: lbl.configure(font=ctk.CTkFont(family="Segoe UI", size=10, underline=True)))
                slot["source_lbl"].bind("<Leave>", lambda e, lbl=slot["source_lbl"]: lbl.configure(font=ctk.CTkFont(family="Segoe UI", size=10)))
            else:
                slot["source_lbl"].configure(cursor="")

            slot["desc_lbl"].configure(text=mod.get("description", ""))

            support_url = mod.get("support")
            if support_url:
                slot["support_btn"].configure(command=lambda url=support_url: webbrowser.open(url))
                slot["support_btn"].pack(side="left", padx=(0, 6), before=slot["action_btn"])

            if active_pack:
                if has_update and installed:
                    slot["inst_lbl"].configure(text="Update Available", text_color="#ffaa00")
                elif in_active_pack:
                    lbl_text = f"In {active_pack.get('name', 'Active Pack')}"
                    lbl_color = "#44cc88" if mod_enabled[0] else "#ffaa00"
                    if not mod_enabled[0]:
                        lbl_text += " (disabled)"
                    slot["inst_lbl"].configure(text=lbl_text, text_color=lbl_color)
                else:
                    slot["inst_lbl"].configure(text="Not in active pack", text_color=TEXT_DIM)
                slot["action_btn"].configure(
                    text="Remove" if in_active_pack else "Add to Pack",
                    fg_color="#2a2a2a" if in_active_pack else ACCENT,
                    hover_color="#3a1a1a" if in_active_pack else "#cc0040",
                    text_color="#cc4444" if in_active_pack else "#ffffff",
                    state="normal"
                )
                slot["toggle_canvas"].pack_forget()
            else:
                if installed:
                    if has_update:
                        slot["inst_lbl"].configure(text="Update Available", text_color="#ffaa00")
                    else:
                        slot["inst_lbl"].configure(text="Installed", text_color="#44cc88")
                    slot["action_btn"].configure(
                        text="Remove", fg_color="#2a2a2a",
                        hover_color="#3a1a1a", text_color="#cc4444", state="normal"
                    )
                    game_data = self._detected_map.get(gk)
                    install_dir = game_data["install_dir"] if game_data else None
                    config_path = None
                    if install_dir and os.path.isdir(install_dir):
                        cached_path = state["config_paths"].get(mod["id"])
                        if cached_path and os.path.exists(cached_path):
                            config_path = cached_path
                        else:
                            config_path = self._mod_manager.get_mod_config_path(gk, mod["id"], install_dir)
                            state["config_paths"][mod["id"]] = config_path
                    if config_path:
                        slot["config_btn"].configure(command=lambda m=mod, p=config_path: _load_config_into_panel(m, p))
                        slot["config_btn"].pack(side="left", padx=(0, 6))
                    _draw_toggle(slot["toggle_canvas"], mod_enabled[0])
                    slot["toggle_canvas"].configure(cursor="hand2")
                    slot["toggle_canvas"].pack(side="left", padx=(0, 6), before=slot["action_btn"])
                else:
                    slot["inst_lbl"].configure(text="Not Installed", text_color=TEXT_DIM)
                    slot["action_btn"].configure(
                        text="Install", fg_color=ACCENT,
                        hover_color="#cc0040", text_color="#ffffff", state="normal"
                    )
                    slot["toggle_canvas"].pack_forget()

            slot["update_btn"].pack_forget()
            if installed and has_update:
                slot["update_btn"].pack(side="left", padx=(6, 0))
                slot["update_btn"].configure(state="normal",
                    command=lambda s=slot, gk2=gk: _do_update(s, gk2))

            slot["toggle_canvas"].unbind("<Button-1>")
            if installed and not active_pack:
                def _on_toggle(e=None, s=slot, gk2=gk, me=mod_enabled):
                    if not self._mod_manager.is_installed(gk2, s["mod"][0]["id"]):
                        return
                    new_state = not me[0]
                    me[0] = new_state
                    _draw_toggle(s["toggle_canvas"], new_state)
                    if new_state:
                        threading.Thread(target=lambda: self._mod_manager.enable_mod(gk2, s["mod"][0]["id"]), daemon=True).start()
                    else:
                        threading.Thread(target=lambda: self._mod_manager.disable_mod(gk2, s["mod"][0]["id"]), daemon=True).start()
                slot["toggle_canvas"].bind("<Button-1>", _on_toggle)

            def _do_remove(s=slot, gk2=gk):
                if _get_active_pack():
                    mod_id = s["mod"][0]["id"]
                    active_pack = _get_active_pack()
                    _remove_mod_from_active_pack(mod_id)
                    if not _mod_in_other_pack(mod_id, exclude_pack_id=active_pack.get("id") if active_pack else None):
                        try:
                            self._mod_manager.uninstall_mod(gk2, mod_id)
                        except Exception:
                            pass
                    else:
                        try:
                            _set_installed_owner(mod_id, _other_pack_owner(mod_id, exclude_pack_id=active_pack.get("id") if active_pack else None))
                            self._mod_manager.disable_mod(gk2, mod_id)
                        except Exception:
                            pass
                    if not _mod_in_other_pack(mod_id, exclude_pack_id=active_pack.get("id") if active_pack else None):
                        self._stats.track_mod_deleted(gk2, 1)
                    _go_page(state["page"])
                    return
                try:
                    self._mod_manager.uninstall_mod(gk2, s["mod"][0]["id"])
                    self._stats.track_mod_deleted(gk2, 1)
                    s["inst_lbl"].configure(text="Not Installed", text_color=TEXT_DIM)
                    s["action_btn"].configure(
                        text="Install", fg_color=ACCENT,
                        hover_color="#cc0040", text_color="#ffffff",
                        command=lambda: _do_install(s, gk2), state="normal"
                    )
                    s["toggle_canvas"].pack_forget()
                except Exception:
                    s["inst_lbl"].configure(text="Remove failed", text_color="#cc4444")

            def _finalize_pack_membership(installed_mods, gk2):
                active_pack_now = _get_active_pack()
                if not active_pack_now:
                    return
                for installed_mod in installed_mods:
                    _add_mod_to_active_pack(installed_mod)
                    try:
                        _set_installed_owner(installed_mod["id"], active_pack_now["id"])
                        self._mod_manager.enable_mod(gk2, installed_mod["id"])
                    except Exception:
                        pass

            def _add_existing_to_pack(s=slot, gk2=gk):
                _add_mod_to_active_pack(s["mod"][0])
                try:
                    if self._mod_manager.is_installed(gk2, s["mod"][0]["id"]):
                        active_pack = _get_active_pack()
                        if active_pack:
                            _set_installed_owner(s["mod"][0]["id"], active_pack["id"])
                        self._mod_manager.enable_mod(gk2, s["mod"][0]["id"])
                except Exception:
                    pass
                _go_page(state["page"])

            def _do_install(s=slot, gk2=gk, install_modloader_first=False, confirmed_deps=None):
                game_data   = self._detected_map.get(gk2)
                install_dir = game_data["install_dir"] if game_data else None

                if not install_dir or not os.path.isdir(install_dir):
                    s["inst_lbl"].configure(text="Game path not found", text_color="#cc4444")
                    return

                if not install_modloader_first and not self._mod_manager.check_modloader(gk2, install_dir):
                    _show_modloader_notif(s, gk2)
                    return

                if confirmed_deps is None:
                    all_mods_index = self._get_available_mods_for_game(gk2, fetch_thunderstore=False)
                    deps = self._mod_manager.resolve_dependencies(gk2, s["mod"][0], all_mods_index)
                    if deps:
                        _show_dep_notif(s, gk2, deps)
                        return

                _dismiss_notif()
                s["action_btn"].configure(state="disabled", text="Downloading...")

                deps_to_install = confirmed_deps or []
                all_installs    = deps_to_install + [s["mod"][0]]
                planned_ids     = {m["id"] for m in all_installs}
                before_ids      = {
                    mid for mid in planned_ids
                    if self._mod_manager.is_installed(gk2, mid)
                }
                total_steps     = len(all_installs)

                def install_all():
                    game_data2   = self._detected_map.get(gk2)
                    install_dir2 = game_data2["install_dir"] if game_data2 else None

                    if install_modloader_first:
                        try:
                            s["action_btn"].after(0, lambda: s["action_btn"].configure(text="Installing mod loader..."))
                            self._mod_manager.install_modloader(gk2, install_dir2)
                        except Exception:
                            s["inst_lbl"].after(0, lambda: s["inst_lbl"].configure(text="Mod loader install failed", text_color="#cc4444"))
                            s["action_btn"].after(0, lambda: s["action_btn"].configure(state="normal", text="Retry"))
                            return

                    bep_offset = 0.3 if install_modloader_first else 0.0
                    remaining  = 1.0 - bep_offset
                    installed_now = []

                    for i, current_mod in enumerate(all_installs):
                        step_start = bep_offset + (i / total_steps) * remaining
                        step_end   = bep_offset + ((i + 1) / total_steps) * remaining
                        n          = current_mod["name"]
                        s["action_btn"].after(0, lambda nm=n: s["action_btn"].configure(text=f"Installing {nm}..."))

                        try:
                            src = current_mod.get("source", "curated")
                            if src == "thunderstore":
                                self._mod_manager.install_mod_thunderstore(gk2, current_mod, install_dir2)
                            else:
                                self._mod_manager.install_mod(gk2, current_mod, install_dir2)
                            installed_now.append(current_mod)
                        except ModConflictError as exc:
                            s["inst_lbl"].after(0, lambda msg=str(exc): s["inst_lbl"].configure(text=msg, text_color="#ccaa44"))
                            s["action_btn"].after(0, lambda: s["action_btn"].configure(state="normal", text="Retry", command=lambda: _do_install(s, gk2)))
                            return
                        except Exception:
                            s["inst_lbl"].after(0, lambda: s["inst_lbl"].configure(text="Install failed", text_color="#cc4444"))
                            s["action_btn"].after(0, lambda: s["action_btn"].configure(state="normal", text="Retry", command=lambda: _do_install(s, gk2)))
                            return

                    _finalize_pack_membership(installed_now, gk2)
                    installed_count = sum(
                        1 for mid in planned_ids
                        if mid not in before_ids and self._mod_manager.is_installed(gk2, mid)
                    )
                    self._stats.track_mod_install(gk2, installed_count)

                    def on_done():
                        _go_page(state["page"])

                    s["action_btn"].after(0, on_done)

                threading.Thread(target=install_all, daemon=True).start()

            def _show_modloader_notif(s, gk2):
                _dismiss_notif()
                notif_bar.configure(height=40)
                notif_bar.pack_propagate(False)
                bar = ctk.CTkFrame(notif_bar, fg_color="#1e0a0a", corner_radius=0)
                bar.pack(fill="both", expand=True)
                ctk.CTkLabel(bar, text="Mod loader not installed — required to run mods. Would you like Moxi to install it?",
                    font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#cc4444", anchor="w"
                ).pack(side="left", padx=14)
                ctk.CTkButton(bar, text="No thanks", font=ctk.CTkFont(family="Segoe UI", size=10),
                    fg_color="transparent", hover_color="#2a1010", text_color="#666666",
                    corner_radius=4, border_width=0, width=80, height=26, command=_dismiss_notif
                ).pack(side="right", padx=(0, 6))
                ctk.CTkButton(bar, text="Install", font=ctk.CTkFont(family="Segoe UI", size=10),
                    fg_color="#4a1a1a", hover_color="#6a2a2a", text_color="#cc4444",
                    corner_radius=4, border_width=0, width=80, height=26,
                    command=lambda: [_dismiss_notif(), _do_install(s, gk2, install_modloader_first=True)]
                ).pack(side="right", padx=(0, 4))

            def _show_dep_notif(s, gk2, deps):
                _dismiss_notif()
                notif_bar.configure(height=40)
                notif_bar.pack_propagate(False)
                bar = ctk.CTkFrame(notif_bar, fg_color="#0a1a0a", corner_radius=0)
                bar.pack(fill="both", expand=True)
                names = ", ".join(d["name"] for d in deps)
                ctk.CTkLabel(bar, text=f"Requires: {names}. Install all?",
                    font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#44cc88", anchor="w"
                ).pack(side="left", padx=14)
                ctk.CTkButton(bar, text="Cancel", font=ctk.CTkFont(family="Segoe UI", size=10),
                    fg_color="transparent", hover_color="#1a2a1a", text_color="#666666",
                    corner_radius=4, border_width=0, width=70, height=26, command=_dismiss_notif
                ).pack(side="right", padx=(0, 6))
                ctk.CTkButton(bar, text="Install All", font=ctk.CTkFont(family="Segoe UI", size=10),
                    fg_color="#1a4a1a", hover_color="#226622", text_color="#44cc88",
                    corner_radius=4, border_width=0, width=90, height=26,
                    command=lambda: [_dismiss_notif(), _do_install(s, gk2, confirmed_deps=deps)]
                ).pack(side="right", padx=(0, 4))

            if active_pack and not in_active_pack and installed:
                slot["action_btn"].configure(command=lambda s=slot, gk2=game_key: _add_existing_to_pack(s, gk2))
            elif installed:
                slot["action_btn"].configure(command=lambda s=slot, gk2=game_key: _do_remove(s, gk2))
            else:
                slot["action_btn"].configure(command=lambda s=slot, gk2=game_key: _do_install(s, gk2))

            slot["frame"].pack(fill="x", padx=20, pady=(0, 6))

        def _dismiss_notif():
            for w in notif_bar.winfo_children():
                w.destroy()
            notif_bar.configure(height=0)
            notif_bar.pack_propagate(False)

        def _render_page(mods_slice, gk):
            _hide_message()
            pool = state["row_pool"]
            for slot in pool:
                slot["frame"].pack_forget()
            for i, mod in enumerate(mods_slice):
                _bind_row(pool[i], mod, gk)

        def _go_page(page):
            mods_source = state["filtered_mods"] if state["filtered_mods"] is not None else state["all_mods"]
            gk          = state["game_key"]
            total       = len(mods_source)
            max_page    = max(0, (total - 1) // PAGE_SIZE)
            page        = max(0, min(page, max_page))
            state["page"] = page

            start  = page * PAGE_SIZE
            sliced = mods_source[start:start + PAGE_SIZE]

            status_lbl.configure(text=f"{total} mod{'s' if total != 1 else ''}")
            try:
                print(
                    f"[Moxi Mods] render game={gk} total={total} "
                    f"filtered={state['filtered_mods'] is not None} page={page + 1}/{max_page + 1}",
                    flush=True,
                )
            except Exception:
                pass
            page_lbl.configure(text=f"Page {page + 1} of {max_page + 1}")
            prev_btn.configure(state="normal" if page > 0 else "disabled",
                               text_color=TEXT_DIM if page > 0 else "#333333")
            next_btn.configure(state="normal" if page < max_page else "disabled",
                               text_color=TEXT_DIM if page < max_page else "#333333")
            _render_page(sliced, gk)

        def _refresh_mods_view():
            _refresh_pack_controls()
            _go_page(state["page"])

        modpack_state["refresh_mods"] = _refresh_mods_view

        def _do_search(*_):
            if state["suppress_search"]:
                return
            if state["search_after"] is not None:
                try:
                    list_container.after_cancel(state["search_after"])
                except Exception:
                    pass
            state["search_after"] = list_container.after(350, _apply_search)

        def _apply_search():
            state["search_after"] = None
            query = search_var.get().strip().lower()
            gk    = state["game_key"]

            if not query:
                state["filtered_mods"] = None
                pager.pack(fill="x", side="bottom")
                _go_page(0)
                return

            terms = query.split()
            mods  = state["all_mods"]
            index = state["search_index"]
            gen   = state["search_gen"] + 1
            state["search_gen"] = gen

            status_lbl.configure(text="Searching...")
            pager.pack_forget()
            page_lbl.configure(text="")

            def _run():
                results = []
                for m, (words, blob) in zip(mods, index):
                    if all(any(t in kw for kw in words) or t in blob for t in terms):
                        results.append(m)
                if state["search_gen"] == gen:
                    list_container.after(0, lambda r=results, gk2=gk: _show_results(r, gk2))

            def _show_results(results, gk2):
                if state["search_gen"] != gen:
                    return
                state["filtered_mods"] = results
                status_lbl.configure(text=f"{len(results)} result{'s' if len(results) != 1 else ''}")
                if not results:
                    _show_message("No mods found.")
                    return
                _render_page(results[:PAGE_SIZE], gk2)

            threading.Thread(target=_run, daemon=True).start()

        def _apply_sort():
            sort = sort_var.get()
            mods = list(state["all_mods"])
            installed_set = {m["id"] for m in mods if _is_visible_installed(m["id"])}

            if sort == "Alphabetical":
                mods.sort(key=lambda m: m.get("name", "").lower())
            elif sort == "Author Name":
                mods.sort(key=lambda m: (m.get("author", "").lower(), m.get("name", "").lower()))
            elif sort == "Installed First":
                mods.sort(key=lambda m: (0 if m["id"] in installed_set else 1, m.get("name", "").lower()))
            elif sort == "Curated First":
                mods.sort(key=lambda m: (0 if m.get("source") == "curated" else 1, m.get("name", "").lower()))

            state["all_mods"]      = mods
            state["filtered_mods"] = None
            state["search_gen"]   += 1

            state["search_index"] = self._build_search_index(mods)

            state["suppress_search"] = True
            search_var.set("")
            state["suppress_search"] = False
            _go_page(0)

        def _check_updates(gk, all_mods):
            updates   = {}
            installed = self._mod_manager.installed.get(gk, {})
            for mod in all_mods:
                mid = mod["id"]
                if mid not in installed or not _is_visible_installed(mid):
                    continue
                inst_ver    = installed[mid].get("version", "")
                current_ver = mod.get("version", "")
                if inst_ver and current_ver and inst_ver != current_ver:
                    updates[mid] = current_ver
            return updates

        def _do_update(slot, gk2):
            mod         = slot["mod"][0]
            mid         = mod["id"]
            game_data   = self._detected_map.get(gk2)
            install_dir = game_data["install_dir"] if game_data else None

            if not install_dir or not os.path.isdir(install_dir):
                slot["inst_lbl"].configure(text="Game path not found", text_color="#cc4444")
                return

            was_enabled = self._mod_manager.installed.get(gk2, {}).get(mid, {}).get("enabled", True)

            slot["action_btn"].configure(state="disabled", text="Updating...")
            if "update_btn" in slot:
                slot["update_btn"].configure(state="disabled")

            def _run():
                try:
                    self._mod_manager.uninstall_mod(gk2, mid)
                    src = mod.get("source", "curated")

                    if src == "thunderstore":
                        self._mod_manager.install_mod_thunderstore(gk2, mod, install_dir)
                    else:
                        self._mod_manager.install_mod(gk2, mod, install_dir)

                    if not was_enabled:
                        self._mod_manager.disable_mod(gk2, mid)

                    def on_done():
                        state["updates_available"].pop(mid, None)
                        if not state["updates_available"]:
                            update_all_btn.pack_forget()
                        _bind_row(slot, mod, gk2)

                    slot["action_btn"].after(0, on_done)

                except ModConflictError as exc:
                    msg = str(exc)
                    def on_fail():
                        slot["inst_lbl"].configure(text=msg, text_color="#ccaa44")
                        slot["action_btn"].configure(state="normal", text="Remove",
                            command=lambda: _do_remove(slot, gk2))
                        if "update_btn" in slot:
                            slot["update_btn"].configure(state="normal")
                    slot["action_btn"].after(0, on_fail)
                except Exception:
                    def on_fail():
                        slot["inst_lbl"].configure(text="Update failed", text_color="#cc4444")
                        slot["action_btn"].configure(state="normal", text="Remove",
                            command=lambda: _do_remove(slot, gk2))
                        if "update_btn" in slot:
                            slot["update_btn"].configure(state="normal")
                    slot["action_btn"].after(0, on_fail)

            threading.Thread(target=_run, daemon=True).start()

        def _do_update_all():
            gk      = state["game_key"]
            updates = dict(state["updates_available"])
            if not updates:
                return

            update_all_btn.configure(state="disabled", text="Updating...")
            errors = []

            def _run_all():
                for mid, new_ver in updates.items():
                    mod = next((m for m in state["all_mods"] if m["id"] == mid), None)
                    if not mod:
                        continue
                    game_data   = self._detected_map.get(gk)
                    install_dir = game_data["install_dir"] if game_data else None
                    if not install_dir or not os.path.isdir(install_dir):
                        errors.append(mod["name"])
                        continue
                    was_enabled = self._mod_manager.installed.get(gk, {}).get(mid, {}).get("enabled", True)
                    try:
                        self._mod_manager.uninstall_mod(gk, mid)
                        src = mod.get("source", "curated")
                        if src == "thunderstore":
                            self._mod_manager.install_mod_thunderstore(gk, mod, install_dir)
                        else:
                            self._mod_manager.install_mod(gk, mod, install_dir)
                        if not was_enabled:
                            self._mod_manager.disable_mod(gk, mid)
                        state["updates_available"].pop(mid, None)
                    except Exception:
                        errors.append(mod["name"])

                def on_done():
                    update_all_btn.configure(state="normal", text="Update All")
                    if not state["updates_available"]:
                        update_all_btn.pack_forget()
                    _go_page(state["page"])
                    if errors:
                        _show_error_banner(f"Failed to update: {', '.join(errors)}")

                update_all_btn.after(0, on_done)

            threading.Thread(target=_run_all, daemon=True).start()

        def _show_error_banner(msg):
            _dismiss_notif()
            notif_bar.configure(height=40)
            notif_bar.pack_propagate(False)
            bar = ctk.CTkFrame(notif_bar, fg_color="#1e0a0a", corner_radius=0)
            bar.pack(fill="both", expand=True)
            ctk.CTkLabel(bar, text=msg,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="#cc4444", anchor="w"
            ).pack(side="left", padx=14)
            ctk.CTkButton(bar, text="Dismiss",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color="transparent", hover_color="#2a1010",
                text_color="#666666", corner_radius=4,
                border_width=0, width=70, height=26, command=_dismiss_notif
            ).pack(side="right", padx=(0, 10))

        def _show_rro_modloader_update_notif(update_info):
            game_data = self._detected_map.get(game_key)
            install_dir = game_data["install_dir"] if game_data else None
            if not install_dir:
                return

            installed_version = update_info.get("installed_version", "")
            latest_version = update_info.get("latest_version", "")

            _dismiss_notif()
            notif_bar.configure(height=40)
            notif_bar.pack_propagate(False)
            bar = ctk.CTkFrame(notif_bar, fg_color="#1e0f05", corner_radius=0)
            bar.pack(fill="both", expand=True)
            ctk.CTkLabel(
                bar,
                text=f"RROML update available: {installed_version} -> {latest_version}. Update now?",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="#e6b15c",
                anchor="w",
            ).pack(side="left", padx=14)

            update_btn = ctk.CTkButton(
                bar,
                text="Update",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color="#7a4a12",
                hover_color="#99611f",
                text_color="#ffffff",
                corner_radius=4,
                border_width=0,
                width=80,
                height=26,
            )
            update_btn.pack(side="right", padx=(0, 4))

            ctk.CTkButton(
                bar,
                text="Later",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color="transparent",
                hover_color="#2a1d10",
                text_color="#666666",
                corner_radius=4,
                border_width=0,
                width=70,
                height=26,
                command=_dismiss_notif,
            ).pack(side="right", padx=(0, 6))

            def _run_update():
                update_btn.after(0, lambda: update_btn.configure(state="disabled", text="Updating..."))
                try:
                    self._mod_manager.install_modloader("railroads_online", install_dir)
                except Exception:
                    notif_bar.after(0, lambda: _show_error_banner("Failed to update RROML"))
                    status_lbl.after(0, lambda: status_lbl.configure(text="RROML update failed", text_color="#cc4444"))
                    return

                notif_bar.after(0, _dismiss_notif)
                status_lbl.after(0, lambda: status_lbl.configure(text=f"RROML updated to {latest_version}", text_color="#44cc88"))

            update_btn.configure(command=lambda: threading.Thread(target=_run_update, daemon=True).start())

        def _import_manual(kind):
            from tkinter import filedialog

            game_data = self._detected_map.get(game_key)
            install_dir = game_data["install_dir"] if game_data else None
            if not install_dir or not os.path.isdir(install_dir):
                status_lbl.configure(text="Game path not found", text_color="#cc4444")
                return

            if not self._mod_manager.check_modloader(game_key, install_dir):
                status_lbl.configure(text="Install the mod loader first", text_color="#cc4444")
                return

            if kind == "file":
                selected_path = filedialog.askopenfilename(
                    title="Select a mod DLL",
                    filetypes=[("DLL files", "*.dll")]
                )
            else:
                selected_path = filedialog.askdirectory(title="Select a mod folder")

            if not selected_path:
                return

            status_lbl.configure(text="Importing manual mod...", text_color=TEXT_DIM)
            import_file_btn.configure(state="disabled")
            import_folder_btn.configure(state="disabled")

            def _run_import():
                try:
                    self._mod_manager.import_manual_mod(game_key, selected_path, install_dir)
                    def _on_done():
                        import_file_btn.configure(state="normal")
                        import_folder_btn.configure(state="normal")
                        status_lbl.configure(text="Manual mod imported", text_color="#44cc88")
                        _load_mods_data()
                    toolbar.after(0, _on_done)
                except ModConflictError as exc:
                    def _on_conflict():
                        import_file_btn.configure(state="normal")
                        import_folder_btn.configure(state="normal")
                        status_lbl.configure(text=str(exc), text_color="#ccaa44")
                    toolbar.after(0, _on_conflict)
                except Exception as exc:
                    def _on_fail(msg=str(exc)):
                        import_file_btn.configure(state="normal")
                        import_folder_btn.configure(state="normal")
                        status_lbl.configure(text=msg or "Manual import failed", text_color="#cc4444")
                    toolbar.after(0, _on_fail)

            threading.Thread(target=_run_import, daemon=True).start()

        import_file_btn.configure(command=lambda: _import_manual("file"))
        import_folder_btn.configure(command=lambda: _import_manual("folder"))

        def _load_mods_data():
            gk        = game_key
            supported = game.get("supported", False)

            state["page"]            = 0
            state["game_key"]        = gk
            state["all_mods"]        = []
            state["filtered_mods"]   = None
            state["config_paths"]    = {}
            state["suppress_search"] = True
            search_var.set("")
            state["suppress_search"] = False
            pager.pack(fill="x", side="bottom")
            for _s in state["row_pool"]:
                _s["frame"].pack_forget()
            _hide_message()
            _refresh_pack_controls()

            if not supported:
                status_lbl.configure(text="")
                _show_message(f"{game['name']} is not yet supported.")
                return

            if self._index_loading:
                status_lbl.configure(text="Loading index...")
                _show_message("Loading mod index...")
                self.after(300, _load_mods_data)
                return

            if not self._mod_index:
                status_lbl.configure(text="Failed to load index.")
                _show_message("Could not load mod index. Press Refresh to try again.")
                return

            curated_raw = self._mod_index.get("games", {}).get(gk, {}).get("mods", [])
            curated_ids = {m["id"] for m in curated_raw if m.get("id")}
            blocked = THUNDERSTORE_BLOCKLIST.get(gk, set()) if gk in THUNDERSTORE_GAMES else set()

            if gk in THUNDERSTORE_GAMES:
                ts_cached = self._thunderstore_cache.get(gk)
                if ts_cached is None or (gk == "valheim" and not ts_cached):
                    if gk not in self._ts_loading:
                        self._ts_loading.add(gk)
                        status_lbl.configure(text="Loading Thunderstore...")
                        _show_message("Fetching mods from Thunderstore...")
                        def _fetch(gk2=gk):
                            fetch_failed = False
                            try:
                                pkgs = self._mod_manager.fetch_thunderstore_packages(gk2)
                                self._thunderstore_cache[gk2] = pkgs
                            except Exception as exc:
                                fetch_failed = True
                            self._ts_loading.discard(gk2)
                            if self._active_frame and state["game_key"] == gk2:
                                if fetch_failed:
                                    self._active_frame.after(0, lambda: _show_message("Could not fetch Thunderstore mods. Press Refresh to try again."))
                                    self._active_frame.after(0, lambda: status_lbl.configure(text="Thunderstore unavailable", text_color="#cc4444"))
                                else:
                                    self._active_frame.after(0, _load_mods_data)
                        threading.Thread(target=_fetch, daemon=True).start()
                    return

            all_mods = self._get_available_mods_for_game(gk, fetch_thunderstore=False)

            state["all_mods"]      = all_mods
            state["filtered_mods"] = None
            state["search_gen"]   += 1

            state["search_index"] = self._build_search_index(all_mods)

            if not all_mods:
                status_lbl.configure(text="0 mods")
                _show_message("No mods available yet for this game.")
                return

            sort_var.set("Alphabetical")
            _go_page(0)

            def _run_update_check(gk2=gk, mods=all_mods):
                updates = _check_updates(gk2, mods)
                if self._active_frame and state["game_key"] == gk2:
                    list_container.after(0, lambda u=updates: _apply_updates(u))

            def _apply_updates(updates):
                state["updates_available"] = updates
                if updates:
                    update_all_btn.pack(side="right", padx=(0, 8), pady=8, before=refresh_btn)
                else:
                    update_all_btn.pack_forget()
                _go_page(state["page"])

            threading.Thread(target=_run_update_check, daemon=True).start()

            game_warnings = {
                "schedule_i": "⚠  Schedule I mods require the \"alternate\" Steam beta branch (Mono). Right-click the game → Properties → Betas.",
            }
            warning_msg = game_warnings.get(gk)
            if warning_msg and gk not in self._dismissed_warnings:
                for w in notif_bar.winfo_children():
                    w.destroy()
                notif_bar.configure(height=40)
                notif_bar.pack_propagate(False)
                bar = ctk.CTkFrame(notif_bar, fg_color="#0a0f1a", corner_radius=0)
                bar.pack(fill="both", expand=True)
                ctk.CTkLabel(bar, text=warning_msg,
                    font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#4a9eff", anchor="w"
                ).pack(side="left", padx=14)
                def _dismiss_warning(gk2=gk):
                    self._dismissed_warnings.add(gk2)
                    self._mod_manager.save_dismissed_warnings(self._dismissed_warnings)
                    for w in notif_bar.winfo_children():
                        w.destroy()
                    notif_bar.configure(height=0)
                    notif_bar.pack_propagate(False)
                ctk.CTkButton(bar, text="Got it",
                    font=ctk.CTkFont(family="Segoe UI", size=10),
                    fg_color="transparent", hover_color="#0a1a2a",
                    text_color="#666666", corner_radius=4,
                    border_width=0, width=70, height=26,
                    command=_dismiss_warning
                ).pack(side="right", padx=(0, 10))
            else:
                for w in notif_bar.winfo_children():
                    w.destroy()
                notif_bar.configure(height=0)
                notif_bar.pack_propagate(False)

            if gk == "railroads_online":
                game_data = self._detected_map.get(gk)
                install_dir = game_data["install_dir"] if game_data else None

                def _run_modloader_update_check():
                    try:
                        update_info = self._mod_manager.get_modloader_update_info(gk, install_dir)
                    except Exception:
                        return
                    if not update_info:
                        return
                    if self._active_frame and state["game_key"] == gk:
                        list_container.after(0, lambda info=update_info: _show_rro_modloader_update_notif(info))

                threading.Thread(target=_run_modloader_update_check, daemon=True).start()

        def _do_refresh():
            if self._index_loading:
                return
            refresh_btn.configure(text="Refreshing...", state="disabled")
            status_lbl.configure(text="")
            self._mod_manager.invalidate_thunderstore_cache(game_key)
            if game_key in self._thunderstore_cache:
                del self._thunderstore_cache[game_key]
            state["all_mods"] = []

            def on_done():
                refresh_btn.after(0, lambda: refresh_btn.configure(text="Refresh", state="normal"))
                refresh_btn.after(0, _load_mods_data)

            threading.Thread(target=self._do_fetch_index, args=(on_done,), daemon=True).start()

        search_var.trace_add("write", _do_search)

        if self._index_loading:
            status_lbl.configure(text="Loading...")
            self.after(400, _load_mods_data)
        else:
            _load_mods_data()

    def _make_mod_row_REMOVED(self, parent, mod, game_key, installed, notif_bar=None, on_install_done=None):
        row = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=8, height=80, border_width=0)
        row.pack(fill="x", padx=20, pady=(0, 6))
        row.pack_propagate(False)

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(16, 8), pady=10)

        top_line = ctk.CTkFrame(left, fg_color="transparent")
        top_line.pack(fill="x")

        ctk.CTkLabel(
            top_line, text=mod["name"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_ON, anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            top_line, text=f"v{mod['version']}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_DIM, anchor="w"
        ).pack(side="left", padx=(8, 0))

        ctk.CTkLabel(
            top_line, text=f"by {mod['author']}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#666666", anchor="w"
        ).pack(side="left", padx=(10, 0))

        source = mod.get("source", "curated")
        if source == "thunderstore":
            ctk.CTkLabel(
                top_line, text="Thunderstore",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color="#4a9eff", anchor="w"
            ).pack(side="left", padx=(10, 0))
        elif source == "curated":
            ctk.CTkLabel(
                top_line, text="Curated",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=ACCENT, anchor="w"
            ).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            left, text=mod.get("description", ""),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_DIM, anchor="w", wraplength=700, justify="left"
        ).pack(anchor="w", pady=(3, 0))

        right = ctk.CTkFrame(row, fg_color="transparent", width=140)
        right.pack(side="right", padx=16, pady=10)
        right.pack_propagate(False)

        status_lbl = ctk.CTkLabel(
            right,
            text="Installed" if installed else "Not Installed",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#44cc88" if installed else TEXT_DIM
        )
        status_lbl.pack(anchor="e", pady=(0, 4))

        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.pack(anchor="e")

        mod_enabled = [self._mod_manager.installed.get(game_key, {}).get(mod["id"], {}).get("enabled", True)]

        toggle_canvas = tk.Canvas(btn_row, width=44, height=22, bg=CARD_BG, bd=0, highlightthickness=0)
        toggle_canvas.pack(side="left", padx=(0, 8))

        def _draw_toggle(enabled, animating=False):
            toggle_canvas.delete("all")
            bg_color = "#44cc88" if enabled else "#cc4444"
            toggle_canvas.create_rounded_rect = None
            x0, y0, x1, y1 = 0, 2, 44, 20
            r = 9
            toggle_canvas.create_arc(x0, y0, x0+r*2, y1, start=90,  extent=180, fill=bg_color, outline=bg_color)
            toggle_canvas.create_arc(x1-r*2, y0, x1, y1, start=270, extent=180, fill=bg_color, outline=bg_color)
            toggle_canvas.create_rectangle(x0+r, y0, x1-r, y1, fill=bg_color, outline=bg_color)
            cx = 32 if enabled else 12
            toggle_canvas.create_oval(cx-8, 3, cx+8, 19, fill="white", outline="white")

        _draw_toggle(mod_enabled[0])

        def _animate_toggle(enabled, step=0, steps=6):
            if step > steps:
                mod_enabled[0] = enabled
                _draw_toggle(enabled)
                return
            progress = step / steps
            cx = int(12 + (32 - 12) * progress) if enabled else int(32 - (32 - 12) * progress)
            toggle_canvas.delete("all")
            bg_color = "#44cc88" if enabled else "#cc4444"
            x0, y0, x1, y1 = 0, 2, 44, 20
            r = 9
            toggle_canvas.create_arc(x0, y0, x0+r*2, y1, start=90,  extent=180, fill=bg_color, outline=bg_color)
            toggle_canvas.create_arc(x1-r*2, y0, x1, y1, start=270, extent=180, fill=bg_color, outline=bg_color)
            toggle_canvas.create_rectangle(x0+r, y0, x1-r, y1, fill=bg_color, outline=bg_color)
            toggle_canvas.create_oval(cx-8, 3, cx+8, 19, fill="white", outline="white")
            toggle_canvas.after(16, lambda: _animate_toggle(enabled, step+1, steps))

        def _on_toggle(e=None):
            if not self._mod_manager.is_installed(game_key, mod["id"]):
                return
            new_state = not mod_enabled[0]
            _animate_toggle(new_state)
            if new_state:
                threading.Thread(target=lambda: self._mod_manager.enable_mod(game_key, mod["id"]), daemon=True).start()
            else:
                threading.Thread(target=lambda: self._mod_manager.disable_mod(game_key, mod["id"]), daemon=True).start()

        if installed:
            toggle_canvas.configure(cursor="hand2")
            toggle_canvas.bind("<Button-1>", _on_toggle)
        else:
            toggle_canvas.pack_forget()

        action_btn = ctk.CTkButton(
            btn_row,
            text="Remove" if installed else "Install",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#2a2a2a" if installed else ACCENT,
            hover_color="#3a1a1a" if installed else "#cc0040",
            text_color="#cc4444" if installed else "#ffffff",
            corner_radius=6,
            border_width=0,
            width=120, height=28
        )
        action_btn.pack(side="left")
        _glow_on_hover(action_btn, targets=[action_btn], is_btn=True)

        def do_install():
            game_data   = self._detected_map.get(game_key)
            install_dir = game_data["install_dir"] if game_data else None

            if not install_dir or not os.path.isdir(install_dir):
                action_btn.after(0, lambda: status_lbl.configure(text="Game path not found", text_color="#cc4444"))
                action_btn.after(0, lambda: action_btn.configure(state="normal", text="Install"))
                return

            try:
                self._mod_manager.install_mod(game_key, mod, install_dir)
                self._stats.track_mod_install(game_key, 1)
                action_btn.after(0, action_btn.pack_forget)
                status_lbl.after(0, lambda: status_lbl.configure(text="Installed", text_color="#44cc88"))
                def set_remove():
                    if on_install_done:
                        on_install_done()
                    else:
                        action_btn.configure(
                            text="Remove", fg_color="#2a2a2a",
                            hover_color="#3a1a1a", text_color="#cc4444",
                            command=do_remove, state="normal"
                        )
                        action_btn.pack(side="left")
                        toggle_canvas.pack(side="left", padx=(0, 8))
                        toggle_canvas.configure(cursor="hand2")
                        toggle_canvas.bind("<Button-1>", _on_toggle)
                        _draw_toggle(True)
                action_btn.after(0, set_remove)
            except ModConflictError as exc:
                status_lbl.after(0, lambda msg=str(exc): status_lbl.configure(text=msg, text_color="#ccaa44"))
                def set_retry():
                    action_btn.configure(state="normal", text="Retry")
                    action_btn.pack(anchor="e")
                action_btn.after(0, set_retry)
            except Exception:
                status_lbl.after(0, lambda: status_lbl.configure(text="Install failed", text_color="#cc4444"))
                def set_retry():
                    action_btn.configure(state="normal", text="Retry")
                    action_btn.pack(anchor="e")
                action_btn.after(0, set_retry)

        def do_remove():
            try:
                self._mod_manager.uninstall_mod(game_key, mod["id"])
                self._stats.track_mod_deleted(game_key, 1)
                status_lbl.configure(text="Not Installed", text_color=TEXT_DIM)
                action_btn.configure(
                    text="Install", fg_color=ACCENT,
                    hover_color="#cc0040", text_color="#ffffff",
                    command=start_install, state="normal"
                )
                try:
                    toggle_canvas.pack_forget()
                except Exception:
                    pass
            except Exception:
                status_lbl.configure(text="Remove failed", text_color="#cc4444")

        def _dismiss_notif():
            if notif_bar is None:
                return
            for w in notif_bar.winfo_children():
                w.destroy()
            notif_bar.configure(height=0)
            notif_bar.pack_propagate(False)

        def _show_bepinex_notif():
            if notif_bar is None:
                return
            _dismiss_notif()
            notif_bar.configure(height=40)
            notif_bar.pack_propagate(False)
            bar = ctk.CTkFrame(notif_bar, fg_color="#1e0a0a", corner_radius=0)
            bar.pack(fill="both", expand=True)
            ctk.CTkLabel(
                bar,
                text="Mod loader not installed — required to run mods. Would you like Moxi to install it?",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="#cc4444", anchor="w"
            ).pack(side="left", padx=14)
            ctk.CTkButton(
                bar, text="No thanks",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color="transparent", hover_color="#2a1010",
                text_color="#666666", corner_radius=4,
                border_width=0, width=80, height=26,
                command=_dismiss_notif
            ).pack(side="right", padx=(0, 6))
            ctk.CTkButton(
                bar, text="Install Mod Loader",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color=ACCENT, hover_color="#cc0040",
                text_color="#ffffff", corner_radius=4,
                border_width=0, width=110, height=26,
                command=lambda: [_dismiss_notif(), start_install(install_bepinex_first=True)]
            ).pack(side="right", padx=(0, 4))

        def _show_dep_notif(deps):
            _dismiss_notif()
            notif_bar.configure(height=40)
            notif_bar.pack_propagate(False)
            bar = ctk.CTkFrame(notif_bar, fg_color="#0a1a0a", corner_radius=0)
            bar.pack(fill="both", expand=True)
            names = ", ".join(d["name"] for d in deps)
            ctk.CTkLabel(
                bar,
                text=f"Requires: {names}. Install all?",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="#44cc88", anchor="w"
            ).pack(side="left", padx=14)
            ctk.CTkButton(
                bar, text="Cancel",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color="transparent", hover_color="#1a2a1a",
                text_color="#666666", corner_radius=4,
                border_width=0, width=70, height=26,
                command=_dismiss_notif
            ).pack(side="right", padx=(0, 6))
            ctk.CTkButton(
                bar, text="Install All",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color="#1a4a1a", hover_color="#226622",
                text_color="#44cc88", corner_radius=4,
                border_width=0, width=90, height=26,
                command=lambda: [_dismiss_notif(), start_install(confirmed_deps=deps)]
            ).pack(side="right", padx=(0, 4))

        def start_install(install_bepinex_first=False, confirmed_deps=None):
            game_data   = self._detected_map.get(game_key)
            install_dir = game_data["install_dir"] if game_data else None

            if not install_dir:
                status_lbl.configure(text="Game not detected", text_color="#cc4444")
                return

            if not os.path.isdir(install_dir):
                status_lbl.configure(text="Install path missing", text_color="#cc4444")
                return

            if not install_bepinex_first and not self._mod_manager.check_modloader(game_key, install_dir):
                _show_bepinex_notif()
                return

            if confirmed_deps is None:
                all_mods = self._mod_index.get("games", {}).get(game_key, {}).get("mods", [])
                deps = self._mod_manager.resolve_dependencies(game_key, mod, all_mods)
                if deps:
                    _show_dep_notif(deps)
                    return

            _dismiss_notif()
            action_btn.configure(state="disabled", text="Downloading...")
            action_btn.pack(anchor="e")

            deps_to_install = confirmed_deps or []
            all_installs    = deps_to_install + [mod]
            planned_ids     = {m["id"] for m in all_installs}
            before_ids      = {
                mid for mid in planned_ids
                if self._mod_manager.is_installed(game_key, mid)
            }
            total_steps     = len(all_installs)

            def install_all():
                game_data2   = self._detected_map.get(game_key)
                install_dir2 = game_data2["install_dir"] if game_data2 else None

                if install_bepinex_first:
                    try:
                        action_btn.after(0, lambda: action_btn.configure(text="Installing mod loader..."))
                        self._mod_manager.install_modloader(game_key, install_dir2)
                    except Exception:
                        status_lbl.after(0, lambda: status_lbl.configure(text="Mod loader install failed", text_color="#cc4444"))
                        action_btn.after(0, lambda: action_btn.configure(state="normal", text="Retry"))
                        action_btn.after(0, lambda: action_btn.pack(anchor="e"))
                        return

                bep_offset = 0.3 if install_bepinex_first else 0.0
                remaining  = 1.0 - bep_offset

                for i, current_mod in enumerate(all_installs):
                    step_start = bep_offset + (i / total_steps) * remaining
                    step_end   = bep_offset + ((i + 1) / total_steps) * remaining
                    name       = current_mod["name"]

                    action_btn.after(0, lambda n=name: action_btn.configure(text=f"Installing {n}..."))

                    try:
                        if current_mod.get("source") == "thunderstore":
                            self._mod_manager.install_mod_thunderstore(game_key, current_mod, install_dir2)
                        else:
                            self._mod_manager.install_mod(game_key, current_mod, install_dir2)
                    except ModConflictError as exc:
                        status_lbl.after(0, lambda msg=f"{name}: {exc}": status_lbl.configure(
                            text=msg, text_color="#ccaa44"))
                        action_btn.after(0, lambda: action_btn.configure(state="normal", text="Retry"))
                        action_btn.after(0, lambda: action_btn.pack(anchor="e"))
                        return
                    except Exception:
                        status_lbl.after(0, lambda n=name: status_lbl.configure(
                            text=f"Failed: {n}", text_color="#cc4444"))
                        action_btn.after(0, lambda: action_btn.configure(state="normal", text="Retry"))
                        action_btn.after(0, lambda: action_btn.pack(anchor="e"))
                        return

                if on_install_done:
                    installed_count = sum(
                        1 for mid in planned_ids
                        if mid not in before_ids and self._mod_manager.is_installed(game_key, mid)
                    )
                    self._stats.track_mod_install(game_key, installed_count)
                    action_btn.after(0, on_install_done)
                else:
                    installed_count = sum(
                        1 for mid in planned_ids
                        if mid not in before_ids and self._mod_manager.is_installed(game_key, mid)
                    )
                    self._stats.track_mod_install(game_key, installed_count)
                    status_lbl.after(0, lambda: status_lbl.configure(text="Installed", text_color="#44cc88"))
                    def set_remove():
                        action_btn.configure(
                            text="Remove", fg_color="#2a2a2a",
                            hover_color="#3a1a1a", text_color="#cc4444",
                            command=do_remove, state="normal"
                        )
                        action_btn.pack(anchor="e")
                    action_btn.after(0, set_remove)

            threading.Thread(target=install_all, daemon=True).start()

        action_btn.configure(command=do_remove if installed else start_install)

        all_row_widgets = [row, left, right, top_line]
        all_row_widgets += self._all_descendants(left)
        all_row_widgets += self._all_descendants(top_line)
        _glow_on_hover(row, targets=all_row_widgets, bg_normal=CARD_BG, bg_hover="#222222")

    def _all_descendants(self, widget):
        result = []
        try:
            for child in widget.winfo_children():
                result.append(child)
                result.extend(self._all_descendants(child))
        except Exception:
            pass
        return result

    def _build_settings(self, parent):
        import subprocess, webbrowser

        scroll = ctk.CTkScrollableFrame(parent, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        def section(title):
            wrap = ctk.CTkFrame(scroll, fg_color=BG, corner_radius=0)
            wrap.pack(fill="x", padx=32, pady=(28, 0))
            ctk.CTkLabel(
                wrap, text=title,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=TEXT_ON, anchor="w"
            ).pack(anchor="w", pady=(0, 8))
            ctk.CTkFrame(wrap, fg_color="#252525", height=1, corner_radius=0).pack(fill="x", pady=(0, 14))
            return wrap

        def row(parent, label, widget_fn):
            r = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=8, height=54)
            r.pack(fill="x", pady=(0, 6))
            r.pack_propagate(False)
            ctk.CTkLabel(
                r, text=label,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=TEXT_ON, anchor="w"
            ).pack(side="left", padx=16)
            widget_fn(r)
            return r

        def action_btn(parent, text, command, danger=False):
            btn = ctk.CTkButton(
                parent, text=text,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                fg_color="#2a2a2a" if not danger else "#3a1010",
                hover_color="#333333" if not danger else "#5a1a1a",
                text_color=TEXT_DIM if not danger else "#cc4444",
                corner_radius=6, border_width=0,
                width=140, height=30,
                command=command
            )
            btn.pack(side="right", padx=16)
            _glow_on_hover(btn, targets=[btn], is_btn=True)
            return btn

        # --- About ---
        about = section("About")

        version_row = ctk.CTkFrame(about, fg_color=CARD_BG, corner_radius=8, height=54)
        version_row.pack(fill="x", pady=(0, 6))
        version_row.pack_propagate(False)

        ctk.CTkLabel(
            version_row, text=f"Moxi  v{MOXI_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_ON, anchor="w"
        ).pack(side="left", padx=16)

        update_lbl = ctk.CTkLabel(
            version_row, text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_DIM
        )
        update_lbl.pack(side="right", padx=(0, 8))

        def check_updates():
            check_btn.configure(state="disabled", text="Checking...")
            update_lbl.configure(text="")
            def _check():
                try:
                    tag, changelog, dl_url = self._mod_manager.check_for_app_update()
                    if tag and tag != MOXI_VERSION:
                        self._pending_update = {"version": tag, "changelog": changelog, "dl_url": dl_url}
                        def _show():
                            update_lbl.configure(text=f"v{tag} available", text_color=ACCENT)
                            check_btn.configure(state="normal", text="Download Update",
                                command=lambda: do_download(tag, changelog, dl_url))
                        check_btn.after(0, _show)
                    else:
                        check_btn.after(0, lambda: update_lbl.configure(text="Up to date", text_color="#44cc88"))
                        check_btn.after(0, lambda: check_btn.configure(state="normal", text="Check for Updates"))
                except Exception:
                    check_btn.after(0, lambda: update_lbl.configure(text="Check failed", text_color="#cc4444"))
                    check_btn.after(0, lambda: check_btn.configure(state="normal", text="Check for Updates"))
            threading.Thread(target=_check, daemon=True).start()

        def do_download(tag, changelog, dl_url):
            if not dl_url:
                update_lbl.configure(text="No installer found in release", text_color="#cc4444")
                return
            check_btn.configure(state="disabled", text="Downloading...")
            threading.Thread(
                target=self._do_download_update,
                args=(tag, changelog, dl_url, None, check_btn, update_lbl),
                daemon=True
            ).start()

        check_btn = action_btn(version_row, "Check for Updates", check_updates)

        # --- Game Paths ---
        paths_sec = section("Game Install Paths")

        for appid, info in SUPPORTED_GAMES.items():
            game_name = info["name"]
            game_key  = info["game_key"]
            detected  = self._detected_map.get(game_key)
            current   = detected["install_dir"] if detected else None

            path_row = ctk.CTkFrame(paths_sec, fg_color=CARD_BG, corner_radius=8, height=54)
            path_row.pack(fill="x", pady=(0, 6))
            path_row.pack_propagate(False)

            ctk.CTkLabel(
                path_row, text=game_name,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=TEXT_ON, anchor="w", width=160
            ).pack(side="left", padx=16)

            path_lbl = ctk.CTkLabel(
                path_row,
                text=current if current else "Not detected",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=TEXT_DIM if current else "#555555",
                anchor="w"
            )
            path_lbl.pack(side="left", padx=(0, 8), fill="x", expand=True)

            def browse(gkey=game_key, lbl=path_lbl):
                from tkinter import filedialog
                path = filedialog.askdirectory(title=f"Select install folder")
                if path:
                    if gkey not in self._detected_map:
                        self._detected_map[gkey] = {}
                    self._detected_map[gkey]["install_dir"] = path
                    lbl.configure(text=path, text_color=TEXT_DIM)

            browse_btn = ctk.CTkButton(
                path_row, text="Browse",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                fg_color="#2a2a2a", hover_color="#333333",
                text_color=TEXT_DIM,
                corner_radius=6, border_width=0,
                width=80, height=30,
                command=browse
            )
            browse_btn.pack(side="right", padx=16)
            _glow_on_hover(browse_btn, targets=[browse_btn], is_btn=True)

        # --- Data ---
        data_sec = section("Data")

        def refresh_settings_page():
            self._show_page("settings")

        def open_data_folder():
            path = DATA_DIR
            os.makedirs(path, exist_ok=True)
            os.startfile(path)

        row(data_sec, "Open Moxi data folder", lambda p: action_btn(p, "Open Folder", open_data_folder))

        def analytics_status_label():
            consent = self._stats._settings.get("consent")
            if consent is True:
                return "Enabled"
            if consent is False:
                return "Disabled"
            return "Not chosen"

        def toggle_analytics_consent():
            current = self._stats._settings.get("consent")
            enable = current is not True
            self._stats.set_consent(enable)
            if enable:
                self._stats.track_consent_accepted()
                self._stats.track_app_started()
            self._stats_consent_required = False
            self._refresh_nav_state()
            refresh_settings_page()

        analytics_row = ctk.CTkFrame(data_sec, fg_color=CARD_BG, corner_radius=8, height=54)
        analytics_row.pack(fill="x", pady=(0, 6))
        analytics_row.pack_propagate(False)

        ctk.CTkLabel(
            analytics_row, text="Anonymous analytics",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_ON, anchor="w"
        ).pack(side="left", padx=16)

        action_btn(
            analytics_row,
            "Disable" if self._stats._settings.get("consent") is True else "Enable",
            toggle_analytics_consent,
            danger=self._stats._settings.get("consent") is True,
        )

        ctk.CTkLabel(
            analytics_row, text=analytics_status_label(),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_DIM, anchor="e"
        ).pack(side="right", padx=(0, 8))

        optimization_row = ctk.CTkFrame(data_sec, fg_color=CARD_BG, corner_radius=8, height=54)
        optimization_row.pack(fill="x", pady=(0, 6))
        optimization_row.pack_propagate(False)

        ctk.CTkLabel(
            optimization_row, text="Staggered loading optimization",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_ON, anchor="w"
        ).pack(side="left", padx=16)

        def toggle_staggered_loading():
            self._set_staggered_loading_enabled(not self._is_staggered_loading_enabled())
            refresh_settings_page()

        action_btn(
            optimization_row,
            "Disable" if self._is_staggered_loading_enabled() else "Enable",
            toggle_staggered_loading,
            danger=self._is_staggered_loading_enabled(),
        )

        ctk.CTkLabel(
            optimization_row,
            text="On" if self._is_staggered_loading_enabled() else "Off",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_DIM, anchor="e"
        ).pack(side="right", padx=(0, 8))

        def clear_cache():
            import json
            dialog = ctk.CTkToplevel(self)
            dialog.title("Confirm")
            dialog.geometry("360x150")
            dialog.resizable(False, False)
            dialog.configure(fg_color="#1a1a1a")
            dialog.grab_set()
            dialog.lift()
            dialog.focus_force()

            ctk.CTkLabel(
                dialog,
                text="This will remove all installed mod records.\nActual mod files will NOT be deleted.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=TEXT_DIM, justify="center"
            ).pack(pady=(24, 16))

            btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
            btn_row.pack()

            def confirm():
                try:
                    db = os.path.join(DATA_DIR, "installed.json")
                    if os.path.exists(db):
                        os.remove(db)
                    self._mod_manager._load_installed()
                except Exception:
                    pass
                dialog.destroy()

            no_btn = ctk.CTkButton(
                btn_row, text="Cancel",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color="#2a2a2a", hover_color="#333333",
                text_color=TEXT_DIM, corner_radius=6, width=90, height=32,
                command=dialog.destroy
            )
            no_btn.pack(side="left", padx=(0, 10))
            _glow_on_hover(no_btn, targets=[no_btn], is_btn=True)

            yes_btn = ctk.CTkButton(
                btn_row, text="Clear Cache",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                fg_color="#3a1010", hover_color="#5a1a1a",
                text_color="#cc4444", corner_radius=6, width=110, height=32,
                command=confirm
            )
            yes_btn.pack(side="left")
            _glow_on_hover(yes_btn, targets=[yes_btn], is_btn=True)

        row(data_sec, "Clear installed mods cache", lambda p: action_btn(p, "Clear Cache", clear_cache, danger=True))

        def reset_recently_played():
            self._recently_played = []
            self._save_recently_played()
            if self._recently_played_row is not None:
                try:
                    for w in self._recently_played_row.winfo_children():
                        w.destroy()
                    ctk.CTkLabel(
                        self._recently_played_row,
                        text="Nothing here yet.",
                        font=ctk.CTkFont(family="Segoe UI", size=12),
                        text_color=TEXT_DIM
                    ).pack(side="left", padx=16, pady=30)
                except Exception:
                    pass

        row(data_sec, "Clear recently played history", lambda p: action_btn(p, "Clear History", reset_recently_played, danger=True))

    def _build_stats_consent(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        wrap.pack(fill="both", expand=True)

        center = ctk.CTkFrame(wrap, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        card = ctk.CTkFrame(center, fg_color=CARD_BG, corner_radius=14, width=760, height=420)
        card.pack()
        card.pack_propagate(False)

        ctk.CTkLabel(
            card,
            text="Data Tracking Notice",
            font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),
            text_color=ACCENT
        ).pack(pady=(34, 14))

        body = (
            "Moxi can collect a small amount of anonymous usage data to help improve the app.\n\n"
            "If you agree, Moxi will only track:\n"
            "- when you boot up Moxi\n"
            "- how long each session lasts so average time spent can be measured\n"
            "- how many mods get installed\n\n"
            "This data is meant to be safe and lightweight. If you do not agree, analytics will stay disabled and nothing will be tracked."
        )

        ctk.CTkLabel(
            card,
            text=body,
            font=ctk.CTkFont(family="Segoe UI", size=15),
            text_color=TEXT_ON,
            justify="center",
            wraplength=620
        ).pack(padx=42, pady=(0, 24))

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(pady=(4, 0))

        def accept():
            self._stats.set_consent(True)
            self._stats_consent_required = False
            self._refresh_nav_state()
            self._stats.track_consent_accepted()
            self._stats.track_app_started()
            self._show_page("dashboard")

        def decline():
            self._stats.set_consent(False)
            self._stats_consent_required = False
            self._refresh_nav_state()
            self._show_page("dashboard")

        accept_btn = ctk.CTkButton(
            btn_row, text="I Agree",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=ACCENT, hover_color="#cc0040",
            text_color="#ffffff", corner_radius=8,
            border_width=0, width=140, height=36,
            command=accept
        )
        accept_btn.pack(side="left", padx=(0, 10))
        _glow_on_hover(accept_btn, targets=[accept_btn], is_btn=True)

        cancel_btn = ctk.CTkButton(
            btn_row, text="Cancel",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color="#1e1e1e", hover_color="#2a2a2a",
            text_color=TEXT_DIM, corner_radius=8,
            border_width=0, width=140, height=36,
            command=decline
        )
        cancel_btn.pack(side="left")
        _glow_on_hover(cancel_btn, targets=[cancel_btn], is_btn=True)

    def _build_support_moxi(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        wrap.pack(fill="both", expand=True, padx=32, pady=32)

        card = ctk.CTkFrame(wrap, fg_color=CARD_BG, corner_radius=12)
        card.pack(expand=True, fill="both")

        ctk.CTkLabel(
            card,
            text="Support Moxi <3",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=ACCENT
        ).pack(anchor="w", padx=28, pady=(28, 12))

        ctk.CTkLabel(
            card,
            text="The best way to currently support Moxi is by sharing it with your friends and suggesting features on our discord or submitting issues on our GitHub. Thank you so much for using Moxi!",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=TEXT_ON,
            wraplength=760,
            justify="left",
            anchor="w"
        ).pack(anchor="w", padx=28, pady=(0, 18))

        back_btn = ctk.CTkButton(
            card, text="Back to Dashboard",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#1e1e1e", hover_color="#2a2a2a",
            text_color=TEXT_DIM, corner_radius=6,
            border_width=0, width=150, height=32,
            command=lambda: self._show_page("dashboard")
        )
        back_btn.pack(anchor="w", padx=28, pady=(0, 28))
        _glow_on_hover(back_btn, targets=[back_btn], is_btn=True)

    def _build_dev_info(self, parent):
        import webbrowser

        wrap = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        wrap.pack(fill="both", expand=True, padx=32, pady=32)

        card = ctk.CTkFrame(wrap, fg_color=CARD_BG, corner_radius=12)
        card.pack(expand=True, fill="both")

        ctk.CTkLabel(
            card,
            text="Dev Info",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=ACCENT
        ).pack(anchor="w", padx=28, pady=(28, 12))

        text_box = tk.Text(
            card,
            wrap="word",
            font=("Segoe UI", 14),
            fg=TEXT_ON,
            bg=CARD_BG,
            bd=0,
            highlightthickness=0,
            relief="flat",
            cursor="arrow",
            padx=0,
            pady=0,
            height=5
        )
        text_box.pack(fill="x", padx=28, pady=(0, 18))

        text_box.insert("end", "Hello devs, if you would like to submit a mod please open a pull request adding your mod to the ModIndex.json ")
        text_box.insert("end", "here", ("link",))
        text_box.insert("end", " and fill out all relevant information.\n\n")
        text_box.insert("end", "If you would like to remove your mod from Moxi or have any questions relating to adding mods or anything else please Email Me at kerbalmissile@gmail.com, shoot me a message on discord at kerbalmissile, or open an Issue or Pull Request on the ")
        text_box.insert("end", "GitHub", ("github_link",))
        text_box.insert("end", ".")

        text_box.tag_configure("link", foreground=ACCENT, underline=True)
        text_box.tag_configure("github_link", foreground=ACCENT, underline=True)
        text_box.tag_bind("link", "<Button-1>", lambda e: webbrowser.open("https://github.com/KerbalMissile/Moxi/blob/main/Mods/ModIndex.json"))
        text_box.tag_bind("github_link", "<Button-1>", lambda e: webbrowser.open("https://github.com/KerbalMissile/Moxi"))
        text_box.tag_bind("link", "<Enter>", lambda e: text_box.configure(cursor="hand2"))
        text_box.tag_bind("github_link", "<Enter>", lambda e: text_box.configure(cursor="hand2"))
        text_box.bind("<Leave>", lambda e: text_box.configure(cursor="arrow"))
        text_box.configure(state="disabled")

        back_btn = ctk.CTkButton(
            card, text="Back to Dashboard",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#1e1e1e", hover_color="#2a2a2a",
            text_color=TEXT_DIM, corner_radius=6,
            border_width=0, width=150, height=32,
            command=lambda: self._show_page("dashboard")
        )
        back_btn.pack(anchor="w", padx=28, pady=(0, 28))
        _glow_on_hover(back_btn, targets=[back_btn], is_btn=True)