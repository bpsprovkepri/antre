"""Uji terhadap PostgreSQL sungguhan (pgserver). Jalankan: pytest -q"""
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from types import SimpleNamespace

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82")


@pytest.fixture()
def mod(klien):
    """Impor modul aplikasi setelah lingkungan database uji siap."""
    from app import main, pengaturan, suara, util
    return SimpleNamespace(main=main, pengaturan=pengaturan, suara=suara, util=util)


def bersih(k):
    k.srv.psql("DELETE FROM queue_tiket")


# ---------- fungsi murni ----------
def test_terbilang(mod):
    util = mod.util
    assert [util.terbilang(n) for n in (0, 2, 10, 11, 12, 19, 20, 21, 100, 101, 115, 200, 999, 1000, 2025)] == [
        "nol", "dua", "sepuluh", "sebelas", "dua belas", "sembilan belas", "dua puluh", "dua puluh satu", "seratus",
        "seratus satu", "seratus lima belas", "dua ratus", "sembilan ratus sembilan puluh sembilan", "seribu",
        "dua ribu dua puluh lima"]
    assert util.teks_panggil(12, "Meja 2") == "Nomor antrian, dua belas, silakan menuju, Meja dua"


def test_youtube_embed(mod):
    y = mod.pengaturan.youtube_embed
    lama = y("tgdk7wCVLpg?autoplay=1&showinfo=0&loop=1&list=PL88EA9KKUmj1I6LRpec2LlxRw4b7K3DA9&rel=0")
    assert lama.startswith("https://www.youtube-nocookie.com/embed/tgdk7wCVLpg?list=PL88EA9KKUmj1I6LRpec2LlxRw4b7K3DA9&")
    assert "mute=1" in lama and "autoplay=1" in lama and "loop=1" in lama
    assert "playlist=dQw4w9WgXcQ" in y("dQw4w9WgXcQ")
    assert "embed/dQw4w9WgXcQ" in y("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=5")
    assert "embed/dQw4w9WgXcQ" in y("https://youtu.be/dQw4w9WgXcQ")
    assert "videoseries?list=PL88EA9KKUmj1I6LRpec2LlxRw4b7K3DA9" in y("PL88EA9KKUmj1I6LRpec2LlxRw4b7K3DA9")
    for buruk in ("", "https://evil.example/x", "javascript:alert(1)", "abc def", '"><script>'):
        assert y(buruk) == ""


# ---------- awal ----------
def test_seed_dari_tabel_lama_dan_tabel_lama_utuh(klien, mod):
    pengaturan = mod.pengaturan
    p = pengaturan.get(paksa=True)
    assert p["nama_instansi"] == "Pelayanan Statistik Terpadu BPS Provinsi Kepulauan Riau"
    assert p["alamat"].startswith("Jl. Ahmad Yani") and p["telpon"] == "07714500155"
    assert [m["no"] for m in p["meja"]] == [1, 2] and p["meja"][1]["nama"] == "Meja 2"
    assert p["warna_accent"] == "#ff00e6" and p["warna_background"] == "#212529"
    assert pengaturan.youtube_embed(p["youtube_id"]).startswith("https://www.youtube-nocookie.com/embed/tgdk7wCVLpg")
    assert "queue_tiket" in klien.srv.psql("select tablename from pg_tables where schemaname='public'")
    assert klien.srv.psql("select count(*) from queue_antrian_admisi").split()[2] == "1"   # tabel lama tidak disentuh
    assert klien.get("/healthz").json() == {"status": "ok"}


def test_halaman_publik(klien):
    r = klien.get("/")
    assert r.status_code == 200
    for teks in ("Nomor Antrian", "Panggilan Antrian", "Monitor Antrian", "Setting Antrian", "Laporan Layanan", "Meja 2"):
        assert teks in r.text
    k = klien.get("/kiosk")
    assert k.status_code == 200 and "Ambil Nomor" in k.text and 'href="/"' in k.text     # ada navigasi ke home
    badan = k.text.split("<script>")[0]                                         # bagian yang terlihat pengunjung
    assert "bi-printer" not in badan and "Cetak" not in badan and "print(" not in badan  # tombol cetak disembunyikan
    m = klien.get("/monitor")
    assert m.status_code == 200
    for teks in ("Nomor Antrian Sekarang", "Antrian Selanjutnya", "Sisa Antrian", "youtube-nocookie.com/embed/tgdk7wCVLpg", "SELAMAT DATANG DI PST", 'href="/"'):
        assert teks in m.text
    assert "Total Antrian" not in m.text
    assert klien.get("/static/vendor/bootstrap/bootstrap.min.css").status_code == 200
    assert klien.get("/logo").headers["content-type"].startswith("image/svg")


# ---------- login ----------
def test_login_sesi(klien):
    klien.cookies.clear()
    r = klien.get("/loket/1", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login?next=/loket/1")
    assert klien.get("/pengaturan", follow_redirects=False).status_code == 303
    assert klien.get("/laporan", follow_redirects=False).status_code == 303
    assert klien.get("/api/loket/1").status_code == 401
    assert klien.post("/api/pengaturan", data={}).status_code == 401
    bad = klien.post("/login", data={"username": "admin", "password": "salah", "next": "/"})
    assert bad.status_code == 401 and "salah" in bad.text
    ok = klien.post("/login", data={"username": "admin", "password": "rahasia-test", "next": "//evil.com"}, follow_redirects=False)
    assert ok.status_code == 303 and ok.headers["location"] == "/"          # tidak bisa dialihkan ke situs lain
    assert klien.get("/pengaturan").status_code == 200
    assert klien.post("/logout", follow_redirects=False).status_code == 303
    assert klien.get("/pengaturan", follow_redirects=False).status_code == 303


def test_batas_percobaan_login(klien, mod):
    klien.cookies.clear()
    kode = [klien.post("/login", data={"username": "admin", "password": "x%d" % i, "next": "/"}).status_code for i in range(7)]
    assert 429 in kode
    mod.main._gagal.clear()


# ---------- alur antrian ----------
def test_alur_panggil_mulai_selesai(admin):
    k = admin
    bersih(k)
    nomor = [k.post("/api/tiket").json()["nomor"] for _ in range(3)]
    assert nomor == [1, 2, 3]
    s = k.get("/api/loket/1").json()
    rows = {r["nomor"]: r for r in s["rows"]}
    assert s["jumlah"] == 3 and s["sisa"] == 3 and s["selanjutnya"] == "001"
    assert rows["001"]["bisa_panggil"] and not rows["002"]["bisa_panggil"] and not rows["003"]["bisa_panggil"]
    ids = {n: r["id"] for n, r in rows.items()}
    do = lambda m, n, a: k.post(f"/api/loket/{m}/{ids[n]}/{a}")
    assert do(1, "002", "panggil").status_code == 409            # tidak boleh melompat nomor
    assert do(1, "001", "selesai").status_code == 409            # belum dipanggil
    assert do(1, "001", "mulai").status_code == 404              # aksi 'mulai' sudah digabung ke 'panggil'
    r = do(1, "001", "panggil"); assert r.status_code == 200
    j = r.json(); assert j["teks"] == "Nomor antrian, satu, silakan menuju, Meja satu" and j["n"] == 1
    row = k.srv.psql("select dipanggil_at is not null, mulai_at is not null, dipanggil_at = mulai_at from queue_tiket where nomor=1")
    assert "t|t|t" in "".join(row.split())                                   # satu klik = panggil DAN mulai layanan
    s = k.get("/api/loket/1").json(); rows = {r["nomor"]: r for r in s["rows"]}
    assert s["saya"] == "001" and rows["001"]["status"] == "aktif" and rows["001"]["bisa_selesai"] and rows["001"]["bisa_ulang"]
    assert not rows["002"]["bisa_panggil"]                        # 002 nonaktif selama 001 belum selesai
    assert s["rows"][0]["nomor"] == "001"                         # yang aktif tampil paling atas
    assert do(1, "002", "panggil").status_code == 409
    assert do(1, "001", "panggil").json()["n"] == 2               # panggil ulang tidak mengubah waktu mulai
    assert do(2, "001", "selesai").status_code == 409             # meja lain tidak bisa mengambil alih
    assert do(2, "002", "panggil").status_code == 200             # meja 2 bebas -> ambil 002
    time.sleep(1.1)
    assert do(1, "001", "selesai").status_code == 200
    assert do(1, "001", "selesai").status_code == 409
    s = k.get("/api/loket/1").json(); rows = {r["nomor"]: r for r in s["rows"]}
    assert rows["001"]["status"] == "selesai" and rows["001"]["durasi"] >= "00:01"
    assert rows["003"]["bisa_panggil"]                            # kini 003 boleh dipanggil meja 1
    assert do(1, "003", "panggil").status_code == 200
    assert do(1, "003", "lewati").status_code == 200              # tidak hadir
    s = k.get("/api/loket/1").json(); rows = {r["nomor"]: r for r in s["rows"]}
    assert rows["003"]["status"] == "lewat"
    assert k.post("/api/loket/9/1/panggil").status_code == 404
    assert k.post(f"/api/loket/1/{ids['001']}/hapus").status_code == 404


def test_monitor_api(klien):
    d = klien.get("/api/monitor").json()          # public, tanpa login
    assert d["last"]["nomor_txt"] == "003" and d["last"]["meja_nama"] == "Meja 1"
    assert d["last"]["teks"] == "Nomor antrian, tiga, silakan menuju, Meja satu"
    assert d["sisa"] == 0 and d["selanjutnya"] == "-"
    assert [a["nomor"] for a in d["aktif"]] == ["002"]      # 002 masih berjalan di Meja 2
    assert d["suara"] == {"aktif": True, "engine": "auto"} and d["versi"]


def test_laporan(admin):
    k = admin
    r = k.get("/laporan")
    assert r.status_code == 200
    for teks in ("Rata-rata lama layanan", "Layanan terlama", "Ringkasan per meja", "Antrian per jam", "Unduh Excel", 'href="/"', "Tidak hadir"):
        assert teks in r.text
    x = k.get("/laporan.xlsx")
    assert x.status_code == 200 and x.content[:2] == b"PK" and "spreadsheetml" in x.headers["content-type"]
    from openpyxl import load_workbook
    import io
    wb = load_workbook(io.BytesIO(x.content))
    assert wb.sheetnames == ["Detail", "Ringkasan"] and wb["Detail"].max_row == 4
    assert k.get("/laporan?tanggal=2020-01-01").status_code == 200
    assert k.get("/laporan?tanggal=bukan-tanggal").status_code == 422


def test_nomor_unik_paralel(klien):
    bersih(klien)
    with ThreadPoolExecutor(10) as ex:
        hasil = list(ex.map(lambda _: klien.post("/api/tiket").json()["nomor"], range(25)))
    assert sorted(hasil) == list(range(1, 26))


# ---------- pengaturan ----------
def form(admin_klien, **ubah):
    from app import pengaturan
    p = pengaturan.get(paksa=True)
    d = {"nama_instansi": p["nama_instansi"], "alamat": p["alamat"], "telpon": p["telpon"], "email": p["email"],
         "running_text": p["running_text"], "youtube_id": p["youtube_id"], "judul_monitor": p["judul_monitor"],
         "footer_text": p["footer_text"], "warna_primary": p["warna_primary"], "warna_secondary": p["warna_secondary"],
         "warna_accent": p["warna_accent"], "warna_background": p["warna_background"], "warna_text": p["warna_text"],
         "suara_loket": "1", "suara_monitor": "1", "suara_engine": "auto", "printer_host": "", "printer_port": "9100",
         "printer_lebar": "48", "printer_footer": "TERIMA KASIH",
         "meja_no": [str(m["no"]) for m in p["meja"]], "meja_nama": [m["nama"] for m in p["meja"]]}
    d.update(ubah)
    return d


def test_halaman_pengaturan(admin):
    r = admin.get("/pengaturan")
    assert r.status_code == 200
    for teks in ("Informasi Instansi", "Daftar Meja", "Styling Monitor", "Suara Panggilan", "Printer Nomor Antrian", "Footer", "Logout", "Simpan", 'href="/"'):
        assert teks in r.text
    assert admin.get("/loket/1").status_code == 200 and "Panggil &amp; Mulai" in admin.get("/loket/1").text
    assert admin.get("/loket/9").status_code == 404


def test_simpan_footer_kustom_dan_escape(admin, mod):
    util = mod.util
    footer = "Made with ❤️ Tim Teknologi Informasi BPS Provinsi Kepulauan Riau"
    versi0 = admin.get("/api/monitor").json()["versi"]
    r = admin.post("/api/pengaturan", data=form(admin, footer_text=footer, judul_monitor="Monitor <b>PST</b>"))
    assert r.status_code == 200 and r.json()["ok"]
    home = admin.get("/").text
    assert footer in home                                          # footer beranda bisa diubah dari pengaturan
    assert footer in admin.get("/monitor").text
    assert "Monitor &lt;b&gt;PST&lt;/b&gt;" in admin.get("/monitor").text      # HTML dari pengaturan di-escape
    assert admin.get("/api/monitor").json()["versi"] != versi0                 # layar monitor akan memuat ulang
    admin.post("/api/pengaturan", data=form(admin, footer_text="© {tahun} {instansi} <script>x</script>"))
    home = admin.get("/").text
    assert "<script>x</script>" not in home and "&lt;script&gt;x&lt;/script&gt;" in home and str(util.sekarang().year) in home


def test_validasi_pengaturan(admin, mod):
    pengaturan = mod.pengaturan
    def salah(**u):
        r = admin.post("/api/pengaturan", data=form(admin, **u))
        assert r.status_code == 422 and r.json()["errors"], u
        return " ".join(r.json()["errors"])
    assert "warna" in salah(warna_primary="merah")
    assert "YouTube" in salah(youtube_id="https://evil.example/x")
    assert "Nama instansi" in salah(nama_instansi=" ")
    assert "Minimal" in salah(meja_no=[], meja_nama=[])
    assert "dobel" in salah(meja_no=["1", "1"], meja_nama=["a", "b"])
    assert "Port" in salah(printer_port="99999")
    assert "Alamat printer" in salah(printer_aktif="1", printer_host="")
    assert "Alamat printer" in salah(printer_host="a b;rm -rf")
    assert pengaturan.get(paksa=True)["warna_primary"] == "#0a6b38"   # penolakan tidak menyimpan apa pun


def test_meja_dinamis(admin):
    r = admin.post("/api/pengaturan", data=form(admin, meja_no=["1", "2", "3"], meja_nama=["Meja 1", "Meja 2", "Loket VIP 3"]))
    assert r.status_code == 200
    assert "Loket VIP 3" in admin.get("/").text and admin.get("/loket/3").status_code == 200
    admin.post("/api/pengaturan", data=form(admin, meja_no=["1", "2"], meja_nama=["Meja 1", "Meja 2"]))
    assert admin.get("/loket/3").status_code == 404


def test_logo(admin):
    files = lambda b: {"logo": ("logo.png", b, "image/png")}
    r = admin.post("/api/pengaturan", data=form(admin), files=files(b"bukan gambar"))
    assert r.status_code == 422 and "Logo harus" in r.json()["errors"][0]
    r = admin.post("/api/pengaturan", data=form(admin), files=files(b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024)))
    assert r.status_code == 422 and "2 MB" in r.json()["errors"][0]
    assert admin.post("/api/pengaturan", data=form(admin), files=files(PNG)).status_code == 200
    g = admin.get("/logo")
    assert g.headers["content-type"] == "image/png" and g.content == PNG
    assert "/logo?v=" in admin.get("/monitor").text
    assert admin.post("/api/pengaturan/logo/hapus").status_code == 200
    assert admin.get("/logo").headers["content-type"].startswith("image/svg")


# ---------- printer ----------
class PrinterPalsu:
    def __init__(self):
        self.s = socket.socket(); self.s.bind(("127.0.0.1", 0)); self.s.listen(5)
        self.port = self.s.getsockname()[1]; self.data = []
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            buf = b""
            while (x := c.recv(4096)):
                buf += x
            c.close(); self.data.append(buf)


def test_printer_nonaktif_bawaan_dan_cetak_saat_aktif(admin, mod):
    pengaturan = mod.pengaturan
    pr = PrinterPalsu()
    bersih(admin)
    t = admin.post("/api/tiket").json()
    assert t["cetak"] is False and pr.data == []                          # nonaktif: tidak ada yang dicetak

    r = admin.post("/api/pengaturan/tes-cetak", data=form(admin, printer_host="127.0.0.1", printer_port=str(pr.port)))
    assert r.status_code == 200 and r.json()["ok"]
    time.sleep(0.3); assert len(pr.data) == 1 and b"\x1d\x56" in pr.data[0]

    assert admin.post("/api/pengaturan", data=form(admin, printer_aktif="1", printer_host="127.0.0.1",
                                                    printer_port=str(pr.port), printer_footer="TERIMA KASIH")).status_code == 200
    t = admin.post("/api/tiket").json()
    assert t["cetak"] is True
    time.sleep(0.4)
    tiket = pr.data[-1]
    assert b"002" in tiket and b"NOMOR ANTRIAN ANDA" in tiket and b"TERIMA KASIH" in tiket and tiket.endswith(b"\x1d\x56\x42\x00")
    assert "Pelayanan Statistik Terpadu".encode() in tiket

    # printer mati -> nomor tetap terbit, tidak error
    admin.post("/api/pengaturan", data=form(admin, printer_aktif="1", printer_host="127.0.0.1", printer_port="1"))
    assert admin.post("/api/tiket").status_code == 200
    r = admin.post("/api/pengaturan/tes-cetak", data=form(admin, printer_host="127.0.0.1", printer_port="1"))
    assert r.status_code == 502 and "Gagal" in r.json()["pesan"]
    admin.post("/api/pengaturan", data=form(admin))                         # kembalikan: printer nonaktif
    assert pengaturan.get(paksa=True)["printer_aktif"] is False


# ---------- suara ----------
def test_suara_server(klien, mod):
    if not mod.suara.tersedia():
        pytest.skip("espeak-ng tidak terpasang")
    r = klien.get("/api/suara?nomor=12&meja=2")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content[:4] == b"RIFF" and len(r.content) > 5000
    assert klien.get("/api/suara?nomor=0&meja=1").status_code == 400
    assert klien.get("/api/suara?nomor=1&meja=abc").status_code == 422


def test_halaman_memuat_pemutar_suara(admin):
    assert "Suara.buka()" in admin.get("/loket/1").text and "Suara.panggil" in admin.get("/loket/1").text
    m = admin.get("/monitor").text
    assert "Aktifkan Suara" in m and "Suara.panggil" in m
    assert admin.get("/static/js/suara.js").status_code == 200


def test_sintaks_javascript(admin):
    """Semua skrip inline & berkas .js harus lolos pemeriksaan sintaks Node (dilewati bila node tidak ada)."""
    import re
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("node"):
        pytest.skip("node tidak terpasang")
    daftar = []
    for url in ("/", "/kiosk", "/monitor", "/loket/1", "/laporan", "/pengaturan"):
        for i, js in enumerate(re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", admin.get(url).text, re.S)):
            daftar.append((f"{url}#{i}", js))
    for f in ("app.js", "suara.js"):
        daftar.append((f, admin.get(f"/static/js/{f}").text))
    assert len(daftar) >= 7
    for nama, js in daftar:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as t:
            t.write(js)
        r = subprocess.run(["node", "--check", t.name], capture_output=True, text=True)
        assert r.returncode == 0, f"{nama}: {r.stderr}"
