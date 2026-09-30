# Aplikasi Antrian

Sistem antrian layanan: ambil nomor, panggil (otomatis mulai layanan), selesai, layar monitor, dan laporan lama layanan harian.
Stack: Python 3.12 · FastAPI · PostgreSQL · Bootstrap 5 (disalin lokal) · Docker.

## Halaman
| URL | Fungsi | Login |
|---|---|---|
| `/` | Beranda: pilih halaman, footer bisa diubah di Setting | – |
| `/kiosk` | Pengunjung ambil nomor (tanpa tombol cetak) | – |
| `/monitor` | Layar TV PST: video YouTube berulang, nomor sekarang, selanjutnya + meja, sisa antrian, suara panggilan | – |
| `/loket/{n}` | Petugas meja: **Panggil** (sekaligus mulai) → **Selesai** (+ panggil ulang, tidak hadir) | ya |
| `/laporan` | Lama layanan, waktu tunggu, grafik per jam, ringkasan per meja, unduh Excel | ya |
| `/pengaturan` | Instansi, footer, meja, logo & warna, suara, printer | ya |

Setiap sub menu punya tombol/breadcrumb kembali ke Beranda.

## Aturan alur
- Satu klik **Panggil** = memanggil + memulai layanan (waktu tercatat sekali) + suara panggilan.
- Nomor berikutnya nonaktif selama meja itu belum menekan **Selesai**; nomor tidak bisa dilompati (dijaga di query SQL, `app/antrian.py`).
- **Tidak hadir**: menutup nomor tanpa dihitung dalam rata-rata lama layanan.
- Lama layanan = selesai − mulai. Waktu tunggu = dipanggil − diambil. Zona waktu WIB.

## Suara panggilan
Bunyi "ting-tung" lalu ucapan ("Nomor antrian, dua, silakan menuju, meja satu"). Diputar di **halaman petugas** saat klik Panggil dan di **layar monitor**
(masing-masing bisa dimatikan di Setting). Memakai suara Indonesia bawaan browser bila ada; jika tidak, otomatis memakai suara dari server (espeak-ng).
Monitor perlu satu kali klik "Aktifkan Suara". Untuk PC monitor tanpa klik: jalankan Chrome dengan
`chrome --kiosk --autoplay-policy=no-user-gesture-required https://DOMAIN/monitor`.

## Printer (nonaktif bawaan)
Tombol cetak tidak tampil. Untuk mengaktifkan: Setting → Printer (IP, port 9100, lebar kertas) → **Tes Cetak** → aktifkan saklar.
Mendukung printer thermal ESC/POS yang menerima cetak langsung lewat jaringan.

## Menjalankan lokal
```bash
cp .env.example .env      # isi DB_PASSWORD dan ADMIN_PASSWORD
docker compose up -d --build
```
Buka `http://localhost:8000`. Tabel dibuat otomatis saat start.
Deploy dengan **Coolify + GitHub + PostgreSQL sendiri**: ikuti **[PANDUAN-COOLIFY.md](PANDUAN-COOLIFY.md)**.
Server biasa tanpa Coolify: lihat **[DEPLOY.md](DEPLOY.md)**.

## Data
Tabel yang dibuat aplikasi (tabel lain di database tidak disentuh): `queue_tiket` (riwayat antrian & waktu), `queue_pengaturan` (pengaturan), `queue_logo` (logo).
Saat pertama kali jalan, pengaturan awal (nama, alamat, YouTube, warna, daftar meja) otomatis dibaca dari tabel lama `queue_setting` bila ada.

## Struktur
```
app/main.py         route halaman & API      app/pengaturan.py  pengaturan, logo, YouTube
app/antrian.py      logika antrian & laporan app/printer.py      cetak ESC/POS
app/suara.py        suara server (espeak-ng) app/db.py           koneksi & skema
app/templates/      HTML (Jinja)             app/static/        CSS, JS, Bootstrap lokal
tests/              uji otomatis (pytest)    scripts/schema.sql SQL manual (opsional)
```
Uji: `pip install -r requirements-dev.txt && pytest -q` (memakai PostgreSQL tertanam, tidak menyentuh database Anda).

Rahasia hanya di Environment Variables/`.env` (ada di `.gitignore`), tidak ada kredensial di kode.
