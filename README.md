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
| `/data` | **Kelola Data**: edit status/meja/waktu tiket dan hapus data (soft delete: per baris, terpilih, atau semua pada satu tanggal) | ya |
| `/laporan` | Laporan **harian**, **bulanan** (pilih bulan & tahun), **tahunan** (pilih tahun), **rentang tanggal** (awal–akhir, maks 366 hari); grafik, ringkasan per meja, unduh Excel | ya |
| `/pengaturan` | Instansi, footer, meja, logo & warna, suara, printer | ya |

Setiap sub menu punya tombol/breadcrumb kembali ke Beranda.

## Aturan alur
- Satu klik **Panggil** = memanggil + memulai layanan (waktu tercatat sekali) + suara panggilan.
- Nomor berikutnya nonaktif selama meja itu belum menekan **Selesai**; nomor tidak bisa dilompati (dijaga di query SQL, `app/antrian.py`).
- **Tidak hadir**: menutup nomor tanpa dihitung dalam rata-rata lama layanan.
- Lama layanan = selesai − mulai. Waktu tunggu = dipanggil − diambil. Zona waktu WIB.

## Laporan
Semua jenis laporan (dan unduhan Excel) wajib login. Isi: total antrian, selesai dilayani, tidak hadir, rata-rata/terlama/tercepat lama layanan,
rata-rata waktu tunggu, grafik jumlah & lama layanan (per jam untuk harian, per hari untuk bulanan/rentang ≤ 62 hari, per bulan untuk tahunan/rentang lebih panjang),
ringkasan per meja, dan detail per antrian (di layar jika ≤ 300 baris; selengkapnya di Excel).
Excel berisi lembar **Ringkasan**, **Rincian** (per jam/hari/bulan), dan **Detail** (semua antrian, bisa difilter). Nomor yang tidak dipanggil atau tidak ditutup
pada hari yang sudah lewat tercatat sebagai "tidak dilayani / belum ditutup" dan tidak ikut rata-rata lama layanan.

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
**Lama tunggu antre** (laporan, Excel, dan Kelola Data): dihitung sampai nomor dipanggil, mulai dari saat ambil nomor untuk antrian pertama, dan mulai dari saat layanan sebelumnya (meja 1/2) selesai untuk antrian berikutnya. Jika nomor baru diambil setelah layanan sebelumnya selesai, dihitung sejak ambil nomor. Nilai dihitung saat laporan dibuka (tidak disimpan di database), jadi ikut berubah bila waktu dikoreksi.

Hapus data di menu **Kelola Data** adalah *soft delete*: baris tetap ada di `queue_tiket` dengan kolom `dihapus_at` terisi, tidak tampil di antrian/laporan. Lihat datanya: `SELECT * FROM queue_tiket WHERE dihapus_at IS NOT NULL;`
Saat pertama kali jalan, pengaturan awal (nama, alamat, YouTube, warna, daftar meja) otomatis dibaca dari tabel lama `queue_setting` bila ada.

## Struktur
```
app/main.py         route halaman & API      app/pengaturan.py  pengaturan, logo, YouTube
app/antrian.py      logika antrian           app/laporan.py     laporan & Excel
app/kelola.py       edit & hapus data tiket
app/printer.py      cetak ESC/POS
app/suara.py        suara server (espeak-ng) app/db.py           koneksi & skema
app/templates/      HTML (Jinja)             app/static/        CSS, JS, Bootstrap lokal
tests/              uji otomatis (pytest)    scripts/schema.sql SQL manual (opsional)
```
Uji: `pip install -r requirements-dev.txt && pytest -q` (memakai PostgreSQL tertanam, tidak menyentuh database Anda).

Rahasia hanya di Environment Variables/`.env` (ada di `.gitignore`), tidak ada kredensial di kode.
