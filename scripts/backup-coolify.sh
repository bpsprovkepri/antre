#!/usr/bin/env bash
# Cadangan database saat dijalankan lewat Coolify. Jalankan di SERVER (bukan di dalam kontainer).
#   ./scripts/backup-coolify.sh                 -> cari kontainer db otomatis
#   ./scripts/backup-coolify.sh NAMA_KONTAINER  -> jika ada lebih dari satu kandidat
# Cron (tiap 02:00):  0 2 * * * /opt/backup/backup-coolify.sh >> /var/log/antrian-backup.log 2>&1
set -euo pipefail
DIR="${BACKUP_DIR:-/opt/backup/antrian}"
C="${1:-}"
if [ -z "$C" ]; then
  mapfile -t found < <(docker ps --filter "label=com.docker.compose.service=db" \
                                 --filter "ancestor=postgres:16-alpine" --format '{{.Names}}')
  [ "${#found[@]}" -eq 1 ] || { echo "Kandidat kontainer: ${found[*]:-tidak ada}. Beri nama kontainer sebagai argumen." >&2; exit 1; }
  C="${found[0]}"
fi
mkdir -p "$DIR"
f="$DIR/antrian-$(date +%F-%H%M).sql.gz"
docker exec "$C" pg_dump -U antrian antrian | gzip > "$f"
find "$DIR" -name 'antrian-*.sql.gz' -mtime +30 -delete
echo "OK: $f ($C)"
