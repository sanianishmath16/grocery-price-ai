# GroceryAI 🛒

Compare grocery prices across **Blinkit, Zepto, Instamart & Flipkart Minutes** — type a list or upload photos.

---

## Live on your phone in 3 ways

| Method | Cost | Effort | Best for |
|--------|------|--------|----------|
| **Render.com** (recommended) | Free | 10 min | Anyone |
| **Fly.io** | Free | 15 min | Developers |
| **Your own VPS** (Hetzner/DigitalOcean) | ~€3/mo | 20 min | Full control |

All three give you a real `https://` URL you can open on any device using mobile data.

---

## Option A — Deploy on Render.com (easiest, free)

### Step 1 — Push to GitHub

```bash
cd grocery-price-ai
git init
git add .
git commit -m "initial"
# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/grocery-price-ai.git
git push -u origin main
```

### Step 2 — Create a free Render account

Go to **[render.com](https://render.com)** → Sign up (GitHub login is fastest).

### Step 3 — Deploy

1. Dashboard → **New** → **Blueprint**
2. Connect your GitHub repo
3. Render reads `render.yaml` and creates the service automatically
4. Go to the service → **Environment** → add:
   ```
   OPENAI_API_KEY = sk-...your-key...
   ```
   *(leave blank if you don't have one — text search still works)*
5. Click **Deploy**

### Step 4 — Open on your phone

Render gives you a URL like:
```
https://groceryai.onrender.com
```
Open it on any phone using **mobile data** — it works anywhere in the world.

> **Free tier note:** The service sleeps after 15 minutes of inactivity and takes ~30 seconds to wake on the first request. Upgrade to Starter ($7/mo) for always-on.

---

## Option B — Deploy on Fly.io (fast, global, free)

### Step 1 — Install flyctl

```bash
# macOS
brew install flyctl

# Windows
iwr https://fly.io/install.ps1 -useb | iex

# Linux
curl -L https://fly.io/install.sh | sh
```

### Step 2 — Sign up and log in

```bash
fly auth signup    # or: fly auth login
```

### Step 3 — Launch (one-time setup)

```bash
cd grocery-price-ai
fly launch --no-deploy --build-arg BUILD_TARGET=prod
# When asked for app name, type e.g. "groceryai-yourname"
# When asked for region, choose: sin (Singapore, closest to India)
# When asked to create Postgres/Redis: No (we'll add Redis separately)
```

### Step 4 — Add free Redis (optional but recommended)

```bash
fly redis create --name groceryai-redis
# Copy the connection string, then:
fly secrets set REDIS_URL="redis://..."
```

### Step 5 — Set your API key

```bash
fly secrets set OPENAI_API_KEY="sk-..."
# Skip this if you don't have a key yet
```

### Step 6 — Deploy

```bash
fly deploy --build-arg BUILD_TARGET=prod
```

### Step 7 — Open on your phone

```bash
fly open
# Opens https://groceryai-yourname.fly.dev in your browser
```

Send that URL to your phone — works on mobile data worldwide.

---

## Option C — Your own VPS (€3/month on Hetzner)

Best for full control and no sleep issues.

### Step 1 — Get a server

- [Hetzner Cloud](https://www.hetzner.com/cloud) CX11 — €3.79/mo, 1 vCPU, 2 GB RAM
- [DigitalOcean](https://www.digitalocean.com) Basic Droplet — $4/mo

Choose **Ubuntu 22.04**, add your SSH key.

### Step 2 — SSH in and install Docker

```bash
ssh root@YOUR_SERVER_IP

# Install Docker + Compose
curl -fsSL https://get.docker.com | sh
apt-get install -y docker-compose-plugin
```

### Step 3 — Copy the project to the server

```bash
# On your laptop:
scp -r grocery-price-ai root@YOUR_SERVER_IP:/opt/groceryai
```

Or clone from GitHub:
```bash
# On the server:
git clone https://github.com/YOUR_USERNAME/grocery-price-ai.git /opt/groceryai
```

### Step 4 — Create `.env`

```bash
cd /opt/groceryai
cp .env.example .env
nano .env
# Set OPENAI_API_KEY=sk-...
```

### Step 5 — Start the stack

```bash
docker compose up -d --build
```

### Step 6 — Open port 80 in the firewall

On Hetzner: Firewall rules → allow TCP port 80 (and 443 if you add HTTPS later).

### Step 7 — Open on your phone

```
http://YOUR_SERVER_IP
```

Works on any device using mobile data. To add a proper domain + HTTPS, point a domain at the IP and add [Caddy](https://caddyserver.com/) as a reverse proxy.

---

## Running locally

```bash
cd grocery-price-ai
cp .env.example .env      # edit if you have an OPENAI_API_KEY

docker compose up --build
```

Open **http://localhost** — the app is served on port 80.

> The `localhost:8000` URL is no longer needed. Everything goes through nginx on port 80.

---

## Architecture

```
Browser / Phone
      │  HTTPS (port 443 in prod, 80 in local)
      ▼
  nginx (port 80)
  ├─ GET /           → serves frontend/index.html, style.css, app.js
  └─ /api/*          → proxies to FastAPI (uvicorn, internal port 8000)
                              │
                              ├─ POST /api/compare
                              ├─ POST /api/analyze-images  ← uses OPENAI_API_KEY
                              ├─ GET  /api/health
                              └─ GET  /api/apps
                                      │
                                 Redis cache (15 min TTL)
```

**No secrets in the frontend.** `OPENAI_API_KEY` lives only in the backend container / server environment variables. The frontend JS only ever calls `/api/*` on the same origin.

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | No | Enables image recognition. Get at [platform.openai.com](https://platform.openai.com/api-keys). Without it, text search works perfectly; image tab shows a setup notice. |
| `REDIS_URL` | No | Redis connection string. Default: `redis://redis:6379/0` (docker-compose). Use an [Upstash](https://upstash.com) free Redis for Render/Fly. |
| `CORS_ORIGINS` | No | Comma-separated allowed origins. Default `*`. Tighten to your domain in production: `https://groceryai.onrender.com` |

---

## Activating image recognition

Once you have an OpenAI API key:

**docker-compose (local):**
```bash
echo "OPENAI_API_KEY=sk-..." >> .env
docker compose restart api
```

**Render:** Dashboard → Service → Environment → add `OPENAI_API_KEY` → Redeploy.

**Fly.io:**
```bash
fly secrets set OPENAI_API_KEY="sk-..."
# Fly automatically restarts the app
```

**Cost estimate:** ~$0.001–0.003 per image analysis (GPT-4o `detail:low`). A user uploading 10 images costs about $0.02.

---

## API reference

### `POST /api/compare`

```json
{
  "items": ["Amul Milk 1L", "Maggi 70g x5"],
  "pincode": "560001"
}
```

Returns ranked platform prices (cheapest first).

### `POST /api/analyze-images`

```json
{
  "images_b64": ["<base64>", "<base64>"],
  "pincode": "560001"
}
```

Returns detected products and a price comparison. Requires `OPENAI_API_KEY`.

### `GET /api/health`

Returns `{"status": "ok"}`. Used by load balancers and health checks.

---

## Project structure

```
grocery-price-ai/
├── backend/
│   ├── main.py                 FastAPI app + endpoints
│   ├── config.py               All settings (reads from env vars)
│   ├── ai/
│   │   ├── normalizer.py       Parses "Amul Milk 1L" → structured product
│   │   ├── matcher.py          Fuzzy product matching
│   │   └── vision_service.py   OpenAI Vision integration (stub ready)
│   ├── scrapers/               Mock scrapers (Blinkit, Zepto, Instamart, Flipkart)
│   ├── services/               Price aggregation + ranking
│   └── cache/                  Redis wrapper
├── frontend/
│   ├── index.html              Single-page app (tab: text search + image search)
│   ├── style.css               Mobile-first CSS
│   └── app.js                  Vanilla JS — no framework, no build step
├── docker/
│   └── supervisord.conf        Process supervisor for prod single-container
├── nginx.conf                  nginx for docker-compose (api = separate container)
├── nginx-prod.conf             nginx for prod single-container (api = 127.0.0.1)
├── Dockerfile                  Multi-stage: dev (API-only) + prod (nginx+uvicorn)
├── docker-compose.yml          Local development stack
├── fly.toml                    Fly.io deployment config
├── render.yaml                 Render.com deployment config
├── .env.example                Template for environment variables
└── .gitignore                  Excludes .env and __pycache__
```
