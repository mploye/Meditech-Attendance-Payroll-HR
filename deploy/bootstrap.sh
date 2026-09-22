#!/usr/bin/env bash
# One-shot host provisioning for the docker-compose stack.
# Usage: run from the repo root on a fresh Ubuntu 24.04 VM:
#   sudo bash deploy/bootstrap.sh
# Optionally pass DOMAIN up front:  DOMAIN=hrms.example.com sudo bash deploy/bootstrap.sh
set -euo pipefail

DOMAIN="${DOMAIN:-}"
REPO_DIR="$(pwd)"

echo "==> [1/5] Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi
docker --version

echo "==> [2/5] .env (generated only if missing)"
if [ ! -f "${REPO_DIR}/.env" ]; then
  cp "${REPO_DIR}/.env.example" "${REPO_DIR}/.env"
  POSTGRES_PASSWORD="$(openssl rand -hex 24)"
  JWT_SECRET="$(openssl rand -hex 32)"
  DEVICE_CONNECTOR_API_KEY="$(openssl rand -hex 24)"
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" "${REPO_DIR}/.env"
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|" "${REPO_DIR}/.env"
  sed -i "s|^DEVICE_CONNECTOR_API_KEY=.*|DEVICE_CONNECTOR_API_KEY=${DEVICE_CONNECTOR_API_KEY}|" "${REPO_DIR}/.env"
fi

echo "==> [3/5] Domain"
if [ -z "${DOMAIN}" ]; then
  while [ -z "${DOMAIN}" ]; do
    read -rp "FQDN without scheme (e.g. hrms.example.com): " DOMAIN
  done
fi
sed -i "s|^DOMAIN=.*|DOMAIN=${DOMAIN}|" "${REPO_DIR}/.env"
sed -i "s|^PUBLIC_URL=.*|PUBLIC_URL=https://${DOMAIN}|" "${REPO_DIR}/.env"
grep -E "^(DOMAIN|PUBLIC_URL|POSTGRES_PASSWORD|JWT_SECRET)=" "${REPO_DIR}/.env" | sed 's/=.*/=<set>/'

echo "==> [4/5] Build & start"
cd "${REPO_DIR}"
docker compose up -d --build

echo "==> [5/5] Done"
echo
echo "After you point DNS (${DOMAIN} -> this server's public IP):"
echo "  curl -s https://${DOMAIN}/api/v1/health"
echo "  docker compose ps"
echo
echo "Backups: add to crontab"
echo "  0 2 * * * cd ${REPO_DIR} && deploy/backup.sh"