import io
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime
from zoneinfo import ZoneInfo

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
from psycopg.rows import dict_row

DSN = os.environ["DATABASE_URL"]
TZ = ZoneInfo(os.getenv("TZ", "Asia/Jakarta"))
NAMA = os.getenv("NAMA_INSTANSI", "PST BPS Provinsi Kepulauan Riau")
MEJA = int(os.getenv("JUMLAH_MEJA", "3"))
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.environ["ADMIN_PASSWORD"]  # wajib diisi, tidak ada default

SCHEMA = """
CREATE TABLE IF NOT EXISTS antrian (
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
)
"""

# Setiap aksi = satu UPDATE atomik; aturan urutan dijaga di database, bukan di browser.
AKSI = {
    "panggil": """
        UPDATE antrian SET meja=%(m)s, dipanggil_at=COALESCE(dipanggil_at, now()),
               panggil_n=panggil_n+1, last_call_at=now()
        WHERE id=%(id)s AND tanggal=%(t)s AND mulai_at IS NULL AND selesai_at IS NULL
          AND (meja IS NULL OR meja=%(m)s)
          AND NOT EXISTS (SELECT 1 FROM antrian x WHERE x.tanggal=%(t)s AND x.meja=%(m)s
                          AND x.selesai_at IS NULL AND x.id<>%(id)s)
          AND NOT EXISTS (SELECT 1 FROM antrian x WHERE x.tanggal=%(t)s AND x.dipanggil_at IS NULL
                          AND x.id<>%(id)s AND x.nomor<antrian.nomor)
        RETURNING id""",
    "mulai": """UPDATE antrian SET mulai_at=now() WHERE id=%(id)s AND meja=%(m)s
                AND dipanggil_at IS NOT NULL AND mulai_at IS NULL AND selesai_at IS NULL RETURNING id""",
    "selesai": """UPDATE antrian SET selesai_at=now() WHERE id=%(id)s AND meja=%(m)s
                  AND mulai_at IS NOT NULL AND selesai_at IS NULL RETURNING id""",
    "lewati": """UPDATE antrian SET selesai_at=now(), lewat=true WHERE id=%(id)s AND meja=%(m)s
                 AND dipanggil_at IS NOT NULL AND mulai_at IS NULL AND selesai_at IS NULL RETURNING id""",
}


def q(sql, params=None, one=False):
    with psycopg.connect(DSN, row_factory=dict_row) as c:
        cur = c.execute(sql, params)
        rows = cur.fetchall() if cur.description else []
    return (rows[0] if rows else None) if one else rows


def today():
    return datetime.now(TZ).date()


def hms(d):
    return d.astimezone(TZ).strftime("%H:%M:%S") if d else "-"


def mmss(s):
    return "-" if s is None else f"{int(s) // 60:02d}:{int(s) % 60:02d}"


def p3(n):
    return f"{n:03d}" if n else "-"


def dur(a, b):
    return int((b - a).total_seconds()) if a and b else None


@asynccontextmanager
async def lifespan(_):
    q(SCHEMA)
    yield


app = FastAPI(title="Antrian", lifespan=lifespan)
tpl = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
tpl.env.globals.update(hms=hms, mmss=mmss, p3=p3)
basic = HTTPBasic()


def admin(c: HTTPBasicCredentials = Depends(basic)):
    ok = secrets.compare_digest(c.username.encode(), ADMIN_USER.encode()) & \
        secrets.compare_digest(c.password.encode(), ADMIN_PASS.encode())
    if not ok:
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})


def cek_meja(m):
    if not 1 <= m <= MEJA:
        raise HTTPException(404, "Meja tidak ditemukan")


def page(r, name, **ctx):
    return tpl.TemplateResponse(r, name, {"nama": NAMA, **ctx})


# ---------- halaman ----------
@app.get("/healthz")
def healthz():
    q("SELECT 1")
    return {"status": "ok"}


@app.get("/")
def menu(r: Request):
    return page(r, "menu.html", meja=MEJA)


@app.get("/kiosk")
def kiosk(r: Request):
    return page(r, "kiosk.html")


@app.get("/monitor")
def monitor(r: Request):
    return page(r, "monitor.html")


@app.get("/loket/{meja}", dependencies=[Depends(admin)])
def loket(r: Request, meja: int):
    cek_meja(meja)
    return page(r, "loket.html", meja=meja)


@app.get("/laporan", dependencies=[Depends(admin)])
def laporan(r: Request, tanggal: date | None = None):
    d = tanggal or today()
    rows, ring = laporan_data(d)
    return page(r, "laporan.html", tanggal=d.isoformat(), rows=rows, ring=ring)


# ---------- API ----------
@app.post("/api/tiket")
def tiket():
    with psycopg.connect(DSN, row_factory=dict_row) as c:
        c.execute("SELECT pg_advisory_xact_lock(1)")  # nomor tidak bisa kembar
        row = c.execute(
            "INSERT INTO antrian(tanggal, nomor) SELECT %(t)s, COALESCE(MAX(nomor),0)+1 "
            "FROM antrian WHERE tanggal=%(t)s RETURNING nomor", {"t": today()}).fetchone()
    return {"nomor": row["nomor"]}


@app.get("/api/loket/{meja}", dependencies=[Depends(admin)])
def state(meja: int):
    cek_meja(meja)
    asc = q("SELECT * FROM antrian WHERE tanggal=%s ORDER BY nomor", (today(),))
    aktif = next((r for r in asc if r["meja"] == meja and r["dipanggil_at"] and not r["selesai_at"]), None)
    nxt = next((r for r in asc if not r["dipanggil_at"]), None)
    last = max((r for r in asc if r["last_call_at"]), key=lambda r: r["last_call_at"], default=None)
    rows = [{
        "id": r["id"], "nomor": p3(r["nomor"]), "lewat": r["lewat"],
        "panggil": hms(r["dipanggil_at"]), "mulai": hms(r["mulai_at"]), "selesai": hms(r["selesai_at"]),
        "bisa_panggil": bool((r is nxt and not aktif) or (r is aktif and not r["mulai_at"])),
        "bisa_mulai": bool(r is aktif and not r["mulai_at"]),
        "bisa_selesai": bool(r is aktif and r["mulai_at"]),
    } for r in reversed(asc)]
    return {"jumlah": len(asc), "sekarang": p3(last["nomor"]) if last else "-",
            "selanjutnya": p3(nxt["nomor"]) if nxt else "-",
            "sisa": sum(1 for r in asc if not r["dipanggil_at"]), "rows": rows}


@app.post("/api/loket/{meja}/{id}/{aksi}", dependencies=[Depends(admin)])
def lakukan(meja: int, id: int, aksi: str):
    cek_meja(meja)
    if aksi not in AKSI:
        raise HTTPException(404)
    if not q(AKSI[aksi], {"id": id, "m": meja, "t": today()}, one=True):
        raise HTTPException(409, "Aksi tidak diizinkan untuk status antrian saat ini")
    return {"ok": True}


@app.get("/api/monitor")
def api_monitor():
    d = today()
    last = q("SELECT id, nomor, meja, panggil_n FROM antrian WHERE tanggal=%s AND last_call_at IS NOT NULL "
             "ORDER BY last_call_at DESC LIMIT 1", (d,), one=True)
    aktif = q("SELECT meja, nomor FROM antrian WHERE tanggal=%s AND meja IS NOT NULL "
              "AND dipanggil_at IS NOT NULL AND selesai_at IS NULL ORDER BY meja", (d,))
    sisa = q("SELECT count(*) AS n FROM antrian WHERE tanggal=%s AND dipanggil_at IS NULL", (d,), one=True)["n"]
    return {"last": last, "aktif": aktif, "sisa": sisa}


# ---------- laporan ----------
def laporan_data(d):
    rows = q("SELECT * FROM antrian WHERE tanggal=%s ORDER BY nomor", (d,))
    for r in rows:
        r["tunggu"] = dur(r["dibuat_at"], r["dipanggil_at"])
        r["layanan"] = dur(r["mulai_at"], r["selesai_at"])
    lay = [r["layanan"] for r in rows if r["layanan"] is not None]
    tgg = [r["tunggu"] for r in rows if r["tunggu"] is not None]
    ring = {"total": len(rows), "selesai": len(lay), "lewat": sum(r["lewat"] for r in rows),
            "rata_layanan": mmss(sum(lay) / len(lay)) if lay else "-",
            "maks_layanan": mmss(max(lay)) if lay else "-",
            "rata_tunggu": mmss(sum(tgg) / len(tgg)) if tgg else "-"}
    return rows, ring


@app.get("/laporan.xlsx", dependencies=[Depends(admin)])
def laporan_xlsx(tanggal: date | None = None):
    d = tanggal or today()
    rows, _ = laporan_data(d)
    wb = Workbook()
    ws = wb.active
    ws.title = "Laporan"
    ws.append(["Nomor", "Meja", "Ambil", "Panggil", "Mulai", "Selesai", "Waktu Tunggu", "Lama Layanan", "Keterangan"])
    for r in rows:
        ws.append([p3(r["nomor"]), r["meja"] or "-", hms(r["dibuat_at"]), hms(r["dipanggil_at"]),
                   hms(r["mulai_at"]), hms(r["selesai_at"]), mmss(r["tunggu"]), mmss(r["layanan"]),
                   "Tidak hadir" if r["lewat"] else ""])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="laporan-antrian-{d}.xlsx"'})
