"""Fungsi kecil: terbilang, format waktu Indonesia."""
import re
from datetime import date, datetime

from .config import TZ

_SATUAN = ["nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas"]
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September",
         "Oktober", "November", "Desember"]


def terbilang(n: int) -> str:
    n = int(n)
    if n < 12:
        return _SATUAN[n]
    if n < 20:
        return _SATUAN[n - 10] + " belas"
    if n < 100:
        return _SATUAN[n // 10] + " puluh" + (" " + _SATUAN[n % 10] if n % 10 else "")
    if n < 200:
        return "seratus" + (" " + terbilang(n - 100) if n > 100 else "")
    if n < 1000:
        return _SATUAN[n // 100] + " ratus" + (" " + terbilang(n % 100) if n % 100 else "")
    if n < 2000:
        return "seribu" + (" " + terbilang(n - 1000) if n > 1000 else "")
    return terbilang(n // 1000) + " ribu" + (" " + terbilang(n % 1000) if n % 1000 else "")


def ucapan_meja(nama: str) -> str:
    """'Meja 12' -> 'Meja dua belas' agar terbaca benar oleh mesin suara."""
    return re.sub(r"\d+", lambda m: terbilang(int(m.group())), nama)


def teks_panggil(nomor: int, nama_meja: str) -> str:
    return f"Nomor antrian, {terbilang(nomor)}, silakan menuju, {ucapan_meja(nama_meja)}"


def p3(n) -> str:
    return f"{int(n):03d}" if n else "-"


def hms(d) -> str:
    return d.astimezone(TZ).strftime("%H:%M:%S") if d else "-"


def mmss(s) -> str:
    return "-" if s is None else f"{int(s) // 60:02d}:{int(s) % 60:02d}"


def dur(a, b):
    return int((b - a).total_seconds()) if a and b else None


def sekarang() -> datetime:
    return datetime.now(TZ)


def hari_ini() -> date:
    return sekarang().date()


def tanggal_id(d, dengan_jam=False) -> str:
    s = f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month]} {d.year}"
    return s + (f" {d:%H:%M}" if dengan_jam else "")
