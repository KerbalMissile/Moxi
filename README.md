# Moxi ![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/KerbalMissile/Moxi/total?color=FF0051)

<img width="512" height="512" alt="MoxiLogo" src="https://github.com/user-attachments/assets/bafad4ee-7787-431a-90fc-c035537c36b6" />

A lightweight mod manager for PC games, currently on Steam games are supported. No accounts, no ads, no bloat. Just install mods and play.

Moxi detects your Steam games automatically, pulls mods from a curated index, handles dependencies, and installs everything in the right place. If a game needs a mod loader like BepInEx, Moxi installs that too.

---

## Links

- Website: https://kerbalmissile.github.io/MoxiWebsite/
- Discord: https://discord.com/invite/Y53vwvQRDc
- Releases: https://github.com/KerbalMissile/Moxi/releases

---

## Supported Games

| Game | Status |
|------|--------|
| Planet Crafter | Supported |
| Subnautica | Supported |
| Subnautica 2 | Supported|
| Subnautica: Below Zero | Supported |
| Slime Rancher | Supported |
| Slime Rancher 2 | Supported |
| Dyson Sphere Program | Supported |
| Valheim | Supported |
| Scrap Mechanic | Supported |
| Muck | Supported |
| Risk of Rain 2 | Supported |
| PEAK | Supported |
| Schedule I | Supported |
| BONELAB | Supported |
| BONEWORKS | Supported |
| Out of Ore | Supported |
| Railroads ONLINE | Supported |
| Easy Delivery Co. | Supported |
| Lakehopper | Supported - No Mods / Mod Loaders Released Yet | 

---

## Features

**Automatic game detection** - Moxi scans your Steam libraries across all drives and finds supported games without you having to point it anywhere.

**Mod loader management** - If BepInEx, SRML, or MelonLoader is not installed for a game, Moxi will offer to install it before installing any mods.

**Dependency resolution** - If a mod requires another mod, Moxi detects this automatically and asks you to confirm before installing the full chain.

**Enable and disable mods** - Toggle mods on or off without uninstalling them. Disabled mods are renamed in place and ignored by the game until re-enabled.

**Recently played** - Games you launch from Moxi are tracked so your most-used games are always one click away.

**Automatic update checks** - Moxi checks for new versions on startup and notifies you when one is available.

---

## Installation

Download the latest installer from the [releases page](https://github.com/KerbalMissile/Moxi/releases/latest) and run it. No additional setup required.

**System requirements:**
- Windows 10 or 11
- Internet connection for mod downloads

---

**Incompatibilies:**
- Norton (Norton CyberCapture causes crashes)

---

## For Mod Authors

Mods are distributed through a JSON index hosted in this repository. To add your mod, create an entry in `Mods/ModIndex.json` following this structure:

```json
{
  "id": "your_mod_id",
  "name": "Your Mod Name",
  "author": "YourName",
  "version": "1.0.0",
  "description": "A short description of what your mod does.",
  "dependencies": ["other_mod_id"],
  "files": [
    {
      "url": "https://github.com/you/your-repo/raw/main/YourMod.dll",
      "filename": "YourMod.dll",
      "destination": "BepInEx/plugins"
    }
  ]
}
```

The `dependencies` field is optional. If your mod requires another mod that is already in the index, list its `id` here and Moxi will handle the install order automatically.

File downloads must be direct URLs - GitHub raw file links work well for this. If your mod ships multiple files, add each one as a separate entry in the `files` array.

Once your entry is added and the index is updated, the mod will appear in Moxi without any app update required.

---

## Data Storage

Moxi stores all local data in `%LOCALAPPDATA%\Moxi\`:

- `installed.json` - tracks which mods are installed and where
- `recently_played.json` - stores your recently played game history
- `updates\` - temporary folder used during app updates

You can open this folder directly from Settings inside the app, or clear the installed mods cache and recently played history from there as well.

---

## Coming Soon Games

Games listed in the Coming Soon section of the dashboard are managed through `Games/GameIndex.json` in this repository. Adding a new entry there will make it appear in the app without requiring users to update. Each entry looks like this:

```json
{
  "appid": "1234567",
  "name": "Game Name",
  "coming_date": "April 1st"
}
```

---

## Built With

- Python 3.14.6 (Pre 2.6.x versions used 3.13)
- CustomTkinter
- Pillow
- Requests

---

## License

This project is open source under the GPL-3.0 License. See the LICENSE file for details.
