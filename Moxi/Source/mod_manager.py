import os
import re
import io
import json
import string
import shutil
import time
import zipfile
import requests
from urllib.parse import urljoin


DATA_DIR      = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Moxi")
INSTALLED_DB  = os.path.join(DATA_DIR, "installed.json")
MODLOADER_STATE_DB = os.path.join(DATA_DIR, "modloaders.json")
DEBUG_LOG_PATH = os.path.join(DATA_DIR, "mod_manager_debug.log")
MOD_INDEX_URL  = "https://raw.githubusercontent.com/KerbalMissile/Moxi/main/Mods/ModIndex.json"
GAME_INDEX_URL = "https://raw.githubusercontent.com/KerbalMissile/Moxi/main/Games/GameIndex.json"
MOXI_REPO      = "KerbalMissile/Moxi"
MANUAL_MOD_DESTS = {
    "out_of_ore": "Mods",
}

CONFIG_SEARCH_CONFIGS = {
    "railroads_online": {
        "dir_parts": ("RROML", "Configs"),
        "extensions": (".json",),
        "exclude_substrings": ("-state",),
        "min_score": 8,
        "recursive": True,
    },
}


class ModConflictError(Exception):
    def __init__(self, conflicts):
        self.conflicts = conflicts
        mods = sorted({name for name, _ in conflicts})
        super().__init__(f"Conflicts with installed mod(s): {', '.join(mods)}")

MODLOADER_CONFIGS = {
    "railroads_online": {
        "type":        "github_latest",
        "repo":        "KerbalMissile/RROML",
        "asset":       "RROML-v",
        "asset_match": "startswith",
        "check_path":  "RROML",
        "mod_dest":    "",
    },
    "planet_crafter": {
        "type":       "static",
        "url":        "https://github.com/BepInEx/BepInEx/releases/download/v5.4.23.2/BepInEx_win_x64_5.4.23.2.zip",
        "check_path": os.path.join("BepInEx", "core", "BepInEx.dll"),
        "mod_dest":   os.path.join("BepInEx", "plugins"),
    },
    "subnautica": {
        "type":       "github_latest",
        "repo":       "toebeann/BepInEx.Subnautica",
        "asset":      "Tobey.s.BepInEx.Pack.for.Subnautica.zip",
        "check_path": os.path.join("BepInEx", "core", "BepInEx.dll"),
        "mod_dest":   os.path.join("BepInEx", "plugins"),
    },
    "subnautica_bz": {
        "type":       "github_latest",
        "repo":       "toebeann/BepInEx.SubnauticaZero",
        "asset":      "Tobey.s.BepInEx.Pack.for.Subnautica.Below.Zero.zip",
        "check_path": os.path.join("BepInEx", "core", "BepInEx.dll"),
        "mod_dest":   os.path.join("BepInEx", "plugins"),
    },
    "subnautica_2": {
        "type":          "github_latest",
        "repo":          "Subnautica2Modding/Subnautica2-UE4SS",
        "asset":         "UE4SS_v",
        "asset_match":   "startswith",
        "check_path":    os.path.join("Subnautica2", "Binaries", "Win64", "ue4ss", "UE4SS.dll"),
        "mod_dest":      os.path.join("Subnautica2", "Binaries", "Win64", "ue4ss", "Mods"),
        "install_subdir": os.path.join("Subnautica2", "Binaries", "Win64"),
        "mod_format":    "ue4ss",
    },
    "slime_rancher": {
        "type":       "github_latest",
        "repo":       "SlimeRancherModding/SRML",
        "asset":      "SRMLInstaller",
        "check_path": os.path.join("SRML", "Mods"),
        "mod_dest":   os.path.join("SRML", "Mods"),
        "asset_match": "startswith",
    },
    "slime_rancher_2": {
        "type":       "github_latest",
        "repo":       "LavaGang/MelonLoader",
        "asset":      "MelonLoader.x64.zip",
        "asset_x86":  "MelonLoader.x86.zip",
        "check_path": "MelonLoader",
        "mod_dest":   "Mods",
        "arch_detect": True,
    },
    "dyson_sphere": {
        "type":       "static",
        "url":        "https://github.com/BepInEx/BepInEx/releases/download/v5.4.23.2/BepInEx_win_x64_5.4.23.2.zip",
        "check_path": os.path.join("BepInEx", "core", "BepInEx.dll"),
        "mod_dest":   os.path.join("BepInEx", "plugins"),
    },
    "peak": {
        "type":       "thunderstore_pkg",
        "owner":      "BepInEx",
        "name":       "BepInExPack_PEAK",
        "community":  "peak",
        "check_path": os.path.join("BepInEx", "core", "BepInEx.dll"),
        "mod_dest":   os.path.join("BepInEx", "plugins"),
        "subfolder":  "BepInExPack_PEAK",
    },
    "schedule_i": {
        "type":       "github_latest",
        "repo":       "LavaGang/MelonLoader",
        "asset":      "MelonLoader.x64.zip",
        "asset_x86":  "MelonLoader.x86.zip",
        "check_path": "MelonLoader",
        "mod_dest":   "Mods",
        "arch_detect": True,
    },
    "valheim": {
        "type":       "thunderstore_pkg",
        "owner":      "denikson",
        "name":       "BepInExPack_Valheim",
        "community":  "valheim",
        "check_path": os.path.join("BepInEx", "core", "BepInEx.dll"),
        "mod_dest":   os.path.join("BepInEx", "plugins"),
        "subfolder":  "BepInExPack_Valheim",
    },
    "muck": {
        "type":       "thunderstore_pkg",
        "owner":      "BepInEx",
        "name":       "BepInExPack_Muck",
        "community":  "muck",
        "check_path": os.path.join("BepInEx", "core", "BepInEx.dll"),
        "mod_dest":   os.path.join("BepInEx", "plugins"),
        "subfolder":  "BepInExPack_Muck",
    },
    "boneworks": {
        "type":       "thunderstore_pkg",
        "owner":      "LavaGang",
        "name":       "MelonLoader",
        "community":  "boneworks",
        "check_path": "MelonLoader",
        "mod_dest":   "Mods",
        "subfolder":  "MelonLoader",
    },
    "supermarket_together": {
        "type":       "thunderstore_pkg",
        "owner":      "BepInEx",
        "name":       "BepInExPack",
        "community":  "supermarket-together",
        "version":    "5.4.2100",
        "check_path": os.path.join("BepInEx", "core", "BepInEx.dll"),
        "mod_dest":   os.path.join("BepInEx", "plugins"),
        "subfolder":  "BepInExPack",
    },
    "risk_of_rain_2": {
        "type":       "thunderstore_pkg",
        "owner":      "bbepis",
        "name":       "BepInExPack",
        "community":  "riskofrain2",
        "version":    "5.4.2100",
        "check_path": os.path.join("BepInEx", "core", "BepInEx.dll"),
        "mod_dest":   os.path.join("BepInEx", "plugins"),
        "subfolder":  "BepInExPack",
    },
    "bonelab": {
        "type":       "thunderstore_pkg",
        "owner":      "LavaGang",
        "name":       "MelonLoader",
        "community":  "bonelab",
        "check_path": "MelonLoader",
        "mod_dest":   "Mods",
        "subfolder":  "MelonLoader",
    },
    "easy_delivery_co": {
        "type":       "thunderstore_pkg",
        "owner":      "BepInEx",
        "name":       "BepInExPack",
        "community":  "easy-delivery-co",
        "version":    "5.4.2305",
        "check_path": os.path.join("BepInEx", "core", "BepInEx.dll"),
        "mod_dest":   os.path.join("BepInEx", "plugins"),
        "subfolder":  "BepInExPack",
    },
    "lakehopper": {
        "type":       "tbd",  # mod loader not yet released; placeholder until one exists
        "owner":      None,
        "name":       None,
        "community":  None,
        "check_path": None,
        "mod_dest":   None,
        "subfolder":  None,
    },
}

THUNDERSTORE_CONFIGS = {
    "dyson_sphere": {
        "community": "dyson-sphere-program",
        "mod_dest":  os.path.join("BepInEx", "plugins"),
    },
    "boneworks": {
        "community": "boneworks",
        "mod_dest":  "Mods",
    },
    "supermarket_together": {
        "community": "supermarket-together",
        "mod_dest":  os.path.join("BepInEx", "plugins"),
    },
    "schedule_i": {
        "community": "schedule-i",
        "mod_dest":  "Mods",
    },
    "peak": {
        "community": "peak",
        "mod_dest":  os.path.join("BepInEx", "plugins"),
    },
    "bonelab": {
        "community": "bonelab",
        "mod_dest":  "Mods",
    },
    "valheim": {
        "community": "valheim",
        "mod_dest":  os.path.join("BepInEx", "plugins"),
    },
    "scrap_mechanic": {
        "community": "scrap-mechanic",
        "mod_dest":  os.path.join("BepInEx", "plugins"),
    },
    "muck": {
        "community": "muck",
        "mod_dest":  os.path.join("BepInEx", "plugins"),
    },
    "risk_of_rain_2": {
        "community": "riskofrain2",
        "mod_dest":  os.path.join("BepInEx", "plugins"),
    },
    "easy_delivery_co": {
        "community": "easy-delivery-co",
        "mod_dest":  os.path.join("BepInEx", "plugins"),
    },
}


class ModManager:
    def __init__(self):
        self.installed = {}
        self.modloader_state = {}
        self._session = requests.Session()
        self._thunderstore_listing_cache = {}
        self._archive_cache = {}
        os.makedirs(DATA_DIR, exist_ok=True)
        self._load_installed()
        self._load_modloader_state()

    def _log_debug(self, message):
        line = f"[Moxi ModManager] {message}"
        try:
            print(line, flush=True)
        except Exception:
            pass
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"{line}\n")
        except Exception:
            pass

    def _load_installed(self):
        if os.path.exists(INSTALLED_DB):
            try:
                with open(INSTALLED_DB, "r") as f:
                    self.installed = json.load(f)
            except Exception:
                self.installed = {}
        else:
            self.installed = {}

    def _save_installed(self):
        with open(INSTALLED_DB, "w") as f:
            json.dump(self.installed, f, indent=2)

    def _load_modloader_state(self):
        if os.path.exists(MODLOADER_STATE_DB):
            try:
                with open(MODLOADER_STATE_DB, "r", encoding="utf-8") as f:
                    self.modloader_state = json.load(f)
            except Exception:
                self.modloader_state = {}
        else:
            self.modloader_state = {}

    def _save_modloader_state(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(MODLOADER_STATE_DB, "w", encoding="utf-8") as f:
            json.dump(self.modloader_state, f, indent=2)

    def _set_modloader_version(self, game_key, version):
        state = self.modloader_state.setdefault(game_key, {})
        state["version"] = version or ""
        self._log_debug(
            f"Saving modloader version game_key={game_key!r} version={state['version']!r} "
            f"path={MODLOADER_STATE_DB!r}"
        )
        self._save_modloader_state()

    def _infer_version_from_asset_name(self, asset_name):
        if not asset_name:
            return ""
        base = os.path.basename(asset_name)
        stem, _ = os.path.splitext(base)
        match = re.search(r"v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", stem)
        return match.group(0) if match else stem

    def get_stored_modloader_version(self, game_key):
        return self.modloader_state.get(game_key, {}).get("version", "")

    def _get_thunderstore_config(self, key_or_community):
        cfg = THUNDERSTORE_CONFIGS.get(key_or_community)
        if cfg:
            return cfg
        return next(
            (value for value in THUNDERSTORE_CONFIGS.values() if value.get("community") == key_or_community),
            {},
        )

    def _extract_archive_member(self, game_install_dir, dest_rel, member):
        rel_path = member.replace("\\", "/").strip("/")
        if not rel_path or rel_path.endswith("/"):
            return None

        parts = [p for p in rel_path.split("/") if p not in ("", ".")]
        if not parts:
            return None

        known_roots = {
            "BepInEx", "MelonLoader", "Mods", "UserData", "doorstop_libs",
            "dotnet", "mono", "core", "patchers", "plugins", "config",
        }
        dest_parts = [p for p in dest_rel.replace("\\", "/").split("/") if p]

        trimmed_parts = list(parts)
        if len(trimmed_parts) > 1:
            first = trimmed_parts[0]
            second = trimmed_parts[1]
            if first not in known_roots and (second in known_roots or second in dest_parts):
                trimmed_parts = trimmed_parts[1:]

        if not trimmed_parts:
            return None

        if trimmed_parts[0] in known_roots:
            final_parts = trimmed_parts
        elif dest_parts and trimmed_parts[:len(dest_parts)] == dest_parts:
            final_parts = trimmed_parts
        else:
            final_parts = dest_parts + trimmed_parts

        return os.path.join(game_install_dir, *final_parts)

    def _planned_archive_paths(self, zf, game_install_dir, dest_rel, include_prefix=None):
        planned = []
        prefix = include_prefix.replace("\\", "/").strip("/") if include_prefix else ""

        for member in zf.namelist():
            if member.endswith("/"):
                continue
            normalized = member.replace("\\", "/").strip("/")
            if not normalized:
                continue
            if prefix and normalized != prefix and not normalized.startswith(prefix + "/"):
                continue

            relative_member = normalized
            if prefix:
                relative_member = normalized[len(prefix):].strip("/")
                if not relative_member:
                    continue

            dest_path = self._extract_archive_member(game_install_dir, dest_rel, relative_member)
            if dest_path and not dest_path.endswith(os.sep):
                planned.append(dest_path)

        return planned

    def _normalize_conflict_path(self, path):
        return os.path.normcase(os.path.normpath(path))

    def _check_file_conflicts(self, game_key, mod_id, planned_files):
        planned_lookup = {}
        for path in planned_files:
            normalized = self._normalize_conflict_path(path)
            planned_lookup.setdefault(normalized, path)

        conflicts = []
        installed = self.installed.get(game_key, {})
        for other_mod_id, entry in installed.items():
            if other_mod_id == mod_id:
                continue
            other_name = entry.get("name", other_mod_id)
            for existing_path in entry.get("files", []):
                normalized_existing = self._normalize_conflict_path(existing_path)
                if normalized_existing in planned_lookup:
                    conflicts.append((other_name, planned_lookup[normalized_existing]))

        if conflicts:
            unique = []
            seen = set()
            for other_name, path in conflicts:
                key = (other_name, self._normalize_conflict_path(path))
                if key in seen:
                    continue
                seen.add(key)
                unique.append((other_name, path))
            raise ModConflictError(unique)

    def _extract_zip_to_game(self, zf, game_install_dir, dest_rel):
        installed_files = []

        for member in zf.namelist():
            if member.endswith("/"):
                continue

            dest_path = self._extract_archive_member(game_install_dir, dest_rel, member)
            if not dest_path:
                continue

            try:
                self._log_debug(f"extract_zip member={member!r} dest_path={dest_path!r}")
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with zf.open(member) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())
            except Exception as exc:
                self._log_debug(
                    f"extract_zip failed member={member!r} dest_path={dest_path!r} error={exc!r}"
                )
                raise
            installed_files.append(dest_path)

        return installed_files

    def _extract_zip_subset_to_game(self, zf, game_install_dir, dest_rel, include_prefix=None):
        installed_files = []
        prefix = include_prefix.replace("\\", "/").strip("/") if include_prefix else ""

        for member in zf.namelist():
            if member.endswith("/"):
                continue
            normalized = member.replace("\\", "/").strip("/")
            if not normalized:
                continue
            if prefix and normalized != prefix and not normalized.startswith(prefix + "/"):
                continue

            relative_member = normalized
            if prefix:
                relative_member = normalized[len(prefix):].strip("/")
                if not relative_member:
                    continue

            dest_path = self._extract_archive_member(game_install_dir, dest_rel, relative_member)
            if not dest_path:
                continue
            if os.path.isdir(dest_path):
                continue

            try:
                self._log_debug(
                    f"extract_zip_subset member={member!r} relative_member={relative_member!r} "
                    f"dest_path={dest_path!r} include_prefix={include_prefix!r}"
                )
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with zf.open(member) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())
            except Exception as exc:
                self._log_debug(
                    f"extract_zip_subset failed member={member!r} relative_member={relative_member!r} "
                    f"dest_path={dest_path!r} include_prefix={include_prefix!r} error={exc!r}"
                )
                raise
            installed_files.append(dest_path)

        return installed_files

    def _resolve_file_url(self, file_entry):
        direct_url = file_entry.get("url")
        if direct_url:
            return direct_url

        page_url = file_entry.get("page_url")
        if not page_url:
            raise ValueError("Mod file entry is missing both 'url' and 'page_url'.")

        response = self._session.get(page_url, timeout=30)
        response.raise_for_status()
        html = response.text

        pattern = file_entry.get("download_pattern")
        if pattern:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return urljoin(page_url, match.group(1))

        matches = re.findall(r'href=["\']([^"\']+\.(?:zip|rar|7z))["\']', html, re.IGNORECASE)
        if not matches:
            raise ValueError(f"No downloadable archive link found on page: {page_url}")

        return urljoin(page_url, matches[0])

    def _download_to_buffer(self, url, progress_cb=None, timeout=60, cache_key=None):
        if cache_key and cache_key in self._archive_cache:
            if progress_cb:
                progress_cb(1.0)
            return io.BytesIO(self._archive_cache[cache_key])

        r = self._session.get(url, stream=True, timeout=timeout)
        r.raise_for_status()

        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        buf = io.BytesIO()

        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                buf.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(downloaded / total)

        data = buf.getvalue()
        if cache_key and len(data) <= 200 * 1024 * 1024:
            self._archive_cache[cache_key] = data
        return io.BytesIO(data)

    def _slugify_mod_id(self, value):
        safe = value.lower().replace("&", "and")
        out = []
        last_dash = False
        for ch in safe:
            if ch in string.ascii_lowercase + string.digits:
                out.append(ch)
                last_dash = False
            elif not last_dash:
                out.append("-")
                last_dash = True
        return "".join(out).strip("-")

    def _expand_github_bundle(self, game_key, bundle):
        url = bundle.get("url")
        if not url:
            return []

        response = self._session.get(url, timeout=60)
        response.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(response.content))

        top_entries = {}
        for member in zf.namelist():
            normalized = member.replace("\\", "/").strip("/")
            if not normalized or normalized.endswith("/"):
                continue
            top = normalized.split("/", 1)[0]
            top_entries.setdefault(top, []).append(normalized)

        mods = []
        destination = bundle.get("destination", os.path.join("BepInEx", "plugins"))
        asset_name = os.path.basename(url.split("?", 1)[0]) or "bundle.zip"
        version = bundle.get("version", "")
        author = bundle.get("author", "GitHub")
        name_prefix = bundle.get("name_prefix", "").strip()
        id_prefix = bundle.get("id_prefix", "").strip()
        desc_prefix = bundle.get("description_prefix", "").strip()

        for top_name in sorted(top_entries):
            members = top_entries[top_name]
            include_prefix = top_name if any("/" in m for m in members) else members[0]
            display_name = f"{name_prefix}{top_name}" if name_prefix else top_name
            mod_id_base = f"{id_prefix}{top_name}" if id_prefix else top_name
            description = f"{desc_prefix}{top_name}" if desc_prefix else f"Installed from GitHub bundle: {top_name}"
            mods.append({
                "id": self._slugify_mod_id(mod_id_base),
                "name": display_name,
                "author": author,
                "version": version,
                "description": description,
                "source": "github",
                "files": [{
                    "url": url,
                    "filename": asset_name,
                    "destination": destination,
                    "extract": True,
                    "include_prefix": include_prefix,
                }],
            })

        return mods

    def _extract_share_code(self, code):
        raw = code.strip()
        if not raw:
            raise ValueError("Please enter a Thunderstore share code.")

        raw = raw.lstrip("#").strip()
        if "://" in raw:
            match = re.search(r"/profile/[^/]+/([^/?#]+)", raw)
            if not match:
                match = re.search(r"[?&]code=([^&#]+)", raw)
            if match:
                raw = match.group(1)

        return raw

    def _load_thunderstore_profile_manifest(self, code):
        import base64
        import gzip as gz

        uuid_like = re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            code,
        )

        if uuid_like:
            url = f"https://thunderstore.io/api/experimental/legacyprofile/get/{code}/"
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            payload = response.text.strip().replace("#r2modman", "").strip()
            if not payload:
                raise ValueError("Thunderstore returned an empty profile for that code.")

            try:
                archive_bytes = base64.b64decode(payload)
                archive = io.BytesIO(archive_bytes)
                with zipfile.ZipFile(archive) as zf:
                    manifest_name = next(
                        (
                            name for name in zf.namelist()
                            if name.endswith("export.r2x") or name.endswith("mods.yml")
                        ),
                        None,
                    )
                    if not manifest_name:
                        raise ValueError("Thunderstore profile did not contain an export manifest.")
                    return zf.read(manifest_name).decode("utf-8", errors="replace")
            except ValueError:
                raise
            except Exception:
                raise ValueError("Thunderstore returned a profile, but Moxi couldn't read its archive.")

        pad = (4 - len(code) % 4) % 4
        padded = code + "=" * pad

        try:
            compressed = base64.urlsafe_b64decode(padded)
            return gz.decompress(compressed).decode("utf-8")
        except Exception:
            raise ValueError("Invalid share code. Moxi couldn't decode that Thunderstore profile.")

    def _parse_thunderstore_package_ref(self, value, fallback_version=None):
        ref = value.strip().strip("'\"")
        if not ref:
            return None

        version = fallback_version
        parts = [p for p in ref.split("-") if p]
        if len(parts) < 2:
            return None

        semver_like = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
        if version is None and len(parts) >= 3 and semver_like.match(parts[-1]):
            version = parts[-1]
            parts = parts[:-1]

        if len(parts) < 2:
            return None

        owner = parts[0]
        name = "-".join(parts[1:])
        return owner, name, version

    def _parse_thunderstore_manifest(self, raw):
        profile_name = ""
        mods = []

        profile_match = re.search(r"(?m)^\s*profileName:\s*(.+?)\s*$", raw)
        if profile_match:
            profile_name = profile_match.group(1).strip().strip("'\"")

        mods_start = re.search(r"(?m)^\s*mods:\s*$", raw)
        if not mods_start:
            return profile_name, mods

        mods_text = raw[mods_start.end():]
        entry_blocks = re.findall(r"(?ms)^\s*-\s+.*?(?=^\s*-\s+|\Z)", mods_text)

        for block in entry_blocks:
            name = None
            enabled = True
            version = None
            version_parts = {}

            direct_name = re.search(r"(?m)^\s*-\s*(?:name|full_name):\s*(.+?)\s*$", block)
            if direct_name:
                name = direct_name.group(1).strip().strip("'\"")
            else:
                later_name = re.search(r"(?m)^\s*(?:name|full_name):\s*(.+?)\s*$", block)
                if later_name:
                    name = later_name.group(1).strip().strip("'\"")

            enabled_match = re.search(r"(?m)^\s*enabled:\s*(.+?)\s*$", block)
            if enabled_match:
                enabled_val = enabled_match.group(1).strip().strip("'\"").lower()
                enabled = enabled_val not in {"false", "0", "no"}

            scalar_version = re.search(r"(?m)^\s*(?:version|version_number):\s*([0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?)\s*$", block)
            if scalar_version:
                version = scalar_version.group(1).strip()

            for part_match in re.finditer(r"(?m)^\s*(major|minor|patch):\s*(\d+)\s*$", block):
                version_parts[part_match.group(1)] = part_match.group(2)

            if not version and version_parts:
                ordered = [version_parts.get(k) for k in ("major", "minor", "patch")]
                if all(part is not None for part in ordered):
                    version = ".".join(ordered)

            if not name or not enabled:
                continue

            ref = self._parse_thunderstore_package_ref(name, version)
            if not ref:
                continue

            owner, pkg_name, pkg_version = ref
            mods.append({
                "owner": owner,
                "name": pkg_name,
                "version": pkg_version,
            })

        if not mods:
            for line in mods_text.splitlines():
                stripped = line.strip()
                if not stripped.startswith("-"):
                    continue
                item = stripped[1:].strip().strip("'\"")
                ref = self._parse_thunderstore_package_ref(item)
                if not ref:
                    continue
                owner, pkg_name, pkg_version = ref
                mods.append({
                    "owner": owner,
                    "name": pkg_name,
                    "version": pkg_version,
                })

        return profile_name, mods

    def check_modloader(self, game_key, install_dir):
        cfg = MODLOADER_CONFIGS.get(game_key)
        if not cfg:
            return True
        return os.path.exists(os.path.join(install_dir, cfg["check_path"]))

    def _fetch_github_latest_release(self, repo):
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        return response.json()

    def _get_modloader_release_info(self, game_key):
        cfg = MODLOADER_CONFIGS.get(game_key)
        if not cfg:
            raise ValueError(f"No modloader config for: {game_key}")

        if game_key == "railroads_online":
            release = self._fetch_github_latest_release(cfg["repo"])
            assets = release.get("assets", [])
            zip_assets = [asset for asset in assets if asset.get("name", "").lower().endswith(".zip")]
            if not zip_assets:
                raise ValueError(f"No zip asset found in latest release for {cfg['repo']}")
            asset = zip_assets[0]
            version = (
                release.get("tag_name")
                or release.get("name")
                or self._infer_version_from_asset_name(asset.get("name", ""))
            )
            self._log_debug(
                "Resolved RROML release "
                f"repo={cfg['repo']!r} tag={release.get('tag_name')!r} asset={asset.get('name')!r} "
                f"version={version!r}"
            )
            return {
                "download_url": asset["browser_download_url"],
                "version": version,
                "asset_name": asset.get("name", ""),
            }

        if cfg["type"] == "static":
            version = cfg.get("version")
            if not version:
                match = re.search(r"/download/([^/]+)/", cfg["url"])
                version = match.group(1) if match else ""
            return {
                "download_url": cfg["url"],
                "version": version,
            }

        if cfg["type"] == "thunderstore_pkg":
            owner     = cfg["owner"]
            name      = cfg["name"]
            community = cfg["community"]
            api_url   = f"https://thunderstore.io/c/{community}/api/v1/package/{owner}/{name}/"
            r = requests.get(api_url, timeout=10)
            r.raise_for_status()
            versions = r.json().get("versions", [])
            if not versions:
                raise ValueError(f"No versions found for Thunderstore pkg {owner}/{name}")
            preferred_version = cfg.get("version")
            if preferred_version:
                match = next((v for v in versions if v.get("version_number") == preferred_version), None)
                if not match:
                    raise ValueError(
                        f"Requested Thunderstore version {preferred_version} not found for {owner}/{name}"
                    )
                return {
                    "download_url": match["download_url"],
                    "version": match.get("version_number", preferred_version),
                }
            latest = versions[0]
            return {
                "download_url": latest["download_url"],
                "version": latest.get("version_number", ""),
            }

        if cfg["type"] == "github_latest":
            import platform

            release = self._fetch_github_latest_release(cfg["repo"])
            assets = release.get("assets", [])

            if cfg.get("arch_detect"):
                bits = platform.architecture()[0]
                asset_name = cfg["asset"] if bits == "64bit" else cfg.get("asset_x86", cfg["asset"])
            else:
                asset_name = cfg["asset"]

            match_mode = cfg.get("asset_match", "exact")
            for asset in assets:
                name = asset["name"]
                if match_mode == "startswith" and name.startswith(asset_name) and name.endswith(".zip"):
                    return {
                        "download_url": asset["browser_download_url"],
                        "version": release.get("tag_name") or release.get("name") or name,
                    }
                if match_mode == "exact" and name == asset_name:
                    return {
                        "download_url": asset["browser_download_url"],
                        "version": release.get("tag_name") or release.get("name") or name,
                    }

            raise ValueError(f"No matching asset for {cfg['repo']}: '{asset_name}'")

        raise ValueError(f"Unknown modloader type: {cfg['type']}")

    def get_modloader_update_info(self, game_key, install_dir):
        if game_key != "railroads_online":
            return None
        if not install_dir or not self.check_modloader(game_key, install_dir):
            return None

        installed_version = self.get_stored_modloader_version(game_key)
        if not installed_version:
            return None

        latest = self._get_modloader_release_info(game_key)
        latest_version = latest.get("version", "")
        if not latest_version or latest_version == installed_version:
            return None

        return {
            "installed_version": installed_version,
            "latest_version": latest_version,
            "download_url": latest.get("download_url", ""),
            "update_available": True,
        }

    def _clear_directory_except(self, target_dir, keep_names=()):
        if not os.path.isdir(target_dir):
            return

        keep = {name.lower() for name in keep_names}
        for entry in os.listdir(target_dir):
            if entry.lower() in keep:
                continue
            path = os.path.join(target_dir, entry)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    def _prepare_modloader_update_target(self, game_key, install_dir):
        if game_key != "railroads_online":
            return
        self._clear_directory_except(os.path.join(install_dir, "RROML"), keep_names={"Mods"})

    def get_mod_dest(self, game_key):
        manual_dest = MANUAL_MOD_DESTS.get(game_key)
        if manual_dest:
            return manual_dest
        cfg = MODLOADER_CONFIGS.get(game_key)
        return cfg["mod_dest"] if cfg else os.path.join("BepInEx", "plugins")

    def _unique_manual_mod_id(self, game_key, base_name):
        slug = self._slugify_mod_id(base_name) or "manual-mod"
        base_id = f"manual-{slug}"
        existing = set(self.installed.get(game_key, {}))
        if base_id not in existing:
            return base_id
        i = 2
        while f"{base_id}-{i}" in existing:
            i += 1
        return f"{base_id}-{i}"

    def get_manual_mods(self, game_key):
        mods = []
        for mod_id, entry in self.installed.get(game_key, {}).items():
            if entry.get("source") != "manual":
                continue
            mods.append({
                "id": mod_id,
                "name": entry.get("name", mod_id),
                "author": entry.get("author", "Local"),
                "version": entry.get("version", ""),
                "description": entry.get("description", "Imported manually from disk."),
                "source": "manual",
                "files": entry.get("mod_files", []),
            })
        return mods

    def import_manual_mod(self, game_key, source_path, game_install_dir):
        if not source_path or not os.path.exists(source_path):
            raise ValueError("Selected file or folder was not found.")

        dest_rel = self.get_mod_dest(game_key)
        dest_root = os.path.join(game_install_dir, dest_rel)
        os.makedirs(dest_root, exist_ok=True)

        source_name = os.path.basename(os.path.normpath(source_path))
        if os.path.isfile(source_path):
            if not source_name.lower().endswith(".dll"):
                raise ValueError("Manual file import currently supports .dll files only.")
            mod_name = os.path.splitext(source_name)[0]
            mod_id = self._unique_manual_mod_id(game_key, mod_name)
            dest_path = os.path.join(dest_root, source_name)
            self._check_file_conflicts(game_key, mod_id, [dest_path])
            shutil.copy2(source_path, dest_path)
            copied_files = [dest_path]
            description = f"Imported manually from file: {source_name}"
            manual_kind = "file"
        else:
            mod_name = source_name
            mod_id = self._unique_manual_mod_id(game_key, mod_name)
            dest_base = os.path.join(dest_root, source_name)
            planned_files = []
            for root, _, files in os.walk(source_path):
                rel_root = os.path.relpath(root, source_path)
                for filename in files:
                    if rel_root == ".":
                        planned_files.append(os.path.join(dest_base, filename))
                    else:
                        planned_files.append(os.path.join(dest_base, rel_root, filename))
            self._check_file_conflicts(game_key, mod_id, planned_files)
            copied_files = []
            for root, dirs, files in os.walk(source_path):
                rel_root = os.path.relpath(root, source_path)
                target_root = dest_base if rel_root == "." else os.path.join(dest_base, rel_root)
                os.makedirs(target_root, exist_ok=True)
                for dirname in dirs:
                    os.makedirs(os.path.join(target_root, dirname), exist_ok=True)
                for filename in files:
                    src_file = os.path.join(root, filename)
                    dst_file = os.path.join(target_root, filename)
                    shutil.copy2(src_file, dst_file)
                    copied_files.append(dst_file)
            description = f"Imported manually from folder: {source_name}"
            manual_kind = "folder"

        if game_key not in self.installed:
            self.installed[game_key] = {}

        self.installed[game_key][mod_id] = {
            "name": mod_name,
            "version": "",
            "files": copied_files,
            "enabled": True,
            "source": "manual",
            "author": "Local",
            "description": description,
            "manual_kind": manual_kind,
            "mod_files": copied_files,
        }
        self._save_installed()

        return mod_id

    def _resolve_modloader_url(self, game_key):
        return self._get_modloader_release_info(game_key)["download_url"]

    def install_modloader(self, game_key, install_dir, progress_cb=None):
        release_info = self._get_modloader_release_info(game_key)
        url = release_info["download_url"]
        cfg = MODLOADER_CONFIGS.get(game_key, {})
        self._log_debug(
            f"Installing modloader game_key={game_key!r} install_dir={install_dir!r} "
            f"url={url!r} version={release_info.get('version', '')!r}"
        )
        r   = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()

        total      = int(r.headers.get("content-length", 0))
        downloaded = 0
        buf        = io.BytesIO()

        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                buf.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(downloaded / total)

        buf.seek(0)
        subfolder    = cfg.get("subfolder", "")
        install_subdir = cfg.get("install_subdir", "")

        with zipfile.ZipFile(buf) as zf:
            self._prepare_modloader_update_target(game_key, install_dir)
            if subfolder:
                # Strip the leading subfolder prefix (e.g. BepInExPack_Valheim/)
                prefix = subfolder.rstrip("/") + "/"
                for member in zf.namelist():
                    if not member.startswith(prefix):
                        continue
                    rel = member[len(prefix):]
                    if not rel:
                        continue
                    dest = os.path.join(install_dir, rel)
                    if member.endswith("/"):
                        os.makedirs(dest, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
            elif install_subdir:
                # Extract into a specific subdirectory of install_dir
                # e.g. subnautica_2 needs files in Subnautica2/Binaries/Win64/
                target_dir = os.path.join(install_dir, install_subdir)
                for member in zf.namelist():
                    if member.endswith("/"):
                        continue
                    dest = os.path.join(target_dir, member)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with zf.open(member) as src, open(dest, "wb") as dst:
                        dst.write(src.read())
            else:
                zf.extractall(install_dir)

        version = release_info.get("version", "") or self._infer_version_from_asset_name(
            release_info.get("asset_name", "")
        )
        self._set_modloader_version(game_key, version)

    def check_bepinex(self, install_dir):
        dll = os.path.join(install_dir, "BepInEx", "core", "BepInEx.dll")
        return os.path.exists(dll)

    def install_bepinex(self, install_dir, game_key, progress_cb=None):
        return self.install_modloader(game_key, install_dir, progress_cb)

    def fetch_mod_index(self):
        r = requests.get(MOD_INDEX_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        base_url = MOD_INDEX_URL.rsplit("/", 1)[0] + "/"
        for game_key, game_data in data.get("games", {}).items():
            for mod in game_data.get("mods", []):
                mod.setdefault("__base_url", base_url)
            expanded = []
            for bundle in game_data.get("github_bundles", []):
                try:
                    expanded.extend(self._expand_github_bundle(game_key, bundle))
                except Exception:
                    continue
            if expanded:
                for mod in expanded:
                    mod.setdefault("__base_url", base_url)
                game_data.setdefault("mods", [])
                game_data["mods"].extend(expanded)
        return data

    def fetch_game_index(self):
        r = requests.get(GAME_INDEX_URL, timeout=10)
        r.raise_for_status()
        return r.json()

    def _version_key(self, value):
        if not value:
            return (0,)
        parts = []
        for token in re.findall(r"\d+|[A-Za-z]+", str(value)):
            if token.isdigit():
                parts.append((0, int(token)))
            else:
                parts.append((1, token.lower()))
        return tuple(parts) if parts else ((0, 0),)

    def fetch_thunderstore_packages(self, game_key):
        cfg = THUNDERSTORE_CONFIGS.get(game_key)
        if not cfg:
            return []
        cached = self._thunderstore_listing_cache.get(game_key)
        now = time.time()
        if cached and now - cached["time"] < 300:
            return cached["mods"]
        community = cfg["community"]
        mods      = []
        seen_ids  = set()
        next_url  = f"https://thunderstore.io/c/{community}/api/v1/package/?page=1"
        page      = 1

        while next_url and page <= 100:
            url = next_url
            try:
                r = self._session.get(url, timeout=30)
            except requests.RequestException:
                break
            if r.status_code == 404:
                break
            try:
                r.raise_for_status()
                data = r.json()
            except (requests.RequestException, ValueError):
                break
            packages = data if isinstance(data, list) else data.get("results", [])
            if not isinstance(packages, list):
                break

            for pkg in packages:
                if not isinstance(pkg, dict):
                    continue
                if pkg.get("is_deprecated"):
                    continue
                owner = pkg.get("owner")
                name = pkg.get("name")
                if not owner or not name:
                    continue
                versions = [v for v in (pkg.get("versions") or []) if isinstance(v, dict)]
                if not versions:
                    continue
                latest = versions[0]
                download_url = latest.get("download_url")
                version_number = latest.get("version_number")
                if not download_url or not version_number:
                    continue
                deps   = []
                for dep in latest.get("dependencies") or []:
                    if not isinstance(dep, str):
                        continue
                    parts = dep.split("-")
                    if len(parts) >= 2:
                        deps.append(f"{parts[0]}-{parts[1]}")
                mod_id = f"{owner}-{name}"
                if mod_id in seen_ids:
                    continue
                seen_ids.add(mod_id)
                mods.append({
                    "id":           mod_id,
                    "name":         name,
                    "author":       owner,
                    "version":      version_number,
                    "description":  latest.get("description", ""),
                    "download_url": download_url,
                    "package_url":  f"https://thunderstore.io/c/{community}/p/{owner}/{name}/",
                    "icon":         latest.get("icon") or latest.get("icon_url") or pkg.get("icon") or pkg.get("image"),
                    "dependencies": deps,
                    "source":       "thunderstore",
                    "files": [{
                        "url":         download_url,
                        "filename":    f"{name}.zip",
                        "destination": cfg["mod_dest"],
                        "extract":     True,
                    }],
                })

            if isinstance(data, list):
                break
            next_url = data.get("next")
            if next_url and next_url.startswith("/"):
                next_url = f"https://thunderstore.io{next_url}"
            elif not next_url:
                page += 1
                next_url = f"https://thunderstore.io/c/{community}/api/v1/package/?page={page}"
            else:
                page += 1

        self._thunderstore_listing_cache[game_key] = {"time": now, "mods": mods}
        return mods

    def invalidate_thunderstore_cache(self, game_key=None):
        if game_key is None:
            self._thunderstore_listing_cache.clear()
            return
        self._thunderstore_listing_cache.pop(game_key, None)

    def install_mod_thunderstore(self, game_key, mod, game_install_dir, progress_cb=None):
        file_entry   = mod["files"][0]
        url          = self._resolve_file_url(file_entry)
        dest_rel     = file_entry["destination"]
        dest_dir     = os.path.join(game_install_dir, dest_rel)
        os.makedirs(dest_dir, exist_ok=True)

        buf = self._download_to_buffer(url, progress_cb=progress_cb, timeout=60)
        buf.seek(0)
        with zipfile.ZipFile(buf) as zf:
            planned_files = self._planned_archive_paths(zf, game_install_dir, dest_rel)
            self._check_file_conflicts(game_key, mod["id"], planned_files)
            zf.fp.seek(0)
            installed_files = self._extract_zip_to_game(zf, game_install_dir, dest_rel)

        if game_key not in self.installed:
            self.installed[game_key] = {}

        self.installed[game_key][mod["id"]] = {
            "name":    mod["name"],
            "version": mod["version"],
            "files":   installed_files,
            "enabled": True,
        }
        self._save_installed()

    def check_for_app_update(self):
        url = f"https://api.github.com/repos/{MOXI_REPO}/releases/latest"
        r   = requests.get(url, timeout=8)
        r.raise_for_status()
        data      = r.json()
        tag       = data.get("tag_name", "").lstrip("v")
        changelog = data.get("body", "")
        assets    = data.get("assets", [])
        dl_url    = None
        for asset in assets:
            if asset["name"].startswith("Moxi-v") and asset["name"].endswith("-Installer.exe"):
                dl_url = asset["browser_download_url"]
                break
        return tag, changelog, dl_url

    def download_installer(self, dl_url, version, progress_cb=None):
        updates_dir = os.path.join(DATA_DIR, "updates")
        os.makedirs(updates_dir, exist_ok=True)
        dest = os.path.join(updates_dir, f"Moxi-v{version}-Installer.exe")

        r     = requests.get(dl_url, stream=True, timeout=120)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done  = 0

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb and total > 0:
                        progress_cb(done / total)
        return dest

    def load_dismissed_warnings(self):
        path = os.path.join(DATA_DIR, "dismissed_warnings.json")
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    return set(json.load(f))
        except Exception:
            pass
        return set()

    def save_dismissed_warnings(self, dismissed):
        path = os.path.join(DATA_DIR, "dismissed_warnings.json")
        try:
            with open(path, "w") as f:
                json.dump(list(dismissed), f)
        except Exception:
            pass

    def write_updated_flag(self, version, changelog):
        path = os.path.join(DATA_DIR, "updated.json")
        with open(path, "w") as f:
            json.dump({"version": version, "changelog": changelog}, f, indent=2)

    def read_and_clear_updated_flag(self):
        path = os.path.join(DATA_DIR, "updated.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
            os.remove(path)
            return data
        except Exception:
            return None

    def resolve_dependencies(self, game_key, mod, all_mods):
        mod_by_id = {m["id"]: m for m in all_mods}
        resolved  = []
        visited   = set()

        def walk(m):
            mid = m["id"]
            if mid in visited:
                return
            visited.add(mid)
            for dep_id in m.get("dependencies", []):
                if dep_id in mod_by_id:
                    walk(mod_by_id[dep_id])
            if not self.is_installed(game_key, mid) and mid != mod["id"]:
                resolved.append(m)

        walk(mod)
        return resolved

    def is_installed(self, game_key, mod_id):
        return self.installed.get(game_key, {}).get(mod_id) is not None

    def install_mod(self, game_key, mod, game_install_dir, progress_cb=None):
        files = mod.get("files", [])
        installed_files = []
        self._log_debug(
            f"install_mod start game_key={game_key} mod_id={mod.get('id')} "
            f"file_count={len(files)} install_dir={game_install_dir!r}"
        )

        for i, file_entry in enumerate(files):
            try:
                url = self._resolve_file_url(file_entry)
                filename = file_entry["filename"]
                dest_rel = file_entry["destination"]
                dest_dir = os.path.join(game_install_dir, dest_rel)
                os.makedirs(dest_dir, exist_ok=True)
                dest_path = os.path.join(dest_dir, filename)
                self._log_debug(
                    f"install_mod file index={i} url={url!r} filename={filename!r} "
                    f"destination={dest_rel!r} extract={bool(file_entry.get('extract'))} "
                    f"include_prefix={file_entry.get('include_prefix')!r}"
                )

                if file_entry.get("extract"):
                    cache_key = url if mod.get("source") == "github" else None

                    def step_progress(val, index=i, total_files=len(files)):
                        if progress_cb:
                            progress_cb((index + val) / total_files)

                    buf = self._download_to_buffer(url, progress_cb=step_progress, timeout=30, cache_key=cache_key)
                    buf.seek(0)
                    with zipfile.ZipFile(buf) as zf:
                        include_prefix = file_entry.get("include_prefix")
                        effective_prefix = include_prefix
                        planned_files = self._planned_archive_paths(
                            zf,
                            game_install_dir,
                            dest_rel,
                            effective_prefix,
                        )
                        if effective_prefix and not planned_files:
                            self._log_debug(
                                f"install_mod include_prefix matched no files, falling back to full archive mod_id={mod.get('id')} "
                                f"include_prefix={effective_prefix!r}"
                            )
                            effective_prefix = None
                            planned_files = self._planned_archive_paths(
                                zf,
                                game_install_dir,
                                dest_rel,
                                effective_prefix,
                            )
                        self._log_debug(
                            f"install_mod planned_files mod_id={mod.get('id')} count={len(planned_files)} "
                            f"sample={planned_files[:5]!r}"
                        )
                        if not planned_files:
                            raise ValueError("Archive extraction matched no files.")
                        self._check_file_conflicts(game_key, mod["id"], planned_files)
                        zf.fp.seek(0)
                        subset_files = self._extract_zip_subset_to_game(
                            zf,
                            game_install_dir,
                            dest_rel,
                            effective_prefix,
                        )
                    if not subset_files:
                        raise ValueError("Archive extraction produced no files.")
                    self._log_debug(
                        f"install_mod extracted_files mod_id={mod.get('id')} count={len(subset_files)} "
                        f"sample={subset_files[:5]!r}"
                    )
                    installed_files.extend(subset_files)
                else:
                    r = self._session.get(url, stream=True, timeout=30)
                    r.raise_for_status()
                    total = int(r.headers.get("content-length", 0))
                    downloaded = 0
                    self._check_file_conflicts(game_key, mod["id"], [dest_path])
                    with open(dest_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_cb and total > 0:
                                    progress_cb((i + downloaded / total) / len(files))

                    installed_files.append(dest_path)
                    self._log_debug(f"install_mod copied_file path={dest_path!r}")
            except Exception as exc:
                self._log_debug(
                    f"install_mod failed game_key={game_key} mod_id={mod.get('id')} "
                    f"file_index={i} error={exc!r}"
                )
                raise

        if game_key not in self.installed:
            self.installed[game_key] = {}

        self.installed[game_key][mod["id"]] = {
            "name":    mod["name"],
            "version": mod["version"],
            "files":   installed_files,
            "enabled": True,
        }
        self._save_installed()
        self._log_debug(
            f"install_mod complete game_key={game_key} mod_id={mod.get('id')} installed_count={len(installed_files)}"
        )

    def uninstall_mod(self, game_key, mod_id):
        entry = self.installed.get(game_key, {}).get(mod_id)
        if not entry:
            return

        for path in entry.get("files", []):
            for candidate in [path, path + ".disabled"]:
                if os.path.exists(candidate):
                    try:
                        os.remove(candidate)
                    except Exception:
                        pass

        del self.installed[game_key][mod_id]
        self._save_installed()

    def _ue4ss_mod_root(self, game_key, entry):
        """
        For UE4SS-format mods, locate the mod's root folder (Mods/<ModName>)
        and the Mods/ directory it lives in, derived from the mod's tracked
        files and the game's configured mod_dest. Returns
        (mod_root_dir, mod_folder, mods_dir) or None if it can't be determined.
        """
        cfg = MODLOADER_CONFIGS.get(game_key, {})
        dest_parts = [p for p in cfg.get("mod_dest", "").replace("\\", "/").split("/") if p]
        if not dest_parts:
            return None

        lower_dest = [p.lower() for p in dest_parts]

        for path in entry.get("files", []):
            parts = os.path.normpath(path).split(os.sep)
            lower_parts = [p.lower() for p in parts]
            for i in range(len(parts) - len(lower_dest)):
                if lower_parts[i:i + len(lower_dest)] == lower_dest:
                    mod_folder_idx = i + len(lower_dest)
                    mods_dir   = os.sep.join(parts[:mod_folder_idx])
                    mod_folder = parts[mod_folder_idx]
                    mod_root_dir = os.path.join(mods_dir, mod_folder)
                    return mod_root_dir, mod_folder, mods_dir

        return None

    def _toggle_ue4ss_enabled_txt(self, mod_root_dir, enable):
        """
        Toggle a UE4SS Lua mod on/off via enabled.txt, which "bypasses load
        order control" per UE4SS docs - i.e. its presence enables the mod
        regardless of mods.txt. We rename it to enabled.txt.disabled when
        disabling (preserving it for re-enable), and create an empty one on
        enable if the mod never shipped with one.
        """
        enabled_path  = os.path.join(mod_root_dir, "enabled.txt")
        disabled_path = enabled_path + ".disabled"

        if enable:
            if os.path.exists(enabled_path):
                return
            if os.path.exists(disabled_path):
                os.rename(disabled_path, enabled_path)
            else:
                os.makedirs(mod_root_dir, exist_ok=True)
                open(enabled_path, "w", encoding="utf-8").close()
        else:
            if not os.path.exists(enabled_path):
                return
            if os.path.exists(disabled_path):
                os.remove(disabled_path)
            os.rename(enabled_path, disabled_path)

    def _set_ue4ss_mods_txt_entry(self, mods_dir, mod_folder, enable):
        """
        Update an existing Mods/mods.txt entry for this mod, if mods.txt
        already exists. We never create mods.txt ourselves - UE4SS generates
        it with required built-in entries (e.g. Keybinds) on first launch,
        and writing a partial file before that could break those defaults.
        New entries are inserted before any "Keybinds" line, since UE4SS
        requires built-in keybind entries to stay at the bottom of the file.
        """
        mods_txt_path = os.path.join(mods_dir, "mods.txt")
        if not os.path.exists(mods_txt_path):
            return

        try:
            with open(mods_txt_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except Exception as exc:
            self._log_debug(f"_set_ue4ss_mods_txt_entry read failed path={mods_txt_path!r} error={exc!r}")
            return

        new_line = f"{mod_folder} : {1 if enable else 0}"
        pattern  = re.compile(r"^\s*" + re.escape(mod_folder) + r"\s*:\s*\d+", re.IGNORECASE)
        keybind_idx = None
        replaced = False

        for i, line in enumerate(lines):
            code = line.split(";", 1)[0]
            if pattern.match(code):
                lines[i] = new_line
                replaced = True
                break
            if keybind_idx is None and re.match(r"^\s*Keybinds\s*:", code, re.IGNORECASE):
                keybind_idx = i

        if not replaced:
            if keybind_idx is not None:
                lines.insert(keybind_idx, new_line)
            else:
                lines.append(new_line)

        try:
            with open(mods_txt_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + ("\n" if lines else ""))
        except Exception as exc:
            self._log_debug(f"_set_ue4ss_mods_txt_entry write failed path={mods_txt_path!r} error={exc!r}")

    def _refresh_ue4ss_enabled_txt_tracking(self, entry, mod_root_dir):
        """
        Keep entry['files'] in sync with whichever of enabled.txt /
        enabled.txt.disabled currently exists on disk, so uninstall and
        future toggles find the right file.
        """
        enabled_path  = os.path.join(mod_root_dir, "enabled.txt")
        disabled_path = enabled_path + ".disabled"
        tracked = {
            os.path.normcase(os.path.normpath(enabled_path)),
            os.path.normcase(os.path.normpath(disabled_path)),
        }

        files = [
            f for f in entry.get("files", [])
            if os.path.normcase(os.path.normpath(f)) not in tracked
        ]

        if os.path.exists(enabled_path):
            files.append(enabled_path)
        elif os.path.exists(disabled_path):
            files.append(disabled_path)

        entry["files"] = files

    def _set_ue4ss_mod_state(self, game_key, entry, enable):
        root_info = self._ue4ss_mod_root(game_key, entry)
        if not root_info:
            self._log_debug(
                f"_set_ue4ss_mod_state: could not determine mod root for "
                f"game_key={game_key!r} files={entry.get('files', [])!r}"
            )
            return

        mod_root_dir, mod_folder, mods_dir = root_info

        try:
            self._toggle_ue4ss_enabled_txt(mod_root_dir, enable)
        except Exception as exc:
            self._log_debug(f"_set_ue4ss_mod_state enabled.txt toggle failed: {exc!r}")

        try:
            self._set_ue4ss_mods_txt_entry(mods_dir, mod_folder, enable)
        except Exception as exc:
            self._log_debug(f"_set_ue4ss_mod_state mods.txt update failed: {exc!r}")

        self._refresh_ue4ss_enabled_txt_tracking(entry, mod_root_dir)

    def enable_mod(self, game_key, mod_id):
        entry = self.installed.get(game_key, {}).get(mod_id)
        if not entry:
            return

        if MODLOADER_CONFIGS.get(game_key, {}).get("mod_format") == "ue4ss":
            self._set_ue4ss_mod_state(game_key, entry, True)
            entry["enabled"] = True
            self._save_installed()
            return

        updated = []
        for path in entry.get("files", []):
            if path.endswith(".disabled"):
                enabled_path = path[:-len(".disabled")]
                if os.path.exists(path):
                    os.rename(path, enabled_path)
                updated.append(enabled_path)
            else:
                updated.append(path)
        entry["files"]   = updated
        entry["enabled"] = True
        self._save_installed()

    def disable_mod(self, game_key, mod_id):
        entry = self.installed.get(game_key, {}).get(mod_id)
        if not entry:
            return

        if MODLOADER_CONFIGS.get(game_key, {}).get("mod_format") == "ue4ss":
            self._set_ue4ss_mod_state(game_key, entry, False)
            entry["enabled"] = False
            self._save_installed()
            return

        updated = []
        for path in entry.get("files", []):
            if path.endswith(".dll") and os.path.exists(path):
                disabled = path + ".disabled"
                os.rename(path, disabled)
                updated.append(disabled)
            else:
                updated.append(path)
        entry["files"]   = updated
        entry["enabled"] = False
        self._save_installed()

    def _config_tokens_for_mod(self, game_key, mod_id):
        entry = self.installed.get(game_key, {}).get(mod_id, {})
        tokens = set()
        ignored = {
            "mod", "plugin", "config", "version", "number", "game", "settings",
            "the", "and", "for", "with", "from", "file",
        }

        def add_token(value):
            if not value:
                return
            normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
            for part in normalized.split():
                if len(part) >= 3 and part not in ignored:
                    tokens.add(part)

        add_token(mod_id)
        add_token(entry.get("name", ""))
        add_token(entry.get("author", ""))

        for path in entry.get("files", []):
            base = os.path.basename(path)
            if base.endswith(".disabled"):
                base = base[:-len(".disabled")]
            stem, ext = os.path.splitext(base)
            if ext.lower() == ".dll":
                add_token(stem)

        return tokens

    def _config_match_data_for_mod(self, game_key, mod_id):
        entry = self.installed.get(game_key, {}).get(mod_id, {})
        tokens = self._config_tokens_for_mod(game_key, mod_id)
        exact_names = set()

        def add_exact(value):
            if not value:
                return
            normalized = re.sub(r"[^a-z0-9]+", "", value.lower())
            if len(normalized) >= 3:
                exact_names.add(normalized)

        add_exact(mod_id)
        add_exact(entry.get("name", ""))

        for path in entry.get("files", []):
            base = os.path.basename(path)
            if base.endswith(".disabled"):
                base = base[:-len(".disabled")]
            stem, ext = os.path.splitext(base)
            if ext.lower() == ".dll":
                add_exact(stem)

        return tokens, exact_names

    def get_mod_config_path(self, game_key, mod_id, game_install_dir):
        search_cfg = CONFIG_SEARCH_CONFIGS.get(game_key, {})
        config_dir = os.path.join(
            game_install_dir,
            *(search_cfg.get("dir_parts") or ("BepInEx", "config")),
        )
        if not os.path.isdir(config_dir):
            return None

        extensions = tuple(ext.lower() for ext in (search_cfg.get("extensions") or (".cfg", ".config", ".ini", ".txt")))
        exclude_substrings = tuple(part.lower() for part in (search_cfg.get("exclude_substrings") or ()))

        if search_cfg.get("recursive"):
            candidates = []
            for root, _, files in os.walk(config_dir):
                for name in files:
                    lower_name = name.lower()
                    if not lower_name.endswith(extensions):
                        continue
                    if any(part in lower_name for part in exclude_substrings):
                        continue
                    candidates.append(os.path.join(root, name))
        else:
            candidates = [
                os.path.join(config_dir, name)
                for name in os.listdir(config_dir)
                if name.lower().endswith(extensions)
                and not any(part in name.lower() for part in exclude_substrings)
            ]
        if not candidates:
            return None

        tokens, exact_names = self._config_match_data_for_mod(game_key, mod_id)
        if not tokens and not exact_names:
            return None

        min_score = int(search_cfg.get("min_score", 20))
        best_path = None
        best_score = 0
        for path in candidates:
            name = os.path.basename(path).lower()
            filename_stem = re.sub(r"[^a-z0-9]+", "", os.path.splitext(name)[0].lower())
            score = 0

            if filename_stem in exact_names:
                score += 100
            else:
                for exact in exact_names:
                    if exact and exact in filename_stem:
                        score += 35

            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    header = f.read(2048).lower()
            except Exception:
                header = ""

            guid_match = re.search(r"plugin guid:\s*([^\r\n]+)", header)
            if guid_match:
                guid_value = re.sub(r"[^a-z0-9]+", "", guid_match.group(1).lower())
                if guid_value in exact_names:
                    score += 140
                else:
                    for exact in exact_names:
                        if exact and exact in guid_value:
                            score += 55

            plugin_match = re.search(r"created by plugin\s+([^\r\n]+)", header)
            if plugin_match:
                plugin_value = plugin_match.group(1).lower()
                for exact in exact_names:
                    if exact and exact in re.sub(r"[^a-z0-9]+", "", plugin_value):
                        score += 70

            for token in tokens:
                if token in name:
                    score += 8 if name.startswith(token) else 2
                if token in header:
                    score += 3
            if score > best_score:
                best_score = score
                best_path = path

        return best_path if best_score >= min_score else None

    def read_text_file(self, path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def write_text_file(self, path, text):
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def import_thunderstore_modpack(self, community, code):
        """
        Resolve a Thunderstore profile share code.
        Returns the decoded profile name and a list of mod dicts compatible with
        the existing mod format.
        """
        code = self._extract_share_code(code)
        raw = self._load_thunderstore_profile_manifest(code)

        profile_name, mod_entries = self._parse_thunderstore_manifest(raw)
        if not mod_entries:
            raise ValueError("That share code decoded, but no enabled mods were found in the profile.")

        cfg      = self._get_thunderstore_config(community)
        mod_dest = cfg.get("mod_dest", os.path.join("BepInEx", "plugins"))
        mods     = []

        for entry in mod_entries:
            owner = entry["owner"]
            name = entry["name"]
            version_str = entry.get("version")

            try:
                api_url = f"https://thunderstore.io/c/{community}/api/v1/package/{owner}/{name}/"
                r       = requests.get(api_url, timeout=10)
                if not r.ok:
                    continue
                pkg_data = r.json()
                versions = pkg_data.get("versions", [])
                version  = next((v for v in versions if v["version_number"] == version_str), None) if version_str else None
                if not version and versions:
                    version = versions[0]
                if not version:
                    continue

                deps = []
                for dep in version.get("dependencies", []):
                    dp = dep.split("-")
                    if len(dp) >= 2:
                        deps.append(f"{dp[0]}-{dp[1]}")

                mods.append({
                    "id":           f"{owner}-{name}",
                    "name":         name,
                    "author":       owner,
                    "version":      version["version_number"],
                    "description":  version.get("description", ""),
                    "download_url": version["download_url"],
                    "dependencies": deps,
                    "source":       "thunderstore",
                    "files": [{
                        "url":         version["download_url"],
                        "filename":    f"{name}.zip",
                        "destination": mod_dest,
                        "extract":     True,
                    }],
                })
            except Exception:
                continue

        return profile_name, mods


class SteamScanner:
    def __init__(self, supported_games: dict):
        self.supported = supported_games

    def scan(self):
        steamapps_paths = self._find_steamapps_dirs()
        found = []

        for sa_path in steamapps_paths:
            for appid, entry in self.supported.items():
                acf_path = os.path.join(sa_path, f"appmanifest_{appid}.acf")
                if os.path.exists(acf_path):
                    install_name = self._parse_install_dir(acf_path)
                    install_dir  = os.path.join(sa_path, "common", install_name) if install_name else None
                    found.append({
                        "appid":       appid,
                        "name":        entry["name"],
                        "supported":   entry["supported"],
                        "game_key":    entry.get("game_key", ""),
                        "acf_path":    acf_path,
                        "install_dir": install_dir,
                    })

        seen   = set()
        unique = []
        for item in found:
            if item["appid"] not in seen:
                seen.add(item["appid"])
                unique.append(item)

        return unique

    def _parse_install_dir(self, acf_path):
        try:
            with open(acf_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            m = re.search(r'"installdir"\s+"([^"]+)"', content)
            return m.group(1) if m else None
        except Exception:
            return None

    def _find_steamapps_dirs(self):
        candidates = []
        steam_root  = self._steam_root_from_registry() or self._steam_root_fallback()

        if steam_root:
            default_sa = os.path.join(steam_root, "steamapps")
            if os.path.isdir(default_sa):
                candidates.append(default_sa)
            vdf_path = os.path.join(default_sa, "libraryfolders.vdf")
            if os.path.exists(vdf_path):
                for p in self._parse_libraryfolders(vdf_path):
                    sa = os.path.join(p, "steamapps")
                    if os.path.isdir(sa) and sa not in candidates:
                        candidates.append(sa)

        if not candidates:
            candidates = self._brute_force_scan()

        return candidates

    def _steam_root_from_registry(self):
        try:
            import winreg
            key  = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")
            path, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)
            if os.path.isdir(path):
                return path
        except Exception:
            pass
        try:
            import winreg
            key  = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam")
            path, _ = winreg.QueryValueEx(key, "SteamPath")
            winreg.CloseKey(key)
            path = path.replace("/", "\\")
            if os.path.isdir(path):
                return path
        except Exception:
            pass
        return None

    def _steam_root_fallback(self):
        for p in [
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Steam"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Steam"),
        ]:
            if os.path.isdir(p):
                return p
        return None

    def _brute_force_scan(self):
        candidates = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if not os.path.exists(drive):
                continue
            for fragment in [
                os.path.join(drive, "Program Files (x86)", "Steam", "steamapps"),
                os.path.join(drive, "Program Files", "Steam", "steamapps"),
                os.path.join(drive, "Steam", "steamapps"),
                os.path.join(drive, "SteamLibrary", "steamapps"),
            ]:
                if os.path.isdir(fragment) and fragment not in candidates:
                    candidates.append(fragment)
        return candidates

    def _parse_libraryfolders(self, vdf_path):
        paths = []
        try:
            with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for m in re.findall(r'"path"\s+"([^"]+)"', content):
                p = m.replace("\\\\", "\\")
                if os.path.isdir(p):
                    paths.append(p)
        except Exception:
            pass
        return paths


class GameAdapter:
    def get_install_path(self):
        raise NotImplementedError

    def get_plugins_path(self):
        raise NotImplementedError


class PlanetCrafterAdapter(GameAdapter):
    def __init__(self, install_dir):
        self.install_dir = install_dir

    def get_install_path(self):
        return self.install_dir

    def get_plugins_path(self):
        return os.path.join(self.install_dir, "BepInEx", "plugins")