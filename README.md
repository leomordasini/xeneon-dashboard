# Xeneon Dashboard

Custom dashboards for the Corsair Xeneon Edge touch screen.
Served locally from your Windows PC via a Cloudflare tunnel (HTTPS).

## Dashboards

| File | Description |
|---|---|
| `lights.html` | Kitchen + Lounge light control via Home Assistant |

---

## Architecture

```
Windows PC (192.168.1.148)
  ├── server.py :8080      — HTTP server + HA API proxy
  └── tunnel.py            — cloudflared tunnel → public HTTPS URL
        ↓
  https://xxxx.trycloudflare.com
        ↓
  Xeneon Edge — Web URL widget XL
```

---

## First-Time Setup

### 1. Install Python
https://python.org — check **"Add Python to PATH"**

### 2. Install Git
https://git-scm.com/download/win

### 3. Clone repo
```powershell
git clone https://github.com/leomordasini/xeneon-dashboard.git C:\xeneon-dashboard
```

### 4. Download cloudflared
https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe

Save as: `C:\xeneon-dashboard\cloudflared.exe`

### 5. Run setup (as Administrator)
Right-click `setup_autostart.bat` → **Run as administrator**

This will:
- Start the dashboard server on port 8080
- Start the cloudflared tunnel
- Print the public HTTPS URL
- Register both to auto-start on every login

### 6. Add to iCUE
- Xeneon Edge → Web URL widget → Size **XL**
- URL: (the `https://xxxx.trycloudflare.com/lights.html` printed by setup)

---

## After Each Reboot

The tunnel URL changes each restart. Check:
```
C:\xeneon-dashboard\tunnel_url.txt
```
Update the iCUE widget URL with the new one.

> **Note:** To get a permanent URL, set up a free Cloudflare account
> and run: `cloudflared tunnel login`

---

## Updating Dashboards

When changes are pushed to this repo:
```powershell
cd C:\xeneon-dashboard
git pull
```
No restart needed.

---

## Manual Control

| Script | Action |
|---|---|
| `setup_autostart.bat` | First-time setup (run as Admin) |
| `start_server.bat` | Start server manually |
| `stop_server.bat` | Kill everything |

## Files

```
xeneon-dashboard/
├── server.py              — HTTP server + HA proxy
├── tunnel.py              — cloudflared tunnel manager
├── lights.html            — Kitchen & Lounge dashboard
├── setup_autostart.bat    — One-time setup (run as Admin)
├── start_server.bat       — Manual start
├── stop_server.bat        — Kill server + tunnel
├── cloudflared.exe        — Download separately (not in repo)
└── README.md
```
