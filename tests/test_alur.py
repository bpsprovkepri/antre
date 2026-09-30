import os, sys, time, pgserver
srv = pgserver.get_server("/tmp/pgdata-test", cleanup_mode="delete")
os.environ.update(DATABASE_URL=srv.get_uri(), ADMIN_PASSWORD="rahasia-test", JUMLAH_MEJA="2")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from app.main import app
A = ("admin", "rahasia-test")
with TestClient(app) as c:
    for p in ["/", "/kiosk", "/monitor"]:
        assert c.get(p).status_code == 200, p
    assert c.get("/loket/1").status_code == 401 and c.get("/laporan").status_code == 401
    assert c.get("/loket/9", auth=A).status_code == 404
    nums = [c.post("/api/tiket").json()["nomor"] for _ in range(3)]
    assert nums == [1, 2, 3], nums
    st = lambda m: c.get(f"/api/loket/{m}", auth=A).json()
    do = lambda m, i, a: c.post(f"/api/loket/{m}/{i}/{a}", auth=A).status_code
    ids = {r["nomor"]: r["id"] for r in st(1)["rows"]}
    rows = {r["nomor"]: r for r in st(1)["rows"]}
    assert rows["001"]["bisa_panggil"] and not rows["002"]["bisa_panggil"]
    assert do(1, ids["002"], "panggil") == 409   # lompat nomor
    assert do(1, ids["001"], "mulai") == 409     # mulai sebelum panggil
    assert do(1, ids["001"], "panggil") == 200
    assert do(1, ids["002"], "panggil") == 409   # meja 1 masih pegang 001
    assert do(1, ids["001"], "selesai") == 409   # selesai sebelum mulai
    r = {x["nomor"]: x for x in st(1)["rows"]}
    assert r["001"]["bisa_mulai"] and not r["002"]["bisa_panggil"]
    assert do(2, ids["001"], "mulai") == 409     # meja lain tak bisa ambil alih
    assert do(1, ids["001"], "mulai") == 200
    time.sleep(1.2)
    assert do(1, ids["001"], "selesai") == 200
    assert st(1)["rows"][-1]["bisa_panggil"] is False and st(1)["rows"][-1]["selesai"] != "-"
    assert {x["nomor"]: x for x in st(1)["rows"]}["002"]["bisa_panggil"]
    assert do(2, ids["002"], "panggil") == 200   # meja 2 ambil 002
    assert do(2, ids["002"], "lewati") == 200    # tidak hadir
    assert do(2, ids["003"], "panggil") == 200 and do(2, ids["003"], "panggil") == 200  # ulang
    m = c.get("/api/monitor").json()
    print("monitor:", m)
    assert m["last"]["nomor"] == 3 and m["last"]["panggil_n"] == 2 and m["sisa"] == 0
    lap = c.get("/laporan", auth=A); assert lap.status_code == 200 and "001" in lap.text
    x = c.get("/laporan.xlsx", auth=A); assert x.status_code == 200 and x.content[:2] == b"PK"
    # kondisi balapan: 20 tiket paralel harus unik
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(10) as ex:
        res = list(ex.map(lambda _: c.post("/api/tiket").json()["nomor"], range(20)))
    assert len(set(res)) == 20, res
    print("SEMUA UJI LULUS")
