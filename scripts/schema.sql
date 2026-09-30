-- Menambah tabel queue_tiket ke database yang sudah ada (mis. db-antre). Tabel lama TIDAK disentuh.
-- Opsional: aplikasi membuatnya otomatis saat start (CREATE TABLE IF NOT EXISTS)
-- bila user database berhak membuat tabel di schema public.
-- Jalankan manual jika user aplikasi tidak punya hak CREATE:
--   psql "host=HOST dbname=db-antre user=ADMIN" -f scripts/schema.sql
CREATE TABLE IF NOT EXISTS queue_tiket (
  id           bigserial PRIMARY KEY,
  tanggal      date        NOT NULL,
  nomor        int         NOT NULL,
  meja         int,
  dibuat_at    timestamptz NOT NULL DEFAULT now(),
  dipanggil_at timestamptz,
  mulai_at     timestamptz,
  selesai_at   timestamptz,
  lewat        boolean     NOT NULL DEFAULT false,
  panggil_n    int         NOT NULL DEFAULT 0,
  last_call_at timestamptz,
  UNIQUE (tanggal, nomor)
);

-- Beri hak ke user aplikasi (ganti NAMA_USER) bila tabel dibuat oleh user lain:
-- GRANT SELECT, INSERT, UPDATE ON queue_tiket TO NAMA_USER;
-- GRANT USAGE, SELECT ON SEQUENCE queue_tiket_id_seq TO NAMA_USER;
