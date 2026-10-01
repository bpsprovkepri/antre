"""Aplikasi Antrian: route halaman & API. Logika ada di antrian.py, pengaturan.py, printer.py, suara.py."""
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date
from urllib.parse import quote

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from . import antrian, config, db, kelola, laporan as lap, pengaturan, printer, suara
from .util import hari_ini, tanggal_id

BASE = os.path.dirname(os.path.abspath(__file__))


@asynccontextmanager
async def lifespan(_):
    db.init()
    pengaturan.seed()
    yield
    db.tutup()


app = FastAPI(title="Antrian", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, max_age=config.SESI_DETIK,
                   same_site="lax", https_only=config.COOKIE_SECURE, session_cookie="antrian_sesi")
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
tpl = Jinja2Templates(directory=os.path.join(BASE, "templates"))


@app.middleware("http")
async def header_umum(request: Request, call_next):
    r = await call_next(request)
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("Referrer-Policy", "same-origin")
    r.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    if request.url.path.startswith("/api/"):
        r.headers["Cache-Control"] = "no-store"
    return r


# ---------- auth (sesi + halaman login) ----------
class PerluLogin(Exception):
    def __init__(self, tujuan: str):
        self.tujuan = tujuan


@app.exception_handler(PerluLogin)
async def _perlu_login(_, e: PerluLogin):
    return RedirectResponse(f"/login?next={quote(e.tujuan)}", status_code=303)


def is_admin(request: Request) -> bool:
    return bool(request.session.get("admin"))


def admin_halaman(request: Request):
    if not is_admin(request):
        tujuan = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        raise PerluLogin(tujuan)


def admin_api(request: Request):
    if not is_admin(request):
        raise HTTPException(401, "Sesi login berakhir, silakan login kembali")


def _aman(tujuan: str) -> str:
    return tujuan if tujuan.startswith("/") and not tujuan.startswith("//") and "\\" not in tujuan else "/"


_gagal: dict = {}  # ip -> (jumlah gagal, terkunci sampai)


def render(request: Request, nama: str, status_code: int = 200, **extra):
    p = pengaturan.get()
    ctx = {"p": p, "warna": pengaturan.tema(p), "footer": pengaturan.footer_teks(p),
           "logo": f"/logo?v={p['_versi']}", "admin": is_admin(request), **extra}
    return tpl.TemplateResponse(request, nama, ctx, status_code=status_code)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/pengaturan"):
    if is_admin(request):
        return RedirectResponse(_aman(next), 303)
    return render(request, "login.html", next=_aman(next), error=None)


@app.post("/login")
def login_kirim(request: Request, username: str = Form(""), password: str = Form(""), next: str = Form("/")):
    ip = request.client.host if request.client else "?"
    n, sampai = _gagal.get(ip, (0, 0))
    if sampai > time.time():
        return render(request, "login.html", 429, next=_aman(next), error="Terlalu banyak percobaan, coba lagi 1 menit lagi.")
    ok = secrets.compare_digest(username.encode(), config.ADMIN_USER.encode()) & \
        secrets.compare_digest(password.encode(), config.ADMIN_PASS.encode())
    if not ok:
        n += 1
        _gagal[ip] = (n, time.time() + 60 if n >= 5 else 0)
        return render(request, "login.html", 401, next=_aman(next), error="Username atau password salah.")
    _gagal.pop(ip, None)
    request.session["admin"] = True
    return RedirectResponse(_aman(next), 303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", 303)


# ---------- halaman ----------
@app.get("/healthz")
def healthz():
    db.q("SELECT 1")
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def beranda(request: Request):
    return render(request, "beranda.html")


@app.get("/kiosk", response_class=HTMLResponse)
def kiosk(request: Request):
    return render(request, "kiosk.html")


@app.get("/monitor", response_class=HTMLResponse)
def monitor(request: Request):
    p = pengaturan.get()
    return render(request, "monitor.html", youtube=pengaturan.youtube_embed(p["youtube_id"]))


def _cek_meja(no: int) -> str:
    nama = pengaturan.nama_meja(pengaturan.get(), no)
    if nama is None:
        raise HTTPException(404, "Meja tidak ditemukan")
    return nama


@app.get("/loket/{meja}", response_class=HTMLResponse, dependencies=[Depends(admin_halaman)])
def loket(request: Request, meja: int):
    return render(request, "loket.html", meja=meja, meja_nama=_cek_meja(meja))


def _periode(jenis, tanggal, bulan, tahun, awal, akhir):
    """Periode dari query string; bila tidak valid kembali ke laporan harian hari ini + pesan kesalahan."""
    try:
        return lap.periode(jenis, tanggal, bulan, tahun, awal, akhir), None
    except lap.PeriodeError as e:
        return lap.periode("harian"), str(e)


@app.get("/laporan", response_class=HTMLResponse, dependencies=[Depends(admin_halaman)])
def laporan(request: Request, jenis: str = "harian", tanggal: date | None = None, bulan: int | None = None,
            tahun: int | None = None, awal: date | None = None, akhir: date | None = None):
    per, err = _periode(jenis, tanggal, bulan, tahun, awal, akhir)
    return render(request, "laporan.html", 422 if err else 200, per=per, err=err, nav=lap.navigasi(per),
                  tahun_opsi=lap.opsi_tahun(per), nama_bulan=lap.BULAN, **lap.data(per, pengaturan.get()))


@app.get("/laporan.xlsx", dependencies=[Depends(admin_halaman)])
def laporan_xlsx(jenis: str = "harian", tanggal: date | None = None, bulan: int | None = None,
                 tahun: int | None = None, awal: date | None = None, akhir: date | None = None):
    per, err = _periode(jenis, tanggal, bulan, tahun, awal, akhir)
    if err:
        raise HTTPException(422, err)
    return Response(lap.xlsx(per, pengaturan.get()),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="laporan-antrian-{per["kode"]}.xlsx"'})


@app.get("/pengaturan", response_class=HTMLResponse, dependencies=[Depends(admin_halaman)])
def halaman_pengaturan(request: Request):
    return render(request, "pengaturan.html", suara_server=suara.tersedia())


@app.get("/data", response_class=HTMLResponse, dependencies=[Depends(admin_halaman)])
def halaman_data(request: Request, tanggal: date | None = None):
    t = tanggal or hari_ini()
    return render(request, "data.html", tanggal=t, tanggal_iso=t.isoformat(), tanggal_teks=tanggal_id(t),
                  hari_ini=hari_ini().isoformat())


@app.get("/logo")
def logo():
    r = pengaturan.ambil_logo()
    if r:
        return Response(bytes(r["data"]), media_type=r["tipe"], headers={"Cache-Control": "public, max-age=300"})
    return FileResponse(os.path.join(BASE, "static", "img", "logo-default.svg"), media_type="image/svg+xml")


# ---------- API publik ----------
@app.post("/api/tiket")
def api_tiket(tugas: BackgroundTasks):
    t = antrian.tiket_baru()
    p = pengaturan.get()
    if p["printer_aktif"]:
        tugas.add_task(printer.cetak, p, t["nomor"])
    return {**t, "cetak": p["printer_aktif"]}


@app.get("/api/monitor")
def api_monitor():
    return antrian.monitor(pengaturan.get())


@app.get("/api/suara")
def api_suara(nomor: int, meja: int):
    if not (1 <= nomor <= 9999 and 1 <= meja <= 99):
        raise HTTPException(400, "Parameter tidak valid")
    if not suara.tersedia():
        raise HTTPException(503, "Suara server tidak tersedia")
    from .util import teks_panggil
    nama = pengaturan.nama_meja(pengaturan.get(), meja) or f"Meja {meja}"
    try:
        wav = suara.sintesis(teks_panggil(nomor, nama))
    except Exception:
        raise HTTPException(503, "Gagal membuat suara")
    return Response(wav, media_type="audio/wav", headers={"Cache-Control": "public, max-age=86400"})


# ---------- API petugas ----------
@app.get("/api/loket/{meja}", dependencies=[Depends(admin_api)])
def api_loket(meja: int):
    _cek_meja(meja)
    p = pengaturan.get()
    return {**antrian.state(meja), "suara": {"aktif": p["suara_loket"], "engine": p["suara_engine"]}}


@app.post("/api/loket/{meja}/{id_}/{aksi}", dependencies=[Depends(admin_api)])
def api_aksi(meja: int, id_: int, aksi: str):
    _cek_meja(meja)
    if aksi not in antrian.AKSI:
        raise HTTPException(404, "Aksi tidak dikenal")
    r = antrian.lakukan(meja, id_, aksi, pengaturan.get())
    if not r:
        raise HTTPException(409, "Aksi tidak diizinkan untuk status antrian saat ini")
    return {"ok": True, "nomor": r["nomor"], "nomor_txt": r["nomor_txt"], "meja": r["meja"], "teks": r["teks"], "n": r["panggil_n"]}


# ---------- API kelola data (koreksi & hapus) ----------
class UbahTiket(BaseModel):
    status: str = ""
    meja: int | None = None
    dibuat: str | None = None
    dipanggil: str | None = None
    selesai: str | None = None


class HapusTiket(BaseModel):
    ids: list[int] = []


class HapusTanggal(BaseModel):
    tanggal: date


def _kelola(fn, *a):
    try:
        return fn(*a)
    except kelola.TidakAda as e:
        raise HTTPException(404, str(e))
    except kelola.DataError as e:
        raise HTTPException(422, str(e))


@app.get("/api/data", dependencies=[Depends(admin_api)])
def api_data(tanggal: date | None = None):
    t = tanggal or hari_ini()
    return {"tanggal": t.isoformat(), "rows": kelola.daftar(t)}


@app.post("/api/data/hapus", dependencies=[Depends(admin_api)])
def api_data_hapus(b: HapusTiket):
    return {"ok": True, "terhapus": _kelola(kelola.hapus, b.ids)}


@app.post("/api/data/hapus-tanggal", dependencies=[Depends(admin_api)])
def api_data_hapus_tanggal(b: HapusTanggal):
    return {"ok": True, "terhapus": _kelola(kelola.hapus_tanggal, b.tanggal)}


@app.post("/api/data/{id_}/ubah", dependencies=[Depends(admin_api)])
def api_data_ubah(id_: int, b: UbahTiket):
    return {"ok": True, **_kelola(kelola.ubah, id_, b.model_dump(), pengaturan.get())}


@app.post("/api/pengaturan", dependencies=[Depends(admin_api)])
async def api_simpan_pengaturan(request: Request):
    form = await request.form()
    data, err = pengaturan.validasi(form)
    berkas = form.get("logo")
    isi = b""
    if berkas is not None and hasattr(berkas, "read"):
        isi = await berkas.read()
        if isi:
            e = pengaturan.simpan_logo(isi) if not err else None
            if e:
                err.append(e)
    if err:
        return JSONResponse({"ok": False, "errors": err}, status_code=422)
    pengaturan.simpan(data)
    return {"ok": True, "versi": pengaturan.get(paksa=True)["_versi"]}


@app.post("/api/pengaturan/logo/hapus", dependencies=[Depends(admin_api)])
def api_hapus_logo():
    pengaturan.hapus_logo()
    return {"ok": True}


@app.post("/api/pengaturan/tes-cetak", dependencies=[Depends(admin_api)])
async def api_tes_cetak(request: Request):
    form = await request.form()
    data, err = pengaturan.validasi(form)  # memakai isian form saat ini (belum perlu disimpan)
    perr = [e for e in err if "rinter" in e and "wajib" not in e]
    if perr:
        return JSONResponse({"ok": False, "pesan": "; ".join(perr)}, status_code=422)
    p = {**pengaturan.get(), **{k: data[k] for k in ("printer_host", "printer_footer")},
         "printer_port": int(data["printer_port"]), "printer_lebar": int(data["printer_lebar"])}
    e = printer.cetak(p, 1) if p["printer_host"] else "Isi alamat printer terlebih dahulu"
    return JSONResponse({"ok": e is None, "pesan": e or "Tes cetak terkirim ke printer"}, status_code=200 if e is None else 502)
