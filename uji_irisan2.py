"""Irisan 2 — dekode penuh abu-abu & 4:4:4, toleransi ketat.

Tanpa subsampling, satu-satunya sumber selisih yang sah adalah
IDCT float-ku vs IDCT integer libjpeg: selisih harus kecil.
"""
import sys

sys.path.insert(0, ".")

from jpegku import dekode
from uji_bersama import banding, muat_mentah, muat_wasit

lulus = 0


def cek(kondisi, pesan):
    global lulus
    assert kondisi, pesan
    lulus += 1


for nama in ("abu.jpg", "warna444.jpg"):
    w0, h0, wasit = muat_wasit(nama)
    w, h, rgb = dekode(muat_mentah(nama))
    cek((w, h) == (w0, h0), f"{nama}: dimensi cocok")
    maks, rerata, persen = banding(rgb, wasit)
    print(f"  {nama}: maks={maks} rerata={rerata:.3f} "
          f"dalam+-2={persen:.2f}%")
    cek(maks <= 4, f"{nama}: selisih maks {maks} <= 4")
    cek(rerata <= 0.6, f"{nama}: rerata {rerata:.3f} <= 0.6")
    cek(persen >= 99.5, f"{nama}: {persen:.2f}% piksel dalam +-2")

print(f"irisan 2: {lulus} cek lulus")
