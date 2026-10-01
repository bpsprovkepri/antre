"""Koneksi PostgreSQL (pool) dan skema tabel."""
import os
import time

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _dsn() -> str:
    """DATABASE_URL (jika ada) menang; jika tidak dirakit dari DB_* (key/value, aman untuk karakter khusus)."""
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    return make_conninfo(
        host=os.environ["DB_HOST"],
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.getenv("DB_PASS", ""),
        sslmode=os.getenv("DB_SSLMODE", "prefer"),
        connect_timeout="5",
    )


pool = ConnectionPool(
    _dsn(), min_size=1, max_size=int(os.getenv("DB_POOL_MAX", "8")), open=False, timeout=10,
    kwargs={"row_factory": dict_row}, check=ConnectionPool.check_connection,
)

TABEL = [
    """CREATE TABLE IF NOT EXISTS queue_tiket (
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
      dihapus_at   timestamptz
    )""",
    # Hapus data = soft delete: baris tetap ada, dihapus_at terisi, dan tidak ikut antrian/laporan.
    "ALTER TABLE queue_tiket ADD COLUMN IF NOT EXISTS dihapus_at timestamptz",
    # nomor harus unik hanya di antara data yang belum dihapus (nomor bekas data terhapus boleh dipakai lagi)
    "ALTER TABLE queue_tiket DROP CONSTRAINT IF EXISTS queue_tiket_tanggal_nomor_key",
    "CREATE UNIQUE INDEX IF NOT EXISTS queue_tiket_nomor_aktif ON queue_tiket (tanggal, nomor) WHERE dihapus_at IS NULL",
    """CREATE TABLE IF NOT EXISTS queue_pengaturan (
      kunci     text PRIMARY KEY,
      nilai     text NOT NULL DEFAULT '',
      diubah_at timestamptz NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS queue_logo (
      id        smallint PRIMARY KEY,
      tipe      text  NOT NULL,
      data      bytea NOT NULL,
      diubah_at timestamptz NOT NULL DEFAULT now()
    )""",
]


def q(sql, params=None, one=False):
    with pool.connection() as c:
        cur = c.execute(sql, params)
        rows = cur.fetchall() if cur.description else []
    return (rows[0] if rows else None) if one else rows


def init():
    """Buka pool dan buat tabel; menunggu database siap (10x, jeda 3 detik)."""
    pool.open(wait=False)
    for i in range(10):
        try:
            for s in TABEL:
                q(s)
            return
        except psycopg.Error:
            if i == 9:
                raise
            time.sleep(3)


def tutup():
    pool.close()
