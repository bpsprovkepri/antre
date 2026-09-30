import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def klien():
    import pgserver
    from psycopg.conninfo import conninfo_to_dict

    srv = pgserver.get_server("/tmp/pgdata-antrian-test", cleanup_mode="delete")
    # meniru database yang sudah berisi tabel lama aplikasi sebelumnya (tidak boleh terganggu)
    srv.psql("""
      CREATE TABLE queue_antrian_admisi(id bigserial primary key, tanggal date, no_antrian varchar(3), status text default '0', updated_date timestamp);
      INSERT INTO queue_antrian_admisi(tanggal, no_antrian, status) VALUES ('2026-01-01','001','1');
      CREATE TABLE queue_setting(id serial primary key, nama_instansi text, alamat text, telpon text, email text, running_text text,
        youtube_id text, list_loket text, warna_primary text, warna_secondary text, warna_accent text, warna_background text, warna_text text);
      INSERT INTO queue_setting(nama_instansi, alamat, telpon, email, running_text, youtube_id, list_loket, warna_primary, warna_secondary, warna_accent, warna_background, warna_text)
        VALUES ('Pelayanan Statistik Terpadu BPS Provinsi Kepulauan Riau','Jl. Ahmad Yani No. 21','07714500155','bps2100@bps.go.id','SELAMAT DATANG DI PST',
        'tgdk7wCVLpg?autoplay=1&showinfo=0&loop=1&list=PL88EA9KKUmj1I6LRpec2LlxRw4b7K3DA9&rel=0',
        '[{"no_loket":"1","nama_loket":"Meja 1"},{"no_loket":"2","nama_loket":"Meja 2"}]','#0a6b38','#e11010','#ff00e6','#212529','#ffffff');
    """)
    d = conninfo_to_dict(srv.get_uri())
    os.environ.update(DB_HOST=d["host"], DB_PORT=str(d.get("port", "5432")), DB_NAME=d["dbname"], DB_USER=d["user"],
                      DB_PASS=d.get("password", ""), ADMIN_PASSWORD="rahasia-test", ADMIN_USER="admin", COOKIE_SECURE="0")
    os.environ.pop("DATABASE_URL", None)
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        c.srv = srv
        yield c


@pytest.fixture()
def admin(klien):
    r = klien.post("/login", data={"username": "admin", "password": "rahasia-test", "next": "/"}, follow_redirects=False)
    assert r.status_code == 303
    return klien
