"""Logika antrian: ambil nomor, panggil (+mulai), selesai, monitor, laporan."""
from datetime import datetime, timezone


from . import pengaturan
from .db import pool, q
from .util import dur, hari_ini, hms, mmss, p3, teks_panggil

# Setiap aksi = satu UPDATE atomik; aturan urutan dijaga di database, bukan di browser.
# "panggil" = memanggil sekaligus memulai layanan (dan bisa diulang untuk panggil ulang).
AKSI = {
    "panggil": """
        UPDATE queue_tiket SET meja=%(m)s,
               dipanggil_at=COALESCE(dipanggil_at, now()), mulai_at=COALESCE(mulai_at, now()),
               panggil_n=panggil_n+1, last_call_at=now()
        WHERE id=%(id)s AND tanggal=%(t)s AND selesai_at IS NULL
          AND (meja IS NULL OR meja=%(m)s)
          AND NOT EXISTS (SELECT 1 FROM queue_tiket x WHERE x.tanggal=%(t)s AND x.meja=%(m)s
                          AND x.selesai_at IS NULL AND x.id<>%(id)s)
          AND NOT EXISTS (SELECT 1 FROM queue_tiket x WHERE x.tanggal=%(t)s AND x.dipanggil_at IS NULL
                          AND x.id<>%(id)s AND x.nomor<queue_tiket.nomor)
        RETURNING id, nomor, meja, panggil_n""",
    "selesai": """
        UPDATE queue_tiket SET selesai_at=now(), mulai_at=COALESCE(mulai_at, dipanggil_at)
        WHERE id=%(id)s AND tanggal=%(t)s AND meja=%(m)s AND dipanggil_at IS NOT NULL AND selesai_at IS NULL
        RETURNING id, nomor, meja, panggil_n""",
    "lewati": """
        UPDATE queue_tiket SET selesai_at=now(), lewat=true, mulai_at=COALESCE(mulai_at, dipanggil_at)
        WHERE id=%(id)s AND tanggal=%(t)s AND meja=%(m)s AND dipanggil_at IS NOT NULL AND selesai_at IS NULL
        RETURNING id, nomor, meja, panggil_n""",
}


def tiket_baru() -> dict:
    t = hari_ini()
    with pool.connection() as c:
        c.execute("SELECT pg_advisory_xact_lock(%s)", (74200101,))  # nomor tidak bisa kembar
        r = c.execute(
            "INSERT INTO queue_tiket(tanggal, nomor) SELECT %(t)s, COALESCE(MAX(nomor),0)+1 "
            "FROM queue_tiket WHERE tanggal=%(t)s RETURNING nomor", {"t": t}).fetchone()
    depan = q("SELECT count(*) AS n FROM queue_tiket WHERE tanggal=%s AND dipanggil_at IS NULL AND nomor<%s",
              (t, r["nomor"]), one=True)["n"]
    return {"nomor": r["nomor"], "nomor_txt": p3(r["nomor"]), "depan": depan}


def lakukan(meja: int, id_: int, aksi: str, p: dict):
    r = q(AKSI[aksi], {"id": id_, "m": meja, "t": hari_ini()}, one=True)
    if not r:
        return None
    r["nomor_txt"] = p3(r["nomor"])
    r["teks"] = teks_panggil(r["nomor"], pengaturan.nama_meja(p, meja) or f"Meja {meja}")
    return r


def state(meja: int) -> dict:
    """Data halaman loket."""
    t, kini = hari_ini(), datetime.now(timezone.utc)
    asc = q("SELECT * FROM queue_tiket WHERE tanggal=%s ORDER BY nomor", (t,))
    saya = next((r for r in asc if r["meja"] == meja and r["dipanggil_at"] and not r["selesai_at"]), None)
    nxt = next((r for r in asc if not r["dipanggil_at"]), None)
    last = max((r for r in asc if r["last_call_at"]), key=lambda r: r["last_call_at"], default=None)

    def grup(r):
        if r is saya:
            return 0
        if not r["dipanggil_at"]:
            return 1
        return 2 if not r["selesai_at"] else 3

    rows = []
    for r in sorted(asc, key=lambda r: (grup(r), r["nomor"] if grup(r) < 3 else -r["nomor"])):
        g = grup(r)
        aktif = bool(r["dipanggil_at"] and not r["selesai_at"])
        status = "aktif" if aktif else ("menunggu" if not r["dipanggil_at"] else ("lewat" if r["lewat"] else "selesai"))
        rows.append({
            "id": r["id"], "nomor": p3(r["nomor"]), "status": status, "meja": r["meja"],
            "panggil": hms(r["dipanggil_at"]), "selesai": hms(r["selesai_at"]),
            "durasi": mmss(dur(r["mulai_at"], r["selesai_at"])) if status == "selesai" else "-",
            "berjalan": int((kini - r["mulai_at"]).total_seconds()) if aktif and r["mulai_at"] else 0,
            "bisa_panggil": bool(r is nxt and not saya),
            "bisa_ulang": g == 0, "bisa_selesai": g == 0, "bisa_lewati": g == 0,
        })
    return {"jumlah": len(asc), "sekarang": p3(last["nomor"]) if last else "-",
            "selanjutnya": p3(nxt["nomor"]) if nxt else "-",
            "sisa": sum(1 for r in asc if not r["dipanggil_at"]),
            "saya": p3(saya["nomor"]) if saya else None, "rows": rows}


def monitor(p: dict) -> dict:
    t = hari_ini()
    last = q("SELECT id, nomor, meja, panggil_n FROM queue_tiket WHERE tanggal=%s AND last_call_at IS NOT NULL "
             "ORDER BY last_call_at DESC LIMIT 1", (t,), one=True)
    aktif = q("SELECT meja, nomor FROM queue_tiket WHERE tanggal=%s AND meja IS NOT NULL "
              "AND dipanggil_at IS NOT NULL AND selesai_at IS NULL ORDER BY meja", (t,))
    nxt = q("SELECT min(nomor) AS n, count(*) AS sisa FROM queue_tiket WHERE tanggal=%s AND dipanggil_at IS NULL",
            (t,), one=True)
    out = {"versi": p["_versi"], "sisa": nxt["sisa"], "selanjutnya": p3(nxt["n"]),
           "suara": {"aktif": p["suara_monitor"], "engine": p["suara_engine"]},
           "aktif": [{"meja": a["nama"], "nomor": p3(a["nomor"])} for a in
                     ({"nama": pengaturan.nama_meja(p, r["meja"]) or f"Meja {r['meja']}", "nomor": r["nomor"]} for r in aktif)],
           "last": None}
    if last:
        nama = pengaturan.nama_meja(p, last["meja"]) or f"Meja {last['meja']}"
        out["last"] = {"kunci": f"{last['id']}:{last['panggil_n']}", "nomor": last["nomor"], "nomor_txt": p3(last["nomor"]),
                       "meja": last["meja"], "meja_nama": nama, "teks": teks_panggil(last["nomor"], nama)}
    return out
