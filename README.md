# Xeneon Dashboard

Touch-screen light control dashboard for the Corsair Xeneon Edge, served via Cloudflare tunnel with a permanent HTTPS URL.

**Live URL:** `https://xeneon.mordasin.com/lights.html`

---

## First-Time Setup (Windows PC)

### Prerequisites
- Python installed and on PATH
- `cloudflared.exe` in the repo folder (download from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
- `mordasin.com` added to your Cloudflare account ✅

### One-time setup (run once, as Administrator)

```
setup_autostart.bat
```

This script will:
1. Log you into Cloudflare via browser
2. Create a named tunnel called `xeneon`
3. **Pause and ask you to edit `cloudflared-config.yml`** — fill in your Tunnel ID and Windows username
4. Create the `xeneon.mordasin.com` DNS record on Cloudflare
5. Register Task Scheduler tasks that auto-start on every login

### After setup
- Reboot → everything starts automatically
- Dashboard live at `https://xeneon.mordasin.com/lights.html`
- Add to iCUE as a **Web URL widget (XL)**

---

## Manual Start / Stop

```
start_server.bat   ← starts server + tunnel
stop_server.bat    ← kills both
```

---

## Pulling Updates

```
cd C:\xeneon-dashboard
git pull
```

Then restart via `stop_server.bat` → `start_server.bat`.

---

## Architecture

```
Xeneon Edge (iCUE Web URL widget)
    │ HTTPS
    ▼
xeneon.mordasin.com  (Cloudflare named tunnel)
    │ HTTP
    ▼
server.py :8080  (Python HTTP server on Windows PC)
    │ HTTP + Bearer token
    ▼
Home Assistant :8123  (192.168.1.30)
```

- `server.py` — proxies `/api/*` to Home Assistant with auth token (token never sent to browser)
- `tunnel.py` — runs `cloudflared tunnel run` for the named `xeneon` tunnel
- `cloudflared-config.yml` — tunnel config (edit after `tunnel create`)
- `lights.html` — Kitchen + Lounge dashboard

---

## iCUE Widget Settings

- Type: **Web URL**
- Size: **XL**
- URL: `https://xeneon.mordasin.com/lights.html`

---

## Rooms

| Room | Entities |
|------|---------|
| Kitchen | light.kitchen2, light.kitchen3, light.kitchen4, light.kitchen5, light.signify_netherlands_b_v_lca007_3 |
| Lounge | light.lounge1 – light.lounge6 |
