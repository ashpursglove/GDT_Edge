# Publishing the Edge Hub image (for maintainers)

The field installer can **pull a ready-made image** and never run `git clone` or `docker build`. You build once (for **amd64** and **arm64** so it runs on a PC and on a Raspberry Pi), push to a registry, then send them:

- the **image name** (e.g. `ghcr.io/yourname/gdt-edge-hub:latest`),
- a tiny bundle: **`docker-compose.dist.yml`**, **`.env.example`**, **`scripts/friend-setup.sh`** (from this repo),
- plus the **Console URL** and **ingest API key** (or they type them in the script).

Raspberry Pi site steps: **[Raspberry_Pi_Setup.md](./Raspberry_Pi_Setup.md)**.

---

## 1. Choose a registry

| Option | Free tier | Notes |
|--------|-----------|--------|
| **GitHub Container Registry (ghcr.io)** | Yes for public packages | Easy if the repo is already on GitHub |
| **Docker Hub** | Yes | `docker.io/youruser/gdt-edge-hub` |

Below uses **GHCR**; Docker Hub is the same idea with `docker login` and a different tag.

---

## 2. One-time: log in to GHCR

Create a GitHub **Personal Access Token** with `write:packages` (and `read:packages`).

```bash
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

Use your GitHub **username** (or org name for org packages).

---

## 3. Build and push (multi-arch: PC + Raspberry Pi 64-bit)

From your machine, in the **`edge-hub`** folder (where the `Dockerfile` is):

```bash
cd edge-hub

docker buildx create --name gdthub --use 2>/dev/null || docker buildx use gdthub

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f Dockerfile \
  -t ghcr.io/YOUR_GITHUB_USER/gdt-edge-hub:latest \
  -t ghcr.io/YOUR_GITHUB_USER/gdt-edge-hub:1.0.0 \
  --push \
  .
```

Replace `YOUR_GITHUB_USER` with your GitHub user or org (lowercase).

**32-bit Raspberry Pi OS (armv7)** is less common now. If you must support it, add `linux/arm/v7` to `--platform` (builds take longer).

---

## 4. Make the image public (GHCR)

GitHub → your profile → **Packages** → package **gdt-edge-hub** → **Package settings** → **Change visibility** → **Public** (so `docker pull` works without logging in).

---

## 5. What the field installer runs

They need **Docker + Compose** on the Pi/Linux box, then either:

**A) Use the helper script** (recommended)

```bash
chmod +x scripts/friend-setup.sh
export GDT_EDGE_IMAGE=ghcr.io/YOUR_GITHUB_USER/gdt-edge-hub:latest
./scripts/friend-setup.sh
```

**B) Manual**

```bash
cp .env.example .env
nano .env   # set URL, key, SERIAL_DEVICE, and GDT_EDGE_IMAGE
docker compose -f docker-compose.dist.yml pull
docker compose -f docker-compose.dist.yml up -d
```

---

## 6. Optional: save image to a USB stick (no internet on site)

On your PC:

```bash
docker pull ghcr.io/YOUR_USER/gdt-edge-hub:latest
docker save ghcr.io/YOUR_USER/gdt-edge-hub:latest -o gdt-edge-hub.tar
```

On the Pi (offline):

```bash
docker load -i gdt-edge-hub.tar
```

Then use `docker-compose.dist.yml` with the same image name and `docker compose up -d` (no `pull`).

---

## 7. Version bumps

Tag a new version when you change the hub:

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/YOUR_USER/gdt-edge-hub:1.1.0 \
  -t ghcr.io/YOUR_USER/gdt-edge-hub:latest \
  --push .
```

Tell them to `docker compose pull` and `docker compose up -d` (see **Raspberry_Pi_Setup.md** for a full walkthrough).
