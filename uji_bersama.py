"""Pembantu uji: muat gambar wasit Pillow + bandingkan piksel.

Jalankan semua uji irisan dengan Python venv wasit:
../png-ref/venv/bin/python uji_irisanN.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "png-ref"))
from PIL import Image  # noqa: E402  (venv build 27)

REF = os.path.join(os.path.dirname(__file__), "..", "jpeg-ref")


def muat_wasit(nama):
    img = Image.open(os.path.join(REF, nama)).convert("RGB")
    return img.size[0], img.size[1], bytearray(img.tobytes())


def muat_mentah(nama):
    with open(os.path.join(REF, nama), "rb") as f:
        return f.read()


def banding(a, b):
    """Dua bytearray RGB -> (selisih maks, rerata, % dalam +-2)."""
    assert len(a) == len(b), "panjang piksel beda"
    maks = 0
    total = 0
    dalam = 0
    for x, y in zip(a, b):
        d = abs(x - y)
        if d > maks:
            maks = d
        total += d
        if d <= 2:
            dalam += 1
    n = len(a)
    return maks, total / n, 100.0 * dalam / n
