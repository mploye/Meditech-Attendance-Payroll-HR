# Deployment Runbook

Two deploy paths are provided:

| Path | When | Cost |
|---|---|---|
| `docker-compose.yml` (this doc) | Start fast on one always-free VM | $0 |
| `deploy/k8s/` | Real scale later | cluster + ops cost |

Both assume the same app constraints:

- **Backend = exactly 1 instance.** DB migrations and the APScheduler run inside the
  app process on startup (`backend/app/main.py`). More replicas race on migrations
  and duplicate scheduled jobs.
- **Frontend builds `NEXT_PUBLIC_API_URL` in at build time** (`frontend/lib/api.ts`).
  For single-host deploys set it to the same public origin as the UI so API calls
  stay same-origin.
- eSSL is mocked (`ESSL_MOCK_MODE=true`) until real portal credentials are configured.
  The direct pull client additionally needs the server to reach device IPs on TCP/UDP 4370.

---

## A. Free VM + Docker Compose (Oracle Cloud "Always Free")

### 1. Provision the VM
1. Create a free account at oracle.com/cloud/free (card for identity; not charged under
   free limits).
2. **Compute → Instances → Create instance**:
   - Image: **Ubuntu 24.04 (aarch64)**.
   - Shape: **VM.Standard.A1.Flex**, **4 OCPU / 24 GB RAM** (free max).
   - Out of capacity? Try another Availability Domain, or drop to 2 OCPU / 12 GB.
   - Upload your SSH public key; note the **public IP**.
3. **VCN → Security Lists → ingress**: allow **TCP 80** and **443** from `0.0.0.0/0`
   (add `4370` only if the eSSL pull path is used).

### 2. DNS
A record `hrms.example.com → <VM public IP>` at your registrar. Caddy needs this to
resolve before issuing TLS (it retries automatically).

### 3. Install Docker (or use the bootstrap)

Quick path — from the repo root, one script installs Docker, generates `.env`
secrets, prompts for your domain, and starts the whole stack:

```bash
cd <repo root>
sudo bash deploy/bootstrap.sh        # or DOMAIN=hrms.example.com sudo bash deploy/bootstrap.sh
```

Manual equivalent (same commands the script runs):

```bash
ssh ubuntu@<VM_IP>
sudo apt update && sudo apt install -y ca-certificates curl
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
```

### 4. Configure
```bash
git clone <repo-url> app && cd app
cp .env.example .env
nano .env
```
Required values: `DOMAIN`, `PUBLIC_URL`, `POSTGRES_PASSWORD`, `JWT_SECRET` (use
`openssl rand -hex 32`), `DEVICE_CONNECTOR_API_KEY`. Keep `ESSL_MOCK_MODE=true` for now.

### 5. Build & start
```bash
docker compose up -d --build
docker compose ps
```
On first run the backend auto-runs migrations (waits for `db` healthy) and starts the
scheduler; Caddy provisions a Let's Encrypt cert.

### 6. Verify
```bash
docker compose logs -f backend
curl -s https://hrms.example.com/api/v1/health     # {"success":true,...}
```
Open `https://hrms.example.com` → register the super admin → create the company → add
employees/shifts/device.

### 7. Backups (do immediately for payroll data)
```bash
sudo mkdir -p /home/ubuntu/backups
crontab -e
# 0 2 * * * cd /home/ubuntu/app && deploy/backup.sh >> /home/ubuntu/backups/cron.log 2>&1
```

### Day-to-day
- Update: `git pull && docker compose up -d --build`
- Logs: `docker compose logs -f`
- Status: `docker compose ps`

---

## B. Kubernetes (`deploy/k8s/`)

Only when hosting at scale / on managed K8s. Frontend stays scaled (2+ replicas);
backend stays `replicas: 1` for scheduler/migration reasons.

```bash
docker build -t ghcr.io/yourorg/hrms-backend:1.0.0 backend
docker build --build-arg NEXT_PUBLIC_API_URL=https://hrms.example.com -t ghcr.io/yourorg/hrms-frontend:1.0.0 frontend
docker push ghcr.io/yourorg/hrms-backend:1.0.0 ghcr.io/yourorg/hrms-frontend:1.0.0
# fill in deploy/k8s/backend/secret.yaml + ingress host + image refs, then:
kubectl apply -k deploy/k8s
kubectl -n hrms rollout status deploy/hrms-backend deploy/hrms-frontend
```

Notes: the optional in-cluster Postgres (`deploy/k8s/postgres/`) can be swapped for a
managed instance by pointing `DATABASE_URL` at it and dropping that resource from
`kustomization.yaml`. `backend/secret.yaml` / `postgres/secret.yaml` values are placeholders — replace before use.