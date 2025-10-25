# Deploying ics18tickets calendar


This document explains how to serve the generated ICS so people can subscribe to it at:

https://ics.example.com/ics/ics18tickets.ics

It includes two recommended approaches that work well with Nginx Proxy Manager (NPM) running in Docker: a simple static-file approach (recommended) and a small-hosted service approach. It also includes cleanup commands and troubleshooting steps.

## Prerequisites

- A VPS with root or sudo access (Ubuntu/Debian recommended).
- DNS A record for `ics.example.com` pointing at your VPS IP.
- Nginx Proxy Manager already running in Docker on the VPS (manages ports 80/443).
- The `ics18tickets` repo copied to the VPS (suggested path `/opt/ics18tickets`). The script `ics18tickets.py` generates `ics18tickets.ics` in that directory.

Note: this guide assumes NPM handles public TLS. If you prefer host nginx instead of NPM, use the previous instructions in the repo README instead.

---

## Recommended: static file + NPM proxy (simple & robust)

Overview: serve the generated ICS from the host filesystem and let Nginx Proxy Manager (NPM) proxy `ics.example.com` to a small host HTTP server that serves `/opt/ics18tickets`. A host cron job regenerates the ICS every Monday at 23:59.

1. Prepare project and venv (on the VPS):

```bash
sudo mkdir -p /opt/ics18tickets
sudo chown $USER:$USER /opt/ics18tickets
cd /opt/ics18tickets
# Put your repository files here (ics18tickets.py, requirements.txt)
python3 -m venv /opt/ics18tickets/venv
/opt/ics18tickets/venv/bin/pip install --upgrade pip
/opt/ics18tickets/venv/bin/pip install -r /opt/ics18tickets/requirements.txt

Configuration (config.yml)
----------------------------
The generator will look for a `config.yml` file next to the scripts. If present it is used to
build the films API URL. Create `/opt/ics18tickets/config.yml` (or edit the one in your repo) to
change the target site. Example:

```yaml
site: example.18tickets.it
scheme: https
api_path: /api/v2/films
address: "123 Example Street, Exampleville, EX 00000"
```

You can also add an `address` field which will be used as the event location when the ICS is
generated. If omitted, no location will be set on the events (the `LOCATION` property will be
absent from the generated ICS).

Notes:
- `site` may be either a bare host (as above) or a full URL (including scheme). If `site` is a
	full URL it will be used directly and `scheme` is ignored.
- The generator now requires a valid `config.yml` file. If `config.yml` is missing or malformed
	the generator will raise an error and exit — there is no embedded fallback. Make sure the file
	exists at `/opt/ics18tickets/config.yml` (or next to the scripts) before enabling cron/systemd.

Remember to install `PyYAML` in your venv (it's included in the example `requirements.txt`).

# run once to create the ICS file
/opt/ics18tickets/venv/bin/python ics18tickets.py
```

2. Serve the directory from the host (simple, recommended)

Run a tiny HTTP server on the host that serves `/opt/ics18tickets` on port 8085. You can run it via `systemd` (recommended) or as a background process for testing:

Quick test (temporary):

```bash
cd /opt/ics18tickets
python3 -m http.server 8085 --directory . &
# verify
curl -I http://127.0.0.1:8085/ics18tickets.ics
```

Systemd unit (recommended) — create `/etc/systemd/system/ics18tickets-http.service`:

```
[Unit]
Description=Serve ics18tickets static files
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ics18tickets
ExecStart=/usr/bin/python3 -m http.server 8085 --directory /opt/ics18tickets
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ics18tickets-http.service
sudo journalctl -u ics18tickets-http.service -f
```

3. Create a Proxy Host in Nginx Proxy Manager UI:

- Domain Names: `ics.example.com`
- Scheme: `http`
- Forward Hostname / IP: the host IP address reachable from Docker (not `127.0.0.1`)
- Forward Port: `8085`
- Enable SSL: request a Let's Encrypt certificate (NPM will handle it)

After NPM provisions the cert, your calendar is available at:

https://ics.example.com/ics/ics18tickets.ics

4. Cron: regenerate every Monday at 23:59

Create `/etc/cron.d/ics18tickets` with:

```
# regenerate every Monday at 23:59
59 23 * * 1 root cd /opt/ics18tickets && /opt/ics18tickets/venv/bin/python ics18tickets.py && cp /opt/ics18tickets/ics18tickets.ics /opt/ics18tickets/ics/ics18tickets.ics && chown root:root /opt/ics18tickets/ics/ics18tickets.ics
```

This way the host cron updates the file, and the host HTTP server will serve the newest copy immediately.

---

## Alternative: host service (Flask) proxied by NPM


Overview: run the `server.py` Flask app (or a host `python -m http.server`) on the host, and create a Proxy Host in NPM that forwards `ics.example.com` to the host service.

1. Install & run the service on the host (example using `server.py`):

```bash
# create venv & install deps as above
# run the service (or use systemd unit)
/opt/ics18tickets/venv/bin/python /opt/ics18tickets/server.py &
```

2. In NPM create a Proxy Host:

- Domain Names: `ics.example.com`
- Scheme: `http`
- Forward Hostname / IP: the host IP (not 127.0.0.1) — use the VPS local network IP or public IP reachable by Docker containers
- Forward Port: `8000` (or whatever port the Flask app listens on)
- Enable SSL: request Let's Encrypt certificate

Notes & gotchas:
- Docker containers cannot reach the host's 127.0.0.1. Use the host IP visible to Docker (or run the service in Docker instead).
- Prefer running the Flask app as a systemd service so it restarts on failures.

---

## Cleanup: remove the containers and config I suggested

Run these commands to remove the cron and (optionally) the systemd unit you created for the host server:

```bash
sudo rm -f /etc/cron.d/ics18tickets
sudo rm -rf /opt/ics18tickets/ics
sudo systemctl stop ics18tickets-http.service || true
sudo systemctl disable ics18tickets-http.service || true
sudo rm -f /etc/systemd/system/ics18tickets-http.service
sudo systemctl daemon-reload
```

Only remove files and services you previously created.

Only remove files and services you previously created.

---

## Troubleshooting

- 404: path mismatch. Common checks:

	- Verify the file exists on the host and the path matches what NPM proxies to:

		```bash
		ls -l /opt/ics18tickets
		ls -l /opt/ics18tickets/ics || true
		curl -I http://127.0.0.1:8085/ics18tickets.ics
		curl -I http://127.0.0.1:8085/ics/ics18tickets.ics
		```

	- If you run the host HTTP server on port 8085, make sure NPM forwards to the host IP and port 8085 and that the host IP is reachable from Docker.

- 502/timeout: NPM cannot reach upstream. Ensure NPM is configured to forward to a reachable host IP:port and check NPM logs.
- Ports 80/443 unavailable: if another process binds those ports on the host, NPM may fail to provision certs or bind—NPM runs in Docker and expects to own 80/443 on the host.
- Certificates: NPM will provision Let's Encrypt certs for proxied hosts; ensure DNS for `ics.example.com` points to the VPS public IP.

---

## Tests

From any machine, verify:

```bash
# curl -I https://ics.example.com/ics/ics18tickets.ics
# expect HTTP 200 and Content-Type: text/calendar
```

If you want, copy this file to your repo and keep it updated with tweaks as you deploy. If you'd like, I can also add a `systemd` unit template for `server.py` or a small Docker Compose YAML for the static container + NPM network attachment.

---

Last updated: 2025-10-25
