"""Suara panggilan dari server (cadangan bila browser tidak punya suara Indonesia). Memakai espeak-ng."""
import shutil
import subprocess
import threading
from collections import OrderedDict

_kunci = threading.Lock()
_cache: "OrderedDict[str, bytes]" = OrderedDict()


def tersedia() -> bool:
    return shutil.which("espeak-ng") is not None


def sintesis(teks: str) -> bytes:
    with _kunci:
        if teks in _cache:
            _cache.move_to_end(teks)
            return _cache[teks]
    wav = subprocess.run(
        ["espeak-ng", "-v", "id", "-s", "135", "-p", "55", "-a", "190", "--stdout", teks],
        capture_output=True, timeout=15, check=True,
    ).stdout
    with _kunci:
        _cache[teks] = wav
        while len(_cache) > 100:
            _cache.popitem(last=False)
    return wav
