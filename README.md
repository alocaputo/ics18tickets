# ics18tickets

Generate an .ics calendar with films now showing in cinemas that use 18tickets.

## Deploying

This document describes how to automatically regenerate the .ics file and serve it from a server.

### Prerequisites

- A VPS with root or sudo access.
- A DNS A record (e.g. `ics.example.com`) pointing to your VPS IP.
- The `ics18tickets` repo copied to the VPS (suggested path: `/opt/ics18tickets`). The script `ics18tickets.py` generates `ics18tickets.ics` in that directory.

### Prepare project and venv

On the VPS:

```bash
sudo mkdir -p /opt/ics18tickets
sudo chown $USER:$USER /opt/ics18tickets
cd /opt/ics18tickets
# Place repository files here (ics18tickets.py, requirements.txt)
python3 -m venv /opt/ics18tickets/venv
/opt/ics18tickets/venv/bin/pip install --upgrade pip
/opt/ics18tickets/venv/bin/pip install -r /opt/ics18tickets/requirements.txt
```

Configuration (config.yml)
--------------------------

The generator expects a `config.yml` file next to the scripts. If present it is used to build the films API URL.

Example `/opt/ics18tickets/config.yml`:

```yaml
site: example.18tickets.it        # replace with the correct host or full URL
scheme: https
api_path: /api/v2/films
address: "123 Example Street, Exampleville, EX 00000"  # use "" to omit event location
filter: ['']                      # e.g., ['v.o.s.'] to include only matching titles
```

Notes:
- `site` may be a bare host (as above) or a full URL (including scheme). If `site` is a full URL, `scheme` is ignored.
- A valid `config.yml` is required. If missing or malformed the generator will raise an error and exit — there is no built-in fallback. Ensure `/opt/ics18tickets/config.yml` (or the one next to the scripts) exists before enabling cron or systemd.

Run once to create the .ics file:

```bash
/opt/ics18tickets/venv/bin/python ics18tickets.py
```

Serve the directory from the host (optional)
-------------------------------------------

Run a tiny HTTP server that serves `/opt/ics18tickets` on port 8085. For quick testing:

```bash
cd /opt/ics18tickets
python3 -m http.server 8085 --directory . &
# verify
curl -I http://127.0.0.1:8085/ics18tickets.ics
```

Systemd unit (recommended)
--------------------------

Create `/etc/systemd/system/ics18tickets-http.service` to serve files (default port 8091):

```
[Unit]
Description=Serve ics18tickets static files
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ics18tickets
ExecStart=/usr/bin/python3 -m http.server 8091 --directory /opt/ics18tickets
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ics18tickets-http.service
sudo journalctl -u ics18tickets-http.service -f
```

Proxying with Nginx Proxy Manager (NPM)
---------------------------------------

If using NPM, create a Proxy Host:

- Domain Names: `ics.example.com`
- Scheme: `http`
- Forward Hostname / IP: the host IP reachable from Docker (not `127.0.0.1`)
- Forward Port: `8091` (or the port your service uses)
- Enable SSL: request a Let's Encrypt certificate via NPM

After certificate provisioning, the calendar will be available at:

https://ics.example.com/ics/ics18tickets.ics

Cron: regenerate every Monday at 23:59
-------------------------------------

Create `/etc/cron.d/ics18tickets`:

```
# regenerate every Monday at 23:59
59 23 * * 1 root cd /opt/ics18tickets && /opt/ics18tickets/venv/bin/python ics18tickets.py && cp /opt/ics18tickets/ics18tickets.ics /opt/ics18tickets/ics/ics18tickets.ics && chown root:root /opt/ics18tickets/ics/ics18tickets.ics
```

This ensures the host cron updates the file and the host HTTP server serves the latest copy immediately.

Alternative (untested): host service (Flask) proxied by NPM
----------------------------------------------------------

Run `server.py` (Flask) or a host `python -m http.server` and proxy via NPM.

1. Create venv & install deps as above.
2. Run the service:

```bash
/opt/ics18tickets/venv/bin/python /opt/ics18tickets/server.py &
```

3. In NPM create a Proxy Host:

- Domain Names: `ics.example.com`
- Scheme: `http`
- Forward Hostname / IP: the host IP (not 127.0.0.1) — use the VPS local network IP or public IP reachable by Docker containers
- Forward Port: `8000` (or whatever port the Flask app listens on)
- Enable SSL: request Let's Encrypt certificate

Notes & gotchas:
- Docker containers cannot reach the host's `127.0.0.1`. Use the host IP visible to Docker or run the service inside Docker.
- Prefer running the Flask app as a systemd service so it restarts on failure.

Cleanup
-------

To remove the cron and the optional systemd unit and served files:

```bash
sudo rm -f /etc/cron.d/ics18tickets
sudo rm -rf /opt/ics18tickets/ics
sudo systemctl stop ics18tickets-http.service || true
sudo systemctl disable ics18tickets-http.service || true
sudo rm -f /etc/systemd/system/ics18tickets-http.service
sudo systemctl daemon-reload
```

Only remove files and services you previously created.

Troubleshooting
---------------

- 404: path mismatch. Check:
  - The file exists and the proxied path matches:
    ```bash
    ls -l /opt/ics18tickets
    ls -l /opt/ics18tickets/ics || true
    curl -I http://127.0.0.1:8091/ics18tickets.ics
    curl -I http://127.0.0.1:8001/ics/ics18tickets.ics
    ```
  - If using port 8091, ensure NPM forwards to the host IP and port 8091 and that the host IP is reachable from Docker.
- 502/timeout: NPM cannot reach upstream. Verify NPM config and check logs.
- Ports 80/443 unavailable: If another process binds those ports, NPM may fail to provision certs. NPM expects to control host ports 80/443.
- Certificates: Ensure DNS for `ics.example.com` points to the VPS public IP so NPM can provision Let's Encrypt certs.

Tests
-----

From any machine:

```bash
# curl -I https://ics.example.com/ics/ics18tickets.ics
# expect HTTP 200 and Content-Type: text/calendar
```

If helpful, I can add a systemd unit for `server.py` or a small Docker Compose example to run the static file server with NPM.

Last updated: 2025-10-26
