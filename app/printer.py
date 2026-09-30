"""Cetak nomor antrian ke printer thermal lewat jaringan (ESC/POS, raw TCP port 9100). Nonaktif secara bawaan."""
import socket
import textwrap

from .util import p3, sekarang, tanggal_id

ESC, GS = b"\x1b", b"\x1d"
INIT = ESC + b"@"
RATA = {"kiri": ESC + b"a\x00", "tengah": ESC + b"a\x01"}
TEBAL = {True: ESC + b"E\x01", False: ESC + b"E\x00"}
UKURAN = {1: GS + b"!\x00", 2: GS + b"!\x11", 4: GS + b"!\x33"}
POTONG = GS + b"V\x42\x00"


def _t(s: str) -> bytes:
    return s.encode("cp437", "replace")


def tiket_bytes(p: dict, nomor: int, waktu=None) -> bytes:
    w = int(p["printer_lebar"])
    waktu = waktu or sekarang()
    o = [INIT, RATA["tengah"], TEBAL[True], UKURAN[1]]
    for baris in textwrap.wrap(p["nama_instansi"], w) or [""]:
        o.append(_t(baris + "\n"))
    o.append(TEBAL[False])
    for baris in textwrap.wrap(p["alamat"], w) if p["alamat"] else []:
        o.append(_t(baris + "\n"))
    o += [_t("=" * w + "\n"), _t("NOMOR ANTRIAN ANDA\n\n"), TEBAL[True], UKURAN[4],
          _t(p3(nomor) + "\n"), UKURAN[1], TEBAL[False], _t("\n"),
          _t("Silahkan menunggu hingga\nnomor Anda dipanggil\n"), _t("-" * w + "\n"),
          _t(tanggal_id(waktu, True) + "\n")]
    if p["printer_footer"]:
        o.append(TEBAL[True])
        for baris in textwrap.wrap(p["printer_footer"], w):
            o.append(_t(baris + "\n"))
        o.append(TEBAL[False])
    o += [_t("\n\n\n\n"), POTONG]
    return b"".join(o)


def kirim(host: str, port: int, data: bytes, timeout: float = 4.0):
    with socket.create_connection((host, int(port)), timeout=timeout) as s:
        s.sendall(data)


def cetak(p: dict, nomor: int) -> str | None:
    """None = sukses; selain itu pesan kesalahan (tidak pernah melempar exception)."""
    if not p["printer_host"]:
        return "Alamat printer belum diisi"
    try:
        kirim(p["printer_host"], p["printer_port"], tiket_bytes(p, nomor))
    except OSError as e:
        return f"Gagal mengirim ke printer: {e}"
    return None
