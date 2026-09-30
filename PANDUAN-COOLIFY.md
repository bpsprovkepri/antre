# Panduan Deploy: GitHub → Coolify → https://antre-dev.gurind.am

Urutan: **(A) GitHub → (B) DNS → (C) Coolify → (D) Cek → (E) Otomatis deploy**.
Estimasi: 20–30 menit. Repo boleh publik (tidak ada rahasia di kode; rahasia hanya di Coolify).

---
## A. Buat repo GitHub

1. Di github.com klik **New repository** → nama mis. `antrean` → pilih **Public** (atau Private, lihat catatan) → **jangan** centang README/.gitignore/license (sudah ada di proyek) → **Create repository**.
2. Ekstrak zip, lalu dari dalam folder `antrian/`:
```bash
cd antrian
git init -b main
git add .
git status            # pastikan TIDAK ada file .env
git commit -m "Aplikasi antrian: versi awal"
git remote add origin https://github.com/USERNAME/antrean.git
git push -u origin main
```
3. Cek di halaman GitHub: ada `docker-compose.coolify.yml`, `Dockerfile`, folder `app/`.

> Opsional: tambahkan file `LICENSE` sesuai keinginan Anda (mis. MIT) sebelum repo dipublikasikan.
> Repo **private**: di Coolify pakai **Private Repository (with deploy key)** atau **GitHub App** (lihat langkah C1).

---
## B. DNS
Di pengelola DNS `gurind.am`, buat record:

| Type | Name | Value |
|---|---|---|
| A | `antre-dev` | IP publik server Coolify |

Jika memakai **Cloudflare**: saat pertama kali, set awan ke **DNS only** (abu-abu) agar sertifikat Let's Encrypt bisa terbit; setelah aktif boleh dinyalakan proxy dengan SSL mode **Full (strict)**.
Cek: `nslookup antre-dev.gurind.am` harus menunjuk IP server.

---
## C. Coolify

### C1. Buat resource
1. **Projects** → pilih/buat project → **+ New** (di environment `production`).
2. Pilih sumber kode:
   - **Public Repository** → tempel `https://github.com/USERNAME/antrean` → **Check Repository**; atau
   - **Private Repository (with GitHub App)** / **with Deploy Key** bila repo private.
3. **Build Pack: Docker Compose**. Branch: `main`.
4. **Base Directory:** `/`  ·  **Docker Compose Location:** `/docker-compose.coolify.yml`
5. **Save**, lalu buka **Docker Compose Content** dan pastikan terbaca dua service: `db` dan `app`.

### C2. Domain
Di kolom **Domains** untuk service **`app`** isi (perhatikan akhiran `:8000`, itu port internal kontainer):
```
https://antre-dev.gurind.am:8000
```
Service `db` **jangan** diberi domain. Klik **Save**.

### C3. Environment Variables
Tab **Environment Variables** (variabel muncul setelah compose terbaca):

| Variabel | Isi | Wajib |
|---|---|---|
| `ADMIN_PASSWORD` | password login petugas & laporan (panjang, acak) | **Ya** |
| `ADMIN_USER` | default `admin` | tidak |
| `NAMA_INSTANSI` | default `PST BPS Provinsi Kepulauan Riau` | tidak |
| `JUMLAH_MEJA` | default `3` | tidak |

Password database dibuat otomatis oleh Coolify (`SERVICE_PASSWORD_POSTGRES`), tidak perlu diisi.

### C4. Deploy
Klik **Deploy** → buka tab **Deployments** dan tunggu selesai (build pertama 1–3 menit). Status berubah **Running (healthy)**.

---
## D. Verifikasi
1. `https://antre-dev.gurind.am/healthz` → `{"status":"ok"}`
2. `https://antre-dev.gurind.am` → menu (gembok HTTPS aktif).
3. Buka `/kiosk` → klik **Ambil Nomor** → nomor 001 muncul.
4. Buka `/loket/1` → login `ADMIN_USER` / `ADMIN_PASSWORD` → uji Panggil → Mulai → Selesai.
5. Buka `/monitor` di layar TV (Chrome), **klik sekali** agar suara aktif, lalu panggil dari `/loket/1`.
6. Buka `/laporan` → data lama layanan muncul; tombol **Unduh Excel** berfungsi.

---
## E. Deploy otomatis saat `git push`
- **GitHub App** (repo lewat integrasi resmi Coolify): otomatis, tinggal aktifkan **Configuration → Advanced → Deployment → Auto Deploy**.
- **Public URL / deploy key**: pakai webhook manual.
  1. Coolify: **Configuration → Webhooks** → isi **GitHub Webhook Secret** (acak panjang) → **Save** → salin URL **GitHub** di *Manual Git Webhooks*.
  2. GitHub: repo **Settings → Webhooks → Add webhook** → Payload URL = URL tadi, Content type `application/json`, Secret = sama, event **Just the push event**.
  3. Aktifkan **Auto Deploy** di Coolify (Advanced → Deployment).
  4. Uji dengan `git push`; deployment baru harus muncul di tab Deployments.

Rollback: tab **Deployments** → pilih deployment sebelumnya → **Rollback/Redeploy**.

---
## F. Cadangan database
Data ada di volume `pgdata` (tidak hilang saat redeploy). Untuk cadangan, pasang di **server**:
```bash
sudo mkdir -p /opt/backup && sudo cp scripts/backup-coolify.sh /opt/backup/ && sudo chmod +x /opt/backup/backup-coolify.sh
sudo crontab -e     # tambah:  0 2 * * * /opt/backup/backup-coolify.sh >> /var/log/antrian-backup.log 2>&1
```
Salin folder `/opt/backup/antrian` secara berkala ke tempat lain (bukan hanya di server yang sama).
Pulihkan: `gunzip -c FILE.sql.gz | docker exec -i NAMA_KONTAINER_DB psql -U antrian antrian`

---
## G. Masalah umum

| Gejala | Penyebab & solusi |
|---|---|
| **No Available Server** | Domain di Coolify belum ada akhiran `:8000`; atau `app` belum *healthy* (lihat Logs). |
| Sertifikat/HTTPS gagal | DNS belum mengarah ke server, atau Cloudflare masih mode proxy saat penerbitan; port 80/443 server harus terbuka. |
| Deploy ditolak / variabel merah | `ADMIN_PASSWORD` belum diisi (bertanda wajib). |
| `app` restart terus | Cek Logs `app`; biasanya database belum siap atau `ADMIN_PASSWORD` kosong. |
| Suara monitor tidak keluar | Belum klik banner di `/monitor`; atau perangkat belum punya voice bahasa Indonesia (pasang di OS/Chrome). |
| Login `/loket` terus diminta | Password salah; ubah di Environment Variables lalu **Redeploy**. |
| Ganti jumlah meja | Ubah `JUMLAH_MEJA` → Redeploy. |

## Catatan
- **Jangan** menambahkan `ports:` di compose Coolify: itu melewati proxy dan dapat membuka layanan langsung.
- File `docker-compose.yml`, `docker-compose.caddy.yml`, dan `Caddyfile` hanya untuk server tanpa Coolify (lihat `DEPLOY.md`); Coolify memakai `docker-compose.coolify.yml`.
- Nanti untuk produksi: buat resource kedua (atau ganti domain) mis. `antre.gurind.am` dari branch `main`, sedangkan `antre-dev` mengikuti branch `dev`.
