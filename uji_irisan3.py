"""Irisan 3 — subsampling, restart, penolakan di luar lingkup.

Metodologi toleransi (dinyatakan, bukan disembunyikan):
- halus420 (gradien saja): upsampling fancy libjpeg vs nearest
  nyaris identik -> toleransi KETAT membuktikan jalur kroma.
- warna420/422 (tepi kroma tajam): selisih besar di tepi adalah
  konsekuensi METODE upsampling, jadi yang diuji rerata + %
  dalam +-2, dan maks hanya dilaporkan.
"""
import struct
import sys

sys.path.insert(0, ".")

from jpegku import GalatJPEG, GambarJPEG, dekode
from uji_bersama import banding, muat_mentah, muat_wasit

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


# --- Subsampling -------------------------------------------------------
w0, h0, wasit = muat_wasit("halus420.jpg")
w, h, rgb = dekode(muat_mentah("halus420.jpg"))
maks, rerata, persen = banding(rgb, wasit)
print(f"  halus420: maks={maks} rerata={rerata:.3f} dalam+-2={persen:.2f}%")
cek(maks <= 4 and rerata <= 0.6 and persen >= 99.9,
    "halus420: jalur kroma terbukti ketat di gambar halus")

for nama, batas_rerata, batas_persen in [("warna420.jpg", 1.6, 88.0),
                                         ("warna422.jpg", 0.8, 94.0)]:
    w0, h0, wasit = muat_wasit(nama)
    w, h, rgb = dekode(muat_mentah(nama))
    cek((w, h) == (w0, h0), f"{nama}: dimensi")
    maks, rerata, persen = banding(rgb, wasit)
    print(f"  {nama}: maks={maks} (metode upsampling) "
          f"rerata={rerata:.3f} dalam+-2={persen:.2f}%")
    cek(rerata <= batas_rerata, f"{nama}: rerata {rerata:.3f}")
    cek(persen >= batas_persen, f"{nama}: {persen:.2f}% dalam +-2")

# --- Penanda restart: aliran buatan bertabel mini ----------------------
# Tabel Huffman mini: DC simbol [0,1] kode 00/01; AC simbol
# [0x01, 0x00(EOB)] kode 00/01. Kuantisasi semua 1.
def segmen(penanda, isi):
    return b"\xff" + bytes([penanda]) + struct.pack("!H", len(isi) + 2) + isi


def bangun_jpeg(scan, pakai_restart):
    keluar = bytearray(b"\xff\xd8")
    # Kuantisasi 16: koefisien kecil terlihat sesudah IDCT
    # (DC 1 -> sampel 130 vs 128), bukan hilang oleh pembulatan.
    keluar += segmen(0xDB, bytes([0x00]) + bytes([16] * 64))
    dht = bytes([0x00]) + bytes([0, 2] + [0] * 14) + bytes([0, 1])
    dht += bytes([0x10]) + bytes([0, 2] + [0] * 14) + bytes([0x01, 0x00])
    keluar += segmen(0xC4, dht)
    keluar += segmen(0xC0, bytes([8]) + struct.pack("!HH", 8, 16)
                     + bytes([1, 1, 0x11, 0]))
    if pakai_restart:
        keluar += segmen(0xDD, struct.pack("!H", 1))
    keluar += segmen(0xDA, bytes([1, 1, 0x00, 0, 63, 0]))
    keluar += scan
    keluar += b"\xff\xd9"
    return bytes(keluar)


class PenulisBit:
    def __init__(self):
        self.bit = []

    def tulis(self, kode, panjang):
        for i in range(panjang - 1, -1, -1):
            self.bit.append((kode >> i) & 1)

    def byte(self):
        while len(self.bit) % 8:
            self.bit.append(1)          # padding bit 1 ala JPEG
        keluar = bytearray()
        for i in range(0, len(self.bit), 8):
            b = 0
            for bit in self.bit[i:i + 8]:
                b = (b << 1) | bit
            keluar.append(b)
        self.bit = []
        return bytes(keluar)


def blok_a(p):
    p.tulis(0b01, 2)      # DC kategori 1
    p.tulis(0b1, 1)       # diff +1 -> DC absolut 1 (pred 0)
    p.tulis(0b00, 2)      # AC rs=0x01
    p.tulis(0b1, 1)       # koef +1
    p.tulis(0b00, 2)      # AC rs=0x01
    p.tulis(0b0, 1)       # koef -1
    p.tulis(0b01, 2)      # EOB


# Versi restart: blok B sesudah RST0, pred DC RESET -> absolut 0
# ditulis kategori 0. Total bit blok A 11 -> penyelarasan diuji.
p = PenulisBit()
blok_a(p)
scan_rst = p.byte() + b"\xff\xd0"
p = PenulisBit()
p.tulis(0b00, 2)          # DC kategori 0 -> absolut 0
p.tulis(0b01, 2)          # EOB
scan_rst += p.byte()

# Versi rujukan tanpa restart: blok B ditulis sebagai diff -1
# dari pred 1 -> absolut 0 yang sama.
p = PenulisBit()
blok_a(p)
p.tulis(0b01, 2)          # DC kategori 1
p.tulis(0b0, 1)           # diff -1 -> absolut 0
p.tulis(0b01, 2)          # EOB
scan_ref = p.byte()

w1, h1, rgb_rst = dekode(bangun_jpeg(scan_rst, True))
w2, h2, rgb_ref = dekode(bangun_jpeg(scan_ref, False))
cek((w1, h1) == (16, 8), "restart: dimensi 16x8")
cek(rgb_rst == rgb_ref,
    "restart: piksel identik dengan rujukan tanpa restart "
    "(reset DC + penyelarasan terbukti)")
cek(rgb_rst[0] != rgb_rst[8 * 3],
    "restart: blok A dan B memang berbeda nilai")

# --- Di luar lingkup & berkas rusak ------------------------------------
cek_galat(lambda: GambarJPEG(muat_mentah("progresif.jpg")),
          "JPEG progresif ditolak tegas")
mentah = muat_mentah("warna444.jpg")
cek_galat(lambda: dekode(mentah[:len(mentah) // 2]),
          "scan terpotong ditolak")

print(f"irisan 3: {lulus} cek lulus")
