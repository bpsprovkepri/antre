# Aplikasi Antrian

Sistem antrian layanan: ambil nomor, panggil, mulai, selesai, dan laporan lama layanan harian.
Stack: Python 3.12 · FastAPI · PostgreSQL · Docker. Tanpa build frontend, tanpa API key eksternal.

## Menjalankan (lokal)
```bash
cp .env.example .env      # isi DB_PASSWORD dan ADMIN_PASSWORD
docker compose up -d --build
```
Buka `http://localhost:8000`. Tabel dibuat otomatis saat aplikasi start.
Deploy dengan **Coolify + GitHub**: ikuti **[PANDUAN-COOLIFY.md](PANDUAN-COOLIFY.md)**.
Server biasa tanpa Coolify (Docker + Caddy): lihat **[DEPLOY.md](DEPLOY.md)**.

## Halaman
| URL | Fungsi | Login |
|---|---|---|
| `/kiosk` | Pengunjung ambil nomor (tombol Cetak memakai print browser) | – |
| `/monitor` | Layar TV: nomor dipanggil + suara (Web Speech, bahasa Indonesia) | – |
| `/loket/{n}` | Petugas meja: Panggil → Mulai → Selesai | admin |
| `/laporan` | Laporan harian + unduh Excel (`/laporan.xlsx`) | admin |

## Aturan alur
- Hanya nomor berikutnya yang bisa dipanggil, dan hanya jika meja tersebut tidak sedang menangani antrian lain.
- Alur: **Panggil → Mulai → Selesai**. Pengunjung tidak hadir: tombol **Lewati** (tercatat "tidak hadir", tidak dihitung lama layanan).
- Waktu dicatat di server (zona `Asia/Jakarta`): ambil, panggil, mulai, selesai. Aturan dijaga di query SQL (`app/main.py`, konstanta `AKSI`).

## Struktur
`app/main.py` (semua route + SQL) · `app/templates/` (HTML) · `docker-compose.yml` (lokal) · `docker-compose.coolify.yml` (Coolify) · `docker-compose.caddy.yml` (HTTPS non-Coolify) · `scripts/backup.sh` · `tests/test_alur.py` · `DEPLOY.md`

Rahasia hanya di `.env` (sudah di `.gitignore`), tidak ada kredensial di kode.
