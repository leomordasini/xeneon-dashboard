# Xeneon Dashboard

Custom dashboards for the Corsair Xeneon Edge touch screen — served locally from your Windows PC and displayed via the iCUE **Web URL** widget.

## Dashboards

| File | URL | Description |
|---|---|---|
| `lights.html` | `http://192.168.1.148:8080/lights.html` | Kitchen + Lounge light control (HA) |

---

## Architecture

```
Windows PC (192.168.1.148)
  └── server.py :8080
        ├── GET /lights.html  → serves static file
        └── /api/*            → proxies to HA at 192.168.1.30:8123
                                (adds auth token, handles CORS)
              ↓
Xeneon Edge — Web URL widget → http://192.168.1.148:8080/lights.html
```

---

## Setup (one time)

### 1. Install Python
Download from https://python.org — check **"Add Python to PATH"** during install.

### 2. Clone this repo
```
git clone https://github.com/leomordasini/xeneon-dashboard.git C:\xeneon-dashboard
```

### 3. Run autostart setup (once, as Administrator)
Right-click `setup_autostart.bat` → **Run as administrator**

This registers the server to start silently on every Windows login.

### 4. Add Web URL widget in iCUE
- iCUE → Xeneon Edge → Widgets → **Web URL** → Size: **XL**
- URL: `http://192.168.1.148:8080/lights.html`

---

## Updating dashboards

Whenever I push a change to this repo:

```bash
cd C:\xeneon-dashboard
git pull
```

No restart needed — the server serves files fresh on each request.

---

## Manual server control

| Script | Action |
|---|---|
| `start_server.bat` | Start manually (for testing) |
| `stop_server.bat`  | Kill the server |
| `setup_autostart.bat` | Register auto-start on login (run once as Admin) |

---

## Files

```
xeneon-dashboard/
├── server.py              ← HTTP server + HA proxy
├── lights.html            ← Kitchen & Lounge light dashboard
├── setup_autostart.bat    ← One-time auto-start registration
├── start_server.bat       ← Manual start
├── stop_server.bat        ← Manual stop
└── README.md
```
