# serve/ — the always-on Home Base server (M6)

The hub's prod path: a login LaunchAgent (`com.homebase.server`, RunAtLoad + KeepAlive)
runs the venv uvicorn on **:8000** whenever the Mac is up — no terminal. The backend serves
the built frontend from the same port (see `backend/app/main.py`), and `tailscale serve`
fronts it with HTTPS on the tailnet so the phone can reach it from anywhere — cellular
included — with nothing publicly exposed. Mirrors the M3 pattern in `sweeps/schedule/`.

## Install (one-time, then idempotent)

```sh
make setup && make build        # venv + frontend/dist
serve/install-server.sh         # writes + bootstraps the LaunchAgent
serve/install-server.sh status  # confirm it's running
```

The server binds **loopback only** (`127.0.0.1:8000`) — nothing listens on LAN or public
interfaces. Logs land in `backend/data/logs/launchd.log` (gitignored). After a frontend
change: `make build` (the server picks up `dist/` per request — no restart needed).

## Phone reach — Tailscale

One-time, with [Tailscale](https://tailscale.com) installed on the Mac and iPhone (same
tailnet):

```sh
tailscale serve --bg http://127.0.0.1:8000
tailscale serve status            # shows the https://<mac>.<tailnet>.ts.net URL
```

`serve --bg` persists across reboots. The HTTPS cert is automatic — and that secure
context is what lets the phone register the service worker (plain `http://<LAN-IP>`
never can).

## Install to home screen (iPhone)

Open the `https://<mac>.<tailnet>.ts.net` URL in Safari → Share → **Add to Home Screen**.
The hub opens standalone (no browser chrome), and the service worker keeps the last good
brief readable offline — honestly labeled, writes disabled (see `frontend/public/sw.js`).

## Wake the Mac for the morning sweep (optional)

launchd can't wake a sleeping Mac. If you want the 06:00 sweep + brief ready before you
wake the machine yourself, schedule a wake — **run the sudo yourself; the installer only
prints it**:

```sh
sudo pmset repeat wakeorpoweron MTWRFSU 05:55:00
pmset -g sched                    # confirm
```

A lid-closed Mac on battery can still sleep through; the phone then shows the cached
last brief with an "offline copy" banner — that residual gap is by design (M6 fork 4).

## Uninstall

```sh
serve/install-server.sh uninstall
tailscale serve --https=443 off   # if you want the proxy gone too
sudo pmset repeat cancel          # if you scheduled the wake
```
