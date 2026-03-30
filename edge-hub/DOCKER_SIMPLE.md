# Docker in plain English (Edge Hub)

## What you’re doing

1. **`docker build`** — Packages the Edge Hub app into an **image** (a frozen snapshot of the app + Python + dependencies) on **your** computer.

2. **`docker push`** — Uploads that image to a **registry** (a website that stores Docker images). Without a registry, another machine has no way to download your image unless you copy a file (see “No internet” below).

3. **On site: `docker pull`** — Downloads the same image from the registry. Then run it with Compose (serial port, `.env`, etc.). For a Raspberry Pi at a customer site, see **[Raspberry_Pi_Setup.md](./Raspberry_Pi_Setup.md)**.

**GHCR** = **GitHub Container Registry** (`ghcr.io/...`). It’s just one registry option (free with GitHub). **Docker Hub** (`docker.io`) is the older, very common one (`docker login`, `yourname/something`). Both work the same way: **push once, pull anywhere**.

---

## Easiest path: Docker Hub (like most tutorials)

### One-time setup

1. Create a free account at [hub.docker.com](https://hub.docker.com).
2. Create a **repository**, e.g. `gdt-edge-hub` (can be public so pull does not require a login).

### On your machine (in the `edge-hub` folder)

**Same architecture as the target machine (e.g. both PCs, both amd64):**

```bash
cd edge-hub

docker login
docker build -t YOUR_DOCKERHUB_USERNAME/gdt-edge-hub:latest .
docker push YOUR_DOCKERHUB_USERNAME/gdt-edge-hub:latest
```

Replace `YOUR_DOCKERHUB_USERNAME` with your Docker Hub username.

**You on Windows PC, installer on Raspberry Pi (different CPU):** one image must support **both** architectures. Use buildx (see below).

### On the site machine

They need the small files from this repo: `docker-compose.dist.yml`, and optionally `scripts/friend-setup.sh`; they create `.env` on the machine. Step-by-step for Pi: **[Raspberry_Pi_Setup.md](./Raspberry_Pi_Setup.md)**.

In `.env` set:

```env
GDT_EDGE_IMAGE=docker.io/YOUR_DOCKERHUB_USERNAME/gdt-edge-hub:latest
```

(`docker.io/` is optional; Docker adds it by default.)

Then:

```bash
docker compose -f docker-compose.dist.yml pull
docker compose -f docker-compose.dist.yml up -d
```

Or run `scripts/friend-setup.sh` and paste the image name when asked.

---

## PC + Raspberry Pi (two architectures)

Raspberry Pi is usually **arm64** (64-bit Pi OS). Your PC is often **amd64**. A normal `docker build` on the PC only builds **amd64**, so **`docker pull` on the Pi can fail or run badly**.

Build **both** and push one “multi-arch” tag:

```bash
cd edge-hub

docker buildx create --name gdthub --use 2>/dev/null || docker buildx use gdthub

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t YOUR_DOCKERHUB_USERNAME/gdt-edge-hub:latest \
  --push \
  .
```

Then the same `YOUR_DOCKERHUB_USERNAME/gdt-edge-hub:latest` works on your PC and on a 64-bit Pi.

---

## No registry (USB stick, no account)

On your machine:

```bash
cd edge-hub
docker build -t gdt-edge-hub:latest .
docker save gdt-edge-hub:latest -o gdt-edge-hub.tar
```

Copy `gdt-edge-hub.tar` to the Pi. On the Pi:

```bash
docker load -i gdt-edge-hub.tar
```

Then they run Compose using **image name** `gdt-edge-hub:latest` (you’d set `GDT_EDGE_IMAGE=gdt-edge-hub:latest` in `.env` and use a compose file that references that image—no `pull` from internet).

**Catch:** an image built on **amd64** won’t run on **arm64** Pi unless you used `buildx` for `linux/arm64` on that build. Easiest for offline Pi: **build on the Pi itself** (`docker build` on the Pi) and `docker save` there, or use multi-arch buildx above and `docker save` the arm64 variant (more advanced).

---

## GHCR in one line

If you already use GitHub: login to `ghcr.io`, tag `ghcr.io/GITHUB_USER_LOWER/gdt-edge-hub:latest`, push there. Same idea as Docker Hub, different host. See **PUBLISH.md** for exact commands.

---

## Quick reference

| Step            | You (developer)              | Site / installer            |
|----------------|------------------------------|-----------------------------|
| Build / upload | `docker build` → `docker push` | `docker pull` (or `load`)   |
| Run            | —                            | `docker compose up -d`      |
| Config         | —                            | `.env` (URL, key, serial)   |

The Edge Hub **compose** and **env** files are in this folder; the **image** is whatever you pushed (`YOUR_USER/gdt-edge-hub:latest`).
