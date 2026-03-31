# GDT Edge Hub — Raspberry Pi (site install)

This guide is for **GDT staff** installing the Edge Hub on a **customer site** using a Raspberry Pi. The Pi should already be on the network; you need **internet on the Pi** for the first `docker pull`.

---

## 1. Credentials and image (from GDT before you travel)

Get these from GDT operations / engineering (not from the customer). You will paste them into `.env` on the Pi.

| Item | What it is | Example |
|------|------------|---------|
| **Console API base URL** | GDT Console (Vercel) root URL | `https://your-project.vercel.app` |
| **API key** | Bearer / ingest key — same secret as `GDT_INGEST_API_KEY` on the server | Long random string |
| **Docker image** | Pre-built hub image on Docker Hub | `dockerash1987/gdt-edge-hub:latest` |

If the image name or registry changes, use whatever GDT issued for that deployment.

---

## 2. Install Docker (Raspberry Pi OS / Debian)

Open a terminal on the Pi (local or SSH). Run each block in order.

**Update packages (recommended):**

```bash
sudo apt update && sudo apt upgrade -y
```

**Install Docker Engine:**

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**Run Docker as your user (no `sudo` every time):**

```bash
sudo usermod -aG docker $USER
```

**Log out and log back in** (or reboot). Then test:

```bash
docker run --rm hello-world
```

**Docker Compose plugin** (usually installed with the script above). Verify:

```bash
docker compose version
```

If that fails:

```bash
sudo apt install -y docker-compose-plugin
```

---

## 3. Log in to Docker Hub

You should already have a **Docker Hub** account with **pull** access to the GDT image (if the image is private, ask GDT for access). Log in on the Pi:

```bash
docker login
```

Enter your Docker Hub username and password when prompted.

---

## 4. Put the `edge-hub` folder on the Pi

Use one of:

- Copy the **`edge-hub`** folder from the GDT repo (USB, internal share, or `git clone` if you use Git on site).

Example clone (adjust URL to your GDT repo):

```bash
cd ~
git clone https://github.com/YOUR_ORG/GDT_Edge.git
cd GDT_Edge/edge-hub
```

You need at least: `docker-compose.dist.yml` and (optional) `scripts/friend-setup.sh`. You will create `.env` locally (§6).

---

## 5. RS485 serial device path

Plug in the USB ↔ RS485 adapter, then list serial devices:

```bash
ls /dev/ttyUSB* 2>/dev/null
ls -l /dev/serial/by-id/ 2>/dev/null
```

Often the path is **`/dev/ttyUSB0`**. Use whatever path you see for **both** `GDT_SERIAL_DEVICE` and `SERIAL_DEVICE` in the next step.

Allow serial access for your user (recommended):

```bash
sudo usermod -aG dialout $USER
```

Log out and back in after this.

---

## 6. Create `.env`

From the `edge-hub` directory:

```bash
cd ~/GDT_Edge/edge-hub
```

(Change the path if your copy lives elsewhere.)

```bash
nano .env
```

Create the file if it does not exist. Set at least:

```env
GDT_EDGE_IMAGE=dockerash1987/gdt-edge-hub:latest
GDT_CONSOLE_API_BASE_URL=https://YOUR-CONSOLE-URL
GDT_CONSOLE_API_KEY=YOUR-API-KEY
GDT_SERIAL_DEVICE=/dev/ttyUSB0
SERIAL_DEVICE=/dev/ttyUSB0
GDT_PORT=8756
```

Use the **image**, **URL**, and **key** from §1. If your serial device is not `ttyUSB0`, use the path from §5 for `GDT_SERIAL_DEVICE` and `SERIAL_DEVICE`.

Save in nano: **Ctrl+O**, Enter, **Ctrl+X**.

---

## 7. Pull the image and start the hub

```bash
docker compose -f docker-compose.dist.yml pull
docker compose -f docker-compose.dist.yml up -d
```

Check status and logs:

```bash
docker compose -f docker-compose.dist.yml ps
docker compose -f docker-compose.dist.yml logs -f --tail=50
```

**Ctrl+C** stops following logs.

---

## 8. Open the hub in a browser

On the Pi:

```bash
hostname -I
```

Use the first IP (e.g. `192.168.1.42`). On a laptop or phone **on the same LAN**:

```text
http://192.168.1.42:8756
```

If `.env` was filled before first run, **Settings** should already show the console URL and API key. Otherwise enter them and save.

### Use a name instead of memorizing an IP (mDNS)

Raspberry Pi OS usually includes **mDNS** (`.local` hostnames). Set a hostname once:

```bash
sudo hostnamectl set-hostname gdt-hub
sudo reboot
```

On a PC or phone **on the same LAN**, open:

```text
http://gdt-hub.local:8756
```

Use the same name you set (`gdt-hub` in the example). If `.local` does not resolve, use `hostname -I` and the IP as above.

### Start on boot (no manual Docker after every reboot)

One-time install — from your real `edge-hub` path:

```bash
cd ~/GDT_Edge/edge-hub
chmod +x scripts/install-edge-hub-systemd.sh
export EDGE_HUB_DIR="$HOME/GDT_Edge/edge-hub"
export HUB_USER="$USER"
./scripts/install-edge-hub-systemd.sh
```

Requires your user to be in the `docker` group. After this, **`docker compose up -d` runs automatically** when the Pi starts. Check: `sudo systemctl status gdt-edge-hub.service`.

### Pi with desktop: one command opens the browser

From `edge-hub`:

```bash
chmod +x scripts/start-hub-and-open-browser.sh
./scripts/start-hub-and-open-browser.sh
```

Starts the stack (if needed), waits until the API responds, then opens **`http://127.0.0.1:8756`** in the default browser. You can pin this script or add it to **Startup Applications** if you want the UI after login.

### Windows (Docker Desktop)

Double‑click **`open-hub.cmd`** in the `edge-hub` folder (with Docker Desktop running). It runs Compose and opens **`http://127.0.0.1:8756`**.

---

## 9. Finish configuration in the UI

1. **Settings** — Confirm URL, API key, **serial port**, baud rate (often **9600**). Save.
2. **Sites** — **Load sites**, select the site, let reactors sync.
3. **Reactors** — For each reactor, **Devices…** — add Modbus devices and slave IDs per site documentation.
4. **Start monitoring** when wiring and IDs are verified.

---

## 10. If something fails

| Problem | What to try |
|--------|-------------|
| `permission denied` for Docker | Log out/in after `usermod -aG docker`, or use `sudo docker` once to test. |
| `no such file /dev/ttyUSB0` | Re-check §5; update `.env`; try another USB port. |
| Serial still blocked | In `docker-compose.dist.yml`, uncomment **`privileged: true`** under the service, then `docker compose -f docker-compose.dist.yml up -d` again. |
| Cannot reach port 8756 | Test on the Pi: `http://127.0.0.1:8756`. Check firewall. |
| No sites / reactors | API key must match the server; sites/reactors must exist in the console. |
| `no matching manifest for linux/arm64` | The image on the registry was built for **PC (amd64) only**. Whoever publishes the image must push a **multi-arch** build (`linux/amd64` + `linux/arm64`). See **`PUBLISH.md`** — Docker Hub example under “Same build, Docker Hub”. |

---

## 11. Stop and start the service

```bash
cd ~/GDT_Edge/edge-hub
docker compose -f docker-compose.dist.yml down
```

```bash
docker compose -f docker-compose.dist.yml up -d
```

Data persists under **`./data`** next to the compose file.

### After a full shutdown or reboot (get running again)

If you installed **systemd** (see §8), the hub container usually starts by itself after boot — open **`http://<pi-hostname>.local:8756`** or **`http://127.0.0.1:8756`** on the Pi.

Otherwise:

1. **Power on the Pi** and wait until it has finished booting (network is up).
2. **Open a terminal** on the Pi (or SSH in).
3. **Go to the `edge-hub` folder** (use your real path if different):

   ```bash
   cd ~/GDT_Edge/edge-hub
   ```

4. **Start the hub** (safe even if it was already running):

   ```bash
   docker compose -f docker-compose.dist.yml up -d
   ```

5. **Check** (optional):

   ```bash
   docker compose -f docker-compose.dist.yml ps
   ```

   The `gdt-edge-hub` service should be **running**.

6. **Open the UI in a browser** — on the Pi: `http://127.0.0.1:8756` — or from another device: `http://<pi-ip>:8756` or `http://<hostname>.local:8756`.

No need to edit `.env` again unless something changed. **Pull** (`docker compose … pull`) is only required when GDT publishes a **new image** you want to install.

---

## 12. Optional: guided script

If present:

```bash
chmod +x scripts/friend-setup.sh
export GDT_EDGE_IMAGE=dockerash1987/gdt-edge-hub:latest
./scripts/friend-setup.sh
```

---

*Developer notes: build/publish — `PUBLISH.md`; general deploy options — `DEPLOY.md`.*
