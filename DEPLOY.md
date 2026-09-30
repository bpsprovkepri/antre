> Memakai Coolify? Abaikan file ini dan ikuti **PANDUAN-COOLIFY.md**.

# Deploy ke antre-dev.gurind.am

## 1. DNS
Buat record **A** `antre-dev.gurind.am` → IP publik server. Tunggu hingga `ping antre-dev.gurind.am` menunjuk IP tersebut (wajib sebelum Caddy meminta sertifikat).

## 2. Server
Butuh Docker + Docker Compose plugin, port 80 dan 443 terbuka.
```bash
scp antrian-baru.zip user@server:/opt/ && ssh user@server
cd /opt && unzip antrian-baru.zip && cd antrian
cp .env.example .env && nano .env       # isi DB_PASSWORD dan ADMIN_PASSWORD
```

## 3. Jalankan
**Opsi A – HTTPS otomatis (port 80/443 masih kosong):**
```bash
docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d --build
```
**Opsi B – server sudah punya Nginx/Traefik/Caddy sendiri:**
```bash
docker compose up -d --build     # aplikasi hanya di 127.0.0.1:8000
```
Contoh Nginx (sertifikat mis. lewat `certbot --nginx -d antre-dev.gurind.am`):
```nginx
server {
    server_name antre-dev.gurind.am;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 4. Cek
```bash
docker compose ps                 # app & db healthy
curl -s https://antre-dev.gurind.am/healthz    # {"status":"ok"}
```
Buka `https://antre-dev.gurind.am` → menu. Halaman `/loket/{n}`, `/laporan`, dan `/pengaturan` meminta login lewat halaman login (`ADMIN_USER` / `ADMIN_PASSWORD`).

## Operasional
| Tugas | Perintah |
|---|---|
| Lihat log | `docker compose logs -f app` |
| Update kode | ganti file, lalu `docker compose up -d --build` |
| Cadangan | `./scripts/backup.sh` (pasang di cron) |
| Pulihkan | `gunzip -c backups/FILE.sql.gz \| docker compose exec -T db psql -U antrian antrian` |
| Ganti daftar meja | menu Setting → Daftar Meja |

## Uji otomatis (opsional, di laptop)
```bash
pip install -r requirements-dev.txt
pytest -q
```
(uji memakai PostgreSQL tertanam sendiri; nilai `DATABASE_URL` diabaikan)

## Catatan
- Layar TV `/monitor`: buka di browser (disarankan Chrome), klik sekali agar suara aktif. Suara memakai voice bahasa Indonesia bawaan perangkat; jika tidak terdengar, pasang paket suara Indonesia di OS/Chrome.
- Halaman `/kiosk`, `/monitor`, dan `/api/monitor` sengaja tanpa login karena dipakai layar publik.
- Zona waktu tampilan dan pencatatan: Asia/Jakarta (WIB).
