# Observer deploy on the map-server (backbone)

Target: `dsolovev@192.168.80.127:20022` (Ubuntu, python3.14). Channel = `srv.py` exec (SSH:22 closed; SFTP off -> files via exec-channel; playbook L37/L38). Verified: Forgejo local API 200, GitHub reachable 200, `/opt/{forgejo,map}`, Caddyfile present.

Observer is **read-only** (no board writes, no bot launches). Live deploy changes state on the PRODUCTION server (also hosts `map.service` + Forgejo) -> do with care and explicit confirmation.

## 1. Code on server
Bots is private -> clone with token in URL, then strip it:
```
sudo mkdir -p /opt/observer && sudo chown dsolovev:dsolovev /opt/observer
git clone https://x-access-token:<GH_PAT>@github.com/sdim7-hue/Bots.git /opt/observer/src
git -C /opt/observer/src remote set-url origin https://github.com/sdim7-hue/Bots.git
```
Update later: `git -C /opt/observer/src pull`.

## 2. Secrets
`cp deploy/observer.env.example /etc/observer.env`, fill, `chmod 600`, `chown dsolovev`.
- `GITHUB_TOKEN` reads Bots; `FORGEJO_TOKEN` reads map/zvuk (local Forgejo).
- `TELEGRAM_*` / `SMTP_*` optional; a channel auto-enables when its vars are present.

## 3. systemd
```
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
```
Smoke FIRST (manual, no services):
```
cd /opt/observer/src && set -a && . /etc/observer.env && set +a
python3 -m observer collect-once   # writes snapshot, NO board mutation
python3 -m observer notify-dry     # prints events to console
```
Then: `sudo systemctl enable --now observer-loop observer-dash`.

## 4. Dashboard access (pick one)
- **(a) Recommended first:** SSH-tunnel to `127.0.0.1:8787` (no Caddy change, no subpath issues) via the operator/relay path.
- **(b) Caddy `/ops/`:** see `deploy/caddy-ops.snippet` -- only after a base-path tweak; validate + backup + reload; never touch the map `/` or `/git/` blocks.

## Notes
- python3.14 on server; observer is stdlib-only -> OK.
- map/zvuk Forgejo queues are currently EMPTY (no bot workflow yet) -> observer shows 0 tasks for them until status-labeled issues exist. Bots queue is live.
- Read-only guarantee: only `list_issues_by_label`/`get_issue` calls; the single outbound POST is to Telegram's API.
