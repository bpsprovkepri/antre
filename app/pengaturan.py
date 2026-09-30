"""Pengaturan aplikasi (disimpan di tabel queue_pengaturan) + logo (queue_logo)."""
import json
import re
import time
from urllib.parse import parse_qs, urlparse

import psycopg

from . import config
from .db import pool, q

DEFAULT = {
    "nama_instansi": config.NAMA_DEFAULT,
    "alamat": "",
    "telpon": "",
    "email": "",
    "running_text": "SELAMAT DATANG",
    "youtube_id": "",
    "judul_monitor": "Monitor Antrian Pendaftaran",
    "footer_text": "© {tahun} {instansi}",
    "warna_primary": "#0a6b38",
    "warna_secondary": "#e11d48",
    "warna_accent": "#f59e0b",
    "warna_background": "#15191f",
    "warna_text": "#ffffff",
    "suara_loket": "1",
    "suara_monitor": "1",
    "suara_engine": "auto",
    "printer_aktif": "0",
    "printer_host": "",
    "printer_port": "9100",
    "printer_lebar": "48",
    "printer_footer": "TERIMA KASIH, ANDA TELAH TERTIB",
}
BOOL = ("suara_loket", "suara_monitor", "printer_aktif")
WARNA = ("warna_primary", "warna_secondary", "warna_accent", "warna_background", "warna_text")
BATAS = {"nama_instansi": 120, "alamat": 250, "telpon": 40, "email": 100, "running_text": 300,
         "judul_monitor": 80, "footer_text": 200, "printer_footer": 100, "youtube_id": 300}

_cache = {"t": 0.0, "v": None}


# ---------- meja ----------
def _norm_meja(data):
    hasil, dipakai = [], set()
    if not isinstance(data, list):
        return []
    for m in data:
        try:
            no = int(m.get("no"))
        except (TypeError, ValueError, AttributeError):
            continue
        if not 1 <= no <= 99 or no in dipakai:
            continue
        dipakai.add(no)
        hasil.append({"no": no, "nama": (str(m.get("nama") or "").strip()[:30] or f"Meja {no}")})
    return sorted(hasil, key=lambda x: x["no"])


def _meja_default():
    return [{"no": i, "nama": f"Meja {i}"} for i in range(1, max(1, config.JUMLAH_MEJA) + 1)]


# ---------- baca ----------
def get(paksa=False) -> dict:
    now = time.monotonic()
    if not paksa and _cache["v"] is not None and now - _cache["t"] < 3:
        return _cache["v"]
    rows = q("SELECT kunci, nilai, extract(epoch FROM diubah_at)::float8 AS e FROM queue_pengaturan")
    raw = {r["kunci"]: r["nilai"] for r in rows}
    p = {k: raw.get(k, v) for k, v in DEFAULT.items()}
    for k in BOOL:
        p[k] = p[k] == "1"
    for k, lo, hi, dflt in (("printer_port", 1, 65535, 9100), ("printer_lebar", 20, 80, 48)):
        try:
            p[k] = min(hi, max(lo, int(p[k])))
        except ValueError:
            p[k] = dflt
    try:
        meja = _norm_meja(json.loads(raw.get("meja", "[]")))
    except ValueError:
        meja = []
    p["meja"] = meja or _meja_default()
    logo = q("SELECT extract(epoch FROM diubah_at)::float8 AS e FROM queue_logo WHERE id=1", one=True)
    e = max([r["e"] for r in rows] + [0])
    p["punya_logo"] = bool(logo)
    p["_versi"] = f"{int(e * 1000)}-{int(logo['e'] * 1000) if logo else 0}"
    _cache.update(t=now, v=p)
    return p


def nama_meja(p, no):
    for m in p["meja"]:
        if m["no"] == no:
            return m["nama"]
    return None


# ---------- tampilan ----------
def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    return "#%02x%02x%02x" % tuple(round(x * (1 - t) + y * t) for x, y in zip(_rgb(a), _rgb(b)))


def _terang(h):
    r, g, b = _rgb(h)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def tema(p) -> dict:
    pr = p["warna_primary"]
    return {
        "brand": pr, "brand_dark": _mix(pr, "#000000", 0.28), "brand_light": _mix(pr, "#ffffff", 0.35),
        "brand_soft": _mix(pr, "#ffffff", 0.90), "brand_soft2": _mix(pr, "#ffffff", 0.80),
        "on_brand": "#111111" if _terang(pr) > 0.68 else "#ffffff",
        "bg": p["warna_background"], "teks": p["warna_text"],
        "sekunder": p["warna_secondary"], "aksen": p["warna_accent"],
        "bg_naik": _mix(p["warna_background"], "#ffffff", 0.07),
    }


def footer_teks(p) -> str:
    from .util import sekarang
    return p["footer_text"].replace("{tahun}", str(sekarang().year)).replace("{instansi}", p["nama_instansi"])


# ---------- YouTube ----------
_RE_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
_RE_LIST = re.compile(r"^[A-Za-z0-9_-]{10,64}$")


def youtube_embed(teks: str) -> str:
    """Terima ID, ID+parameter (format lama), atau URL YouTube -> URL embed (diam/mute, berulang)."""
    teks = (teks or "").strip()
    if not teks:
        return ""
    vid, lst = "", ""
    if teks.lower().startswith(("http://", "https://")):
        u = urlparse(teks)
        qs = parse_qs(u.query)
        host = (u.hostname or "").lower()
        if host == "youtu.be":
            vid = u.path.strip("/").split("/")[0]
        elif host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
            parts = [x for x in u.path.split("/") if x]
            vid = qs.get("v", [""])[0] or (parts[1] if len(parts) > 1 and parts[0] in ("embed", "shorts", "live") else "")
        else:
            return ""
        lst = qs.get("list", [""])[0]
    else:
        awal, _, sisa = teks.partition("?")
        vid = awal.strip()
        lst = parse_qs(sisa).get("list", [""])[0]
        if not sisa and vid.startswith(("PL", "UU", "OL", "FL")) and len(vid) >= 16:
            vid, lst = "", vid
    if vid and not _RE_ID.match(vid):
        return ""
    if lst and not _RE_LIST.match(lst):
        lst = ""
    if not vid and not lst:
        return ""
    dasar = "autoplay=1&mute=1&loop=1&rel=0&playsinline=1&modestbranding=1&controls=0"
    if lst:
        return f"https://www.youtube-nocookie.com/embed/{vid or 'videoseries'}?list={lst}&{dasar}"
    return f"https://www.youtube-nocookie.com/embed/{vid}?playlist={vid}&{dasar}"


# ---------- tulis ----------
def validasi(form) -> tuple[dict, list]:
    """form: objek dengan .get() dan .getlist() (starlette FormData)."""
    data, err = {}, []
    for k, maks in BATAS.items():
        v = str(form.get(k, DEFAULT[k]) or "").strip()
        if len(v) > maks:
            err.append(f"{k.replace('_', ' ').capitalize()} maksimal {maks} karakter")
        data[k] = v[:maks]
    if not data["nama_instansi"]:
        err.append("Nama instansi wajib diisi")
    if data["youtube_id"] and not youtube_embed(data["youtube_id"]):
        err.append("YouTube ID/URL tidak valid")
    for k in WARNA:
        v = str(form.get(k, DEFAULT[k]) or "").strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            err.append(f"Format {k.replace('_', ' ')} tidak valid")
            v = DEFAULT[k]
        data[k] = v.lower()
    for k in BOOL:
        data[k] = "1" if form.get(k) in ("1", "on", "true") else "0"
    eng = form.get("suara_engine", "auto")
    data["suara_engine"] = eng if eng in ("auto", "browser", "server") else "auto"
    host = str(form.get("printer_host", "") or "").strip()
    if host and not re.fullmatch(r"[A-Za-z0-9._-]{1,253}", host):
        err.append("Alamat printer tidak valid")
    data["printer_host"] = host
    if data["printer_aktif"] == "1" and not host:
        err.append("Alamat printer wajib diisi jika printer diaktifkan")
    try:
        port = int(form.get("printer_port", 9100))
        if not 1 <= port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        err.append("Port printer harus 1-65535")
        port = 9100
    data["printer_port"] = str(port)
    lebar = str(form.get("printer_lebar", "48"))
    data["printer_lebar"] = lebar if lebar in ("32", "42", "48") else "48"
    meja, dipakai = [], set()
    for no, nama in zip(form.getlist("meja_no"), form.getlist("meja_nama")):
        try:
            n = int(no)
        except (TypeError, ValueError):
            err.append("Nomor meja harus angka")
            continue
        if not 1 <= n <= 99:
            err.append("Nomor meja harus 1-99")
        elif n in dipakai:
            err.append(f"Nomor meja {n} dobel")
        else:
            dipakai.add(n)
            meja.append({"no": n, "nama": (str(nama).strip()[:30] or f"Meja {n}")})
    if not meja:
        err.append("Minimal harus ada satu meja")
    data["meja"] = json.dumps(sorted(meja, key=lambda x: x["no"]), ensure_ascii=False)
    return data, err


def simpan(data: dict):
    """Simpan hanya nilai yang berubah (agar layar monitor tidak reload tanpa perlu)."""
    lama = {r["kunci"]: r["nilai"] for r in q("SELECT kunci, nilai FROM queue_pengaturan")}
    with pool.connection() as c:
        for k, v in data.items():
            if lama.get(k) != v:
                c.execute(
                    "INSERT INTO queue_pengaturan(kunci, nilai, diubah_at) VALUES (%s, %s, now()) "
                    "ON CONFLICT (kunci) DO UPDATE SET nilai=EXCLUDED.nilai, diubah_at=now()", (k, v))
    _cache["v"] = None


def _seed_dari_tabel_lama() -> dict:
    """Ambil pengaturan dari tabel lama queue_setting (hanya dibaca, tidak diubah)."""
    try:
        r = q("SELECT * FROM queue_setting ORDER BY 1 DESC LIMIT 1", one=True)
    except psycopg.Error:
        return {}
    if not r:
        return {}
    d = {}
    for k_baru, k_lama in (("nama_instansi", "nama_instansi"), ("alamat", "alamat"), ("telpon", "telpon"),
                           ("email", "email"), ("running_text", "running_text"), ("youtube_id", "youtube_id"),
                           ("warna_primary", "warna_primary"), ("warna_secondary", "warna_secondary"),
                           ("warna_accent", "warna_accent"), ("warna_background", "warna_background"),
                           ("warna_text", "warna_text")):
        v = r.get(k_lama)
        if v not in (None, ""):
            v = str(v).strip()
            if k_baru in WARNA and not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                continue
            d[k_baru] = v
    raw = r.get("list_loket")
    if raw:
        for kandidat in (raw, str(raw).replace('\\"', '"')):
            try:
                lst = json.loads(kandidat)
                meja = _norm_meja([{"no": m.get("no_loket"), "nama": m.get("nama_loket")} for m in lst])
                if meja:
                    d["meja"] = json.dumps(meja, ensure_ascii=False)
                break
            except (ValueError, AttributeError, TypeError):
                continue
    return d


def seed():
    """Isi awal saat tabel pengaturan masih kosong: dari tabel lama bila ada, jika tidak dari default."""
    if q("SELECT 1 FROM queue_pengaturan LIMIT 1", one=True):
        return
    awal = {k: v for k, v in DEFAULT.items()}
    awal["meja"] = json.dumps(_meja_default(), ensure_ascii=False)
    awal.update(_seed_dari_tabel_lama())
    simpan(awal)


# ---------- logo ----------
def _tipe_gambar(b: bytes):
    if b.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if b.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if b[:4] == b"GIF8":
        return "image/gif"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    return None


def simpan_logo(b: bytes) -> str | None:
    """Kembalikan pesan error, atau None jika sukses."""
    if len(b) > 2 * 1024 * 1024:
        return "Ukuran logo maksimal 2 MB"
    tipe = _tipe_gambar(b)
    if not tipe:
        return "Logo harus berformat PNG, JPG, GIF, atau WEBP"
    q("INSERT INTO queue_logo(id, tipe, data, diubah_at) VALUES (1, %s, %s, now()) "
      "ON CONFLICT (id) DO UPDATE SET tipe=EXCLUDED.tipe, data=EXCLUDED.data, diubah_at=now()", (tipe, b))
    _cache["v"] = None
    return None


def hapus_logo():
    q("DELETE FROM queue_logo WHERE id=1")
    _cache["v"] = None


def ambil_logo():
    return q("SELECT tipe, data FROM queue_logo WHERE id=1", one=True)
