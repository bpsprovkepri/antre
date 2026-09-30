#!/usr/bin/env bash
# Cadangan database harian. Jalankan dari folder proyek:  ./scripts/backup.sh
# Jadwal cron (tiap 02:00):  0 2 * * * cd /opt/antrian && ./scripts/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
f="backups/antrian-$(date +%F-%H%M).sql.gz"
docker compose exec -T db pg_dump -U antrian antrian | gzip > "$f"
find backups -name 'antrian-*.sql.gz' -mtime +30 -delete   # simpan 30 hari
echo "OK: $f"
