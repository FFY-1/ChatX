# ChatX 🔒

[![Download](https://img.shields.io/badge/Download-v1.0.0-blue)](https://github.com/FFY/ChatX/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.7+-green?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

<img src="https://cdn-icons-png.magnific.com/512/14562/14562316.png?ga=GA1.1.358465600.1783507656" width="64" align="right">

> Terminal-based encrypted LAN chat — zero deps beyond Python.

```
╔══════════════════════════════╗
║         ChatX v1.0          ║
╚══════════════════════════════╝

📁 My Rooms:
  👥 dev-chat
  👤 alice [private]
🔍 Discovered:
  🔓 (G) python-study (3) — bob
  🔑 (G) gaming (5) — charlie
─────────────────────────────────
 (G) dev-chat | 10 members | 8 online
```

## Features

- 🔒 **E2E Encryption** — Fernet (AES-128-CBC) via `cryptography`
- 📡 **LAN Discovery** — UDP broadcast, no central server
- 🏠 **Rooms** — create, join, leave; public / password / passkey auth
- 👥 **Multi-room** — switch between joined rooms without leaving
- 📎 **File Transfer** — `/file path` to send files
- 🎨 **TUI** — curses-based with ANSI colors & mouse support
- 📏 **Responsive** — adapts to terminal size

## Install

### Download (Windows)

[**ChatX.exe**](https://github.com/FFY/ChatX/releases/latest) — standalone, no Python required.

### From source

```bash
git clone https://github.com/FFY/ChatX.git
cd ChatX
pip install -r requirements.txt
python chatx.py
```

## Usage

| Key | Action |
|-----|--------|
| `↑` `↓` | Navigate rooms |
| `Enter` | Join selected room |
| `N` | Create new room |
| `Esc` | Back / Leave room |
| `Q` | Quit |
| `PgUp` `PgDn` | Scroll chat |
| `/file path` | Send file |

## How It Works

1. Each instance **broadcasts** room info via UDP (`255.255.255.255:50000`)
2. Other instances **discover** rooms and display them
3. Joining a room establishes a **TCP** connection (`50001–50100`)
4. Messages are **encrypted** with a per-room Fernet key

## Requirements

- Python ≥ 3.7
- `cryptography`
- `windows-curses` (Windows only)

## License

MIT
