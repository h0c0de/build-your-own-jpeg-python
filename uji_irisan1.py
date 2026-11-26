"""Irisan 1 — kerangka segmen & tabel melawan berkas Pillow."""
import sys

sys.path.insert(0, ".")

from jpegku import GalatJPEG, GambarJPEG
from uji_bersama import muat_mentah

lulus = 0


def cek(kondisi, pesan):
    global lulus
    assert kondisi, pesan
    lulus += 1


def cek_galat(fungsi, pesan):
    global lulus
    try:
        fungsi()
    except GalatJPEG:
        lulus += 1
        return
    raise AssertionError(f"tidak naik GalatJPEG: {pesan}")


# Tabel luminans baku Annex K (raster) + penskalaan kualitas libjpeg
DASAR_LUM = [
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99,
]


def skala_kualitas(dasar, q):
    skala = 5000 // q if q < 50 else 200 - 2 * q
    return [(v * skala + 50) // 100 for v in dasar]


g = GambarJPEG(muat_mentah("warna444.jpg"))
cek((g.lebar, g.tinggi) == (256, 192), "dimensi 256x192")
cek(len(g.komponen) == 3, "3 komponen")
cek([(k.h, k.v) for k in g.komponen] == [(1, 1)] * 3,
    "4:4:4 sampling 1x1 semua")
cek(g.kuantisasi[0] == skala_kualitas(DASAR_LUM, 90),
    "DQT luminans q90 cocok (zigzag->raster terbukti)")
cek(len(g.huffman_dc) >= 2 and len(g.huffman_ac) >= 2,
    "tabel Huffman DC+AC untuk luma & kroma hadir")

g420 = GambarJPEG(muat_mentah("warna420.jpg"))
cek([(k.h, k.v) for k in g420.komponen] == [(2, 2), (1, 1), (1, 1)],
    "4:2:0 sampling Y 2x2, kroma 1x1")

g422 = GambarJPEG(muat_mentah("warna422.jpg"))
cek([(k.h, k.v) for k in g422.komponen] == [(2, 1), (1, 1), (1, 1)],
    "4:2:2 sampling Y 2x1")

gabu = GambarJPEG(muat_mentah("abu.jpg"))
cek(len(gabu.komponen) == 1 and gabu.komponen[0].h == 1,
    "abu-abu 1 komponen")

cek_galat(lambda: GambarJPEG(b"\xff\xd9"), "SOI rusak ditolak")
cek_galat(lambda: GambarJPEG(b"bukan jpeg sama sekali"),
          "bukan JPEG ditolak")
cek_galat(lambda: GambarJPEG(muat_mentah("warna444.jpg")[:100]),
          "berkas terpotong di segmen ditolak")

print(f"irisan 1: {lulus} cek lulus")
