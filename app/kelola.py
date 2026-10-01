"""Kelola data: koreksi (status, meja, waktu) dan hapus tiket antrian. Khusus petugas yang sudah login."""
import logging
from datetime import date, datetime, timedelta

from . import pengaturan
from .config import TZ
from .db import pool, q
from .util import dur, hms, mmss, p3, sekarang

log = logging.getLogger("uvicorn.error")
KUNCI = 74200101          # sama dengan antrian.tiket_baru: pembuatan nomor & hapus/ubah tidak saling menabrak
MAKS_HAPUS = 2000         # batas jumlah id sekali hapus
STATUS = ("menunggu", "aktif", "selesai", "lewat")


class DataError(ValueError):
    """Isian tidak valid; pesannya langsung ditampilkan ke petugas."""


class TidakAda(LookupError):
    pass


def status_tiket(r: dict) -> str:
    if not r["dipanggil_at"]:
        return "menunggu"
    if not r["selesai_at"]:
        return "aktif"
    return "lewat" if r["lewat"] else "selesai"


def _lokal(d) -> str:
    """Format untuk <input type=datetime-local> (waktu Jakarta, sampai detik)."""
    return d.astimezone(TZ).strftime("%Y-%m-%dT%H:%M:%S") if d else ""


def daftar(tanggal: date) -> list:
    p = pengaturan.get()
    out = []
    for r in q("SELECT * FROM queue_tiket WHERE tanggal=%s ORDER BY nomor", (tanggal,)):
        st = status_tiket(r)
        out.append({
            "id": r["id"], "nomor": r["nomor"], "nomor_txt": p3(r["nomor"]), "status": st,
            "meja": r["meja"], "meja_nama": (pengaturan.nama_meja(p, r["meja"]) or f"Meja {r['meja']}") if r["meja"] else "-",
            "dibuat": hms(r["dibuat_at"]), "dipanggil": hms(r["dipanggil_at"]), "selesai": hms(r["selesai_at"]),
            "durasi": mmss(dur(r["mulai_at"], r["selesai_at"])) if st == "selesai" else "-",
            "dibuat_iso": _lokal(r["dibuat_at"]), "dipanggil_iso": _lokal(r["dipanggil_at"]), "selesai_iso": _lokal(r["selesai_at"]),
        })
    return out


def _waktu(nilai, label: str, wajib: bool):
    """'2026-10-01T09:30[:15]' (waktu Jakarta) -> datetime berzona waktu; kosong -> None."""
    s = (nilai or "").strip() if isinstance(nilai, str) else ""
    if not s:
        if wajib:
            raise DataError(f"Waktu {label} wajib diisi")
        return None
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        raise DataError(f"Waktu {label} tidak valid")
    return d.replace(tzinfo=TZ) if d.tzinfo is None else d.astimezone(TZ)


def periksa(r: dict, data: dict, p: dict, meja_aktif_lain) -> dict:
    """Validasi isian edit terhadap tiket `r`; kembalikan nilai kolom baru. `meja_aktif_lain(meja)` -> bool."""
    st = data.get("status")
    if st not in STATUS:
        raise DataError("Status tidak dikenal")
    dibuat = _waktu(data.get("dibuat"), "ambil nomor", True)
    dipanggil = selesai = meja = None
    if st != "menunggu":
        try:
            meja = int(data.get("meja"))
        except (TypeError, ValueError):
            raise DataError("Pilih meja layanan")
        if pengaturan.nama_meja(p, meja) is None:
            raise DataError("Meja tidak ditemukan")
        dipanggil = _waktu(data.get("dipanggil"), "dipanggil", True)
    if st in ("selesai", "lewat"):
        selesai = _waktu(data.get("selesai"), "selesai", True)

    urut = [("ambil nomor", dibuat), ("dipanggil", dipanggil), ("selesai", selesai)]
    urut = [(n, w) for n, w in urut if w]
    for (n1, w1), (n2, w2) in zip(urut, urut[1:]):
        if w2 < w1:
            raise DataError(f"Waktu {n2} tidak boleh lebih awal dari waktu {n1}")
    batas = sekarang() + timedelta(minutes=1)
    for n, w in urut:
        if w > batas:
            raise DataError(f"Waktu {n} tidak boleh di masa depan")
        if w.astimezone(TZ).date() != r["tanggal"]:
            raise DataError(f"Waktu {n} harus berada pada tanggal tiket ({r['tanggal']:%d-%m-%Y})")
    if st == "aktif" and meja_aktif_lain(meja):
        raise DataError(f"{pengaturan.nama_meja(p, meja)} sedang melayani nomor lain. Selesaikan atau ubah dulu nomor tersebut")

    return {"meja": meja, "dibuat_at": dibuat, "dipanggil_at": dipanggil, "mulai_at": dipanggil,
            "selesai_at": selesai, "lewat": st == "lewat"}


def ubah(id_: int, data: dict, p: dict) -> dict:
    with pool.connection() as c:
        c.execute("SELECT pg_advisory_xact_lock(%s)", (KUNCI,))
        r = c.execute("SELECT * FROM queue_tiket WHERE id=%s", (id_,)).fetchone()
        if not r:
            raise TidakAda("Data tidak ditemukan (mungkin sudah dihapus)")

        def meja_aktif_lain(m):
            return c.execute("SELECT 1 FROM queue_tiket WHERE tanggal=%s AND meja=%s AND dipanggil_at IS NOT NULL "
                             "AND selesai_at IS NULL AND id<>%s LIMIT 1", (r["tanggal"], m, id_)).fetchone() is not None

        v = periksa(r, data, p, meja_aktif_lain)
        called = v["dipanggil_at"] is not None
        c.execute("UPDATE queue_tiket SET meja=%(meja)s, dibuat_at=%(dibuat_at)s, dipanggil_at=%(dipanggil_at)s, "
                  "mulai_at=%(mulai_at)s, selesai_at=%(selesai_at)s, lewat=%(lewat)s, panggil_n=%(pn)s, last_call_at=%(lc)s "
                  "WHERE id=%(id)s",
                  {**v, "id": id_, "pn": max(r["panggil_n"], 1) if called else 0,
                   "lc": (r["last_call_at"] or v["dipanggil_at"]) if called else None})
    log.info("kelola: ubah tiket id=%s tanggal=%s nomor=%s -> %s", id_, r["tanggal"], r["nomor"], data.get("status"))
    return {"id": id_, "nomor_txt": p3(r["nomor"])}


def hapus(ids: list) -> int:
    """Hapus tiket terpilih; mengembalikan jumlah yang benar-benar terhapus."""
    try:
        ids = sorted({int(i) for i in ids})
    except (TypeError, ValueError):
        raise DataError("Daftar data tidak valid")
    if not ids:
        raise DataError("Belum ada data yang dipilih")
    if len(ids) > MAKS_HAPUS:
        raise DataError(f"Maksimal {MAKS_HAPUS} data sekali hapus")
    with pool.connection() as c:
        c.execute("SELECT pg_advisory_xact_lock(%s)", (KUNCI,))
        n = c.execute("DELETE FROM queue_tiket WHERE id = ANY(%s)", (ids,)).rowcount
    log.info("kelola: hapus %s tiket (id=%s)", n, ids[:20])
    return n


def hapus_tanggal(tanggal: date) -> int:
    """Hapus semua tiket pada satu tanggal (nomor antrian hari itu mulai lagi dari 1)."""
    with pool.connection() as c:
        c.execute("SELECT pg_advisory_xact_lock(%s)", (KUNCI,))
        n = c.execute("DELETE FROM queue_tiket WHERE tanggal=%s", (tanggal,)).rowcount
    log.info("kelola: hapus semua tiket tanggal %s (%s data)", tanggal, n)
    return n
