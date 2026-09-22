#!/usr/bin/env bash
# Daily Postgres backup (gzipped SQL dump) with 30-day rotation.
# Run from the repo root:  bash deploy/backup.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/home/${USER}/backups}"
mkdir -p "${BACKUP_DIR}"
docker compose exec -T db pg_dump -U hrms hrms \
  | gzip > "${BACKUP_DIR}/hrms_$(date +%Y%m%d).sql.gz"
find "${BACKUP_DIR}" -name 'hrms_*.sql.gz' -mtime +30 -delete
echo "Backup OK: ${BACKUP_DIR}/hrms_$(date +%Y%m%d).sql.gz"