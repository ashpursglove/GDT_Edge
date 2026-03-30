# Deploying GDT Edge Hub (non-expert friendly)

The hub is a small web app on your PC or **Raspberry Pi** that talks to Modbus sensors and uploads to the GDT Console.

You need two secrets from whoever runs the console (same values as Vercel **`GDT_INGEST_API_KEY`** and your site URL):

- **Console API base URL** — e.g. `https://your-project.vercel.app` (no trailing path).
- **API key** — long random string used as **Bearer** token in the hub UI.

---

## For maintainers: build and publish an image

If you ship a pre-built image (Docker Hub or GitHub Container Registry), the field installer needs `docker-compose.dist.yml` and optionally `scripts/friend-setup.sh`, and creates `.env` on site. See **[PUBLISH.md](./PUBLISH.md)** for build/push steps. Site install steps: **[Raspberry_Pi_Setup.md](./Raspberry_Pi_Setup.md)**.

---

## Option A — Docker on Raspberry Pi / Linux (recommended for Pi)

**Requirements**

- Raspberry Pi OS or another Linux with **Docker Engine** + **Docker Compose** v2.
- USB **RS485 adapter** plugged in (often shows as `/dev/ttyUSB0`).

**Steps**

1. Copy this `edge-hub` folder to the Pi (USB stick, `git clone`, or zip).
2. In a terminal, go into the `edge-hub` folder.
3. Run the setup script (it will ask for URL, key, and serial port):

   ```bash
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

   Or manually:

   ```bash
   nano .env
   # Create the file: URL, key, SERIAL_DEVICE (see Raspberry_Pi_Setup.md). Then:
   docker compose up -d --build
   ```

4. On another device on the same network, open a browser:

   `http://<pi-ip-address>:8756`

   The **API URL** and **API key** fields should already be filled if they were set in `.env` / environment (first run only fills empty fields).

5. **Serial port**: pick the same device path in the UI if needed (e.g. `/dev/ttyUSB0`). Then add reactors/devices and **Start monitoring**.

**Finding the serial device on a Pi**

```bash
ls /dev/ttyUSB* /dev/ttyAMA* 2>/dev/null
ls -l /dev/serial/by-id/
```

Put that path in `.env` as both `GDT_SERIAL_DEVICE` and `SERIAL_DEVICE`, and in `docker-compose.yml` the `devices:` line must map host path → same path inside the container.

**Troubleshooting**

- **Permission / adapter not seen**: try `sudo usermod -aG dialout $USER` and re-login, or temporarily uncomment `privileged: true` under the service in `docker-compose.yml`.
- **ARM (32-bit Pi)**: prefer 64-bit Pi OS if possible; build on the Pi with `docker compose build` so the image matches the CPU.
- **Windows**: USB serial inside Docker is difficult; use **Option B** (Python on Windows) instead.

---

## Option B — Python on the machine (Windows or Linux, no Docker)

1. Install **Python 3.11+**.
2. In `edge-hub`:

   ```bash
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Set environment variables **before** first run (optional; pre-fills empty UI fields):

   **Windows (cmd)**

   ```bat
   set GDT_CONSOLE_API_BASE_URL=https://your-app.vercel.app
   set GDT_CONSOLE_API_KEY=your-key
   set GDT_SERIAL_DEVICE=COM5
   .venv\Scripts\python.exe run.py
   ```

   **Linux / Pi (no Docker)**

   ```bash
   export GDT_CONSOLE_API_BASE_URL=https://your-app.vercel.app
   export GDT_CONSOLE_API_KEY=your-key
   export GDT_SERIAL_DEVICE=/dev/ttyUSB0
   .venv/bin/python run.py
   ```

4. Open `http://127.0.0.1:8756` (or set `GDT_HOST=0.0.0.0` to allow other PCs on the LAN).

---

## Environment variables (reference)

| Variable | Purpose |
|----------|---------|
| `GDT_HOST` | Bind address (default `127.0.0.1`; use `0.0.0.0` for LAN access). |
| `GDT_PORT` | Port (default `8756`). |
| `GDT_HUB_DATA` | Directory for `hub.db` (default `./data`). |
| `GDT_CONSOLE_API_BASE_URL` | Pre-seeds **Console API base URL** if the hub DB field is empty. |
| `GDT_CONSOLE_API_KEY` | Pre-seeds **API key** if empty. |
| `GDT_SERIAL_DEVICE` | Pre-seeds **Serial port** if empty. |

Pre-seeding only fills **empty** fields; it does not overwrite settings already saved in the UI/database.

---

## Building for a specific CPU (optional)

On your laptop, for a **64-bit Pi**:

```bash
docker buildx build --platform linux/arm64 -t gdt-edge-hub:pi --load .
```

Then save/load the image on the Pi, or build directly on the Pi with `docker compose build`.
