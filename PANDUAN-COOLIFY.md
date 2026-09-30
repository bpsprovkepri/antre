# Panduan Deploy: GitHub → Coolify → Nginx aaPanel → https://antre-dev.gurind.am

```
Pengunjung → Nginx aaPanel (HTTPS) → IP_TAILSCALE:PORT (server Coolify) → kontainer app → PostgreSQL milik sendiri
```
Rahasia (password database, password admin) hanya ada di Environment Variables Coolify, tidak pernah di repo.

## 1. Database PostgreSQL
Database `db-antre` dan user aplikasi harus sudah ada. Aplikasi **menambahkan satu tabel baru, `queue_tiket`**, ke schema `public`
saat start; tabel lama (`queue_antrian_admisi`, `queue_penggilan_antrian`, `queue_setting`) **tidak disentuh**.
User butuh hak `CREATE` di schema `public`. Jika tidak, jalankan `scripts/schema.sql` sekali sebagai admin database.

Contoh menyiapkan database baru (lewati jika `db-antre` sudah ada):
```sql
CREATE ROLE user_antre LOGIN PASSWORD 'GANTI_PASSWORD_KUAT';
CREATE DATABASE "db-antre" OWNER user_antre;
```
Jika database sudah ada tetapi dimiliki user lain: `GRANT CREATE, USAGE ON SCHEMA public TO user_antre;`

**Jaringan:** kontainer harus bisa menjangkau `DB_HOST:5432` dari server Coolify. Pastikan `listen_addresses` dan `pg_hba.conf`
mengizinkan alamat server Coolify. Uji dari server Coolify:
```bash
psql "host=DB_HOST port=5432 dbname=db-antre user=user_antre" -c "select 1"
```

## 2. GitHub
Repo: `https://github.com/bpsprovkepri/antre` (`main`). Perubahan berikutnya: `git add .` → `git commit -m "..."` → `git push`.

## 3. Coolify
1. **+ New → Public Repository** → URL repo → **Check Repository**.
2. Build strategy **Compose**, Branch `main`, Base directory `/`, Docker compose location `/docker-compose.coolify.yml` → **Save** → **Load Compose**.
3. **Domains dikosongkan** (Nginx aaPanel yang melayani domain).
4. **Environment Variables:**

| Variabel | Isi | Wajib |
|---|---|---|
| `DB_HOST` | host PostgreSQL | **Ya** |
| `DB_USER` | user database | **Ya** |
| `DB_PASS` | password database | **Ya** |
| `DB_NAME` | default `db-antre` | tidak |
| `DB_PORT` | default `5432` | tidak |
| `DB_SSLMODE` | default `prefer` (`require` jika server mewajibkan SSL) | tidak |
| `ADMIN_PASSWORD` | password login petugas & laporan | **Ya** |
| `APP_PORT` | port host untuk Nginx (mis. `21007`) | disarankan |
| `APP_BIND` | IP Tailscale server Coolify (agar port tidak terbuka ke internet); kosongkan jika tidak perlu | disarankan |
| `ADMIN_USER`, `NAMA_INSTANSI`, `JUMLAH_MEJA` | default `admin`, `PST BPS Provinsi Kepulauan Riau`, `3` | tidak |

5. **Deploy** → tunggu **Running (healthy)**.

## 4. Nginx aaPanel
Situs `antre-dev.gurind.am` dengan SSL (Let's Encrypt) + Force HTTPS. Reverse proxy: `proxy_pass http://IP_TAILSCALE:APP_PORT;`
dengan header `Host`, `X-Forwarded-For`, `X-Forwarded-Proto` diteruskan. DNS record A `antre-dev` mengarah ke **server aaPanel**.

## 5. Uji
1. Dari server aaPanel: `curl http://IP_TAILSCALE:APP_PORT/healthz` → `{"status":"ok"}`
2. `https://antre-dev.gurind.am/healthz` → sama.
3. `/kiosk` ambil nomor · `/loket/1` (login admin) Panggil → Mulai → Selesai · `/monitor` (klik sekali untuk suara) · `/laporan` + Unduh Excel.

## 6. Cadangan
Data ada di PostgreSQL Anda, jadi ikuti prosedur backup server database tersebut. Contoh manual:
`pg_dump "host=DB_HOST dbname=db-antre user=user_antre" | gzip > antrian-$(date +%F).sql.gz`

## 7. Masalah umum
| Gejala | Solusi |
|---|---|
| Deploy ditolak / variabel merah | `DB_HOST`, `DB_USER`, `DB_PASS`, atau `ADMIN_PASSWORD` belum diisi. |
| `app` restart, Logs: `connection ... failed` | Host/port/`pg_hba.conf` salah, firewall, atau `DB_SSLMODE`. Uji dengan `psql` dari server Coolify. |
| Logs: `password authentication failed` | `DB_USER`/`DB_PASS` salah. |
| Logs: `permission denied for schema public` | User tidak berhak membuat tabel: beri hak (langkah 1) atau jalankan `scripts/schema.sql` sebagai admin. |
| `port is already allocated` | Ganti `APP_PORT`, samakan di `proxy_pass`. |
| 502 di HTTPS | `curl` ke `IP:PORT` dari server aaPanel gagal: cek deploy, `APP_BIND`, jaringan Tailscale. |
| Suara monitor tidak keluar | Klik banner di `/monitor`; pasang voice bahasa Indonesia di OS/Chrome. |

Tanpa Coolify (Docker biasa + Caddy + database bawaan): lihat `DEPLOY.md` dan `docker-compose.yml`.
