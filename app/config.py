"""Konfigurasi dari environment variable."""
import hashlib
import os
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv("TZ", "Asia/Jakarta"))
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.environ["ADMIN_PASSWORD"]  # wajib, tanpa default
NAMA_DEFAULT = os.getenv("NAMA_INSTANSI", "Pelayanan Statistik Terpadu")
JUMLAH_MEJA = int(os.getenv("JUMLAH_MEJA", "3"))  # hanya untuk isian awal daftar meja
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"  # 1 = cookie login hanya lewat HTTPS
SECRET_KEY = os.getenv("SECRET_KEY") or hashlib.sha256(("antrian-sesi:" + ADMIN_PASS).encode()).hexdigest()
SESI_DETIK = 12 * 3600
