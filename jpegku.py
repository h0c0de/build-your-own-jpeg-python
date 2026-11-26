"""jpegku — dekoder JPEG baseline (ITU-T T.81) dari nol.

Lingkup: SOF0 (DCT 8-bit, Huffman), sampling 4:4:4 / 4:2:2 /
4:2:0 / 4:1:1 / abu-abu, penanda restart (DRI/RSTn), konversi
YCbCr->RGB JFIF. Progresif/aritmetik/lossless/12-bit ditolak
dengan galat jelas, bukan ditebak.

Jalur datanya persis struktur standarnya: segmen -> tabel
kuantisasi & Huffman -> aliran entropi per-MCU (DC diferensial,
AC run/size) -> dekuantisasi -> IDCT -> rakit sampel ->
upsampling -> warna. Tabel kuantisasi di berkas tersimpan
dalam urutan ZIGZAG — detail yang paling sering terlewat.
"""

import math

# Urutan zigzag: posisi sekuensial -> indeks raster (baris*8+kolom)
ZIGZAG = [
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21,
    28, 35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37,
    44, 51, 58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47,
    55, 62, 63,
]

# Matriks kosinus IDCT 1-D: COS[x][u] = cos((2x+1) * u * pi / 16),
# faktor C(u)/2 terlipat di FAKTOR.
_COS = [[math.cos((2 * x + 1) * u * math.pi / 16.0) for u in range(8)]
        for x in range(8)]
_FAKTOR = [1.0 / math.sqrt(2.0)] + [1.0] * 7


class GalatJPEG(Exception):
    pass


# ------------------------------------------------------------------
# Tabel Huffman (B.2.2 / F.2.2): dekode kanonik per panjang kode

class TabelHuffman:
    def __init__(self, hitungan, simbol):
        """hitungan: 16 angka jumlah kode per panjang 1..16."""
        self.peta = {}
        kode = 0
        idx = 0
        for panjang in range(1, 17):
            for _ in range(hitungan[panjang - 1]):
                self.peta[(panjang, kode)] = simbol[idx]
                idx += 1
                kode += 1
            kode <<= 1
        if idx != len(simbol):
            raise GalatJPEG("tabel Huffman tidak konsisten")

    def dekode(self, bit):
        kode = 0
        for panjang in range(1, 17):
            kode = (kode << 1) | bit.baca(1)
            nilai = self.peta.get((panjang, kode))
            if nilai is not None:
                return nilai
        raise GalatJPEG("kode Huffman tidak ditemukan")


# ------------------------------------------------------------------
# Pembaca bit MSB-first dengan unstuffing (F.1.2)

class PembacaBit:
    """Membaca bit dari data scan. FF00 -> byte FF data; FFD0-FFD7
    dicatat sebagai penanda restart yang MENUNGGU (tidak dikonsumsi
    sebagai data); penanda lain mengakhiri scan."""

    def __init__(self, data, pos):
        self.data = data
        self.pos = pos
        self.akumulasi = 0
        self.jumlah_bit = 0
        self.penanda = None          # penanda non-data yang ditemui

    def _byte_berikut(self):
        if self.pos >= len(self.data):
            raise GalatJPEG("data scan habis")
        b = self.data[self.pos]
        if b != 0xFF:
            self.pos += 1
            return b
        if self.pos + 1 >= len(self.data):
            raise GalatJPEG("FF menggantung di akhir data")
        berikut = self.data[self.pos + 1]
        if berikut == 0x00:
            self.pos += 2
            return 0xFF
        if berikut == 0xFF:
            self.pos += 1            # padding FF: geser, nilai ulang
            return self._byte_berikut()
        self.penanda = berikut       # penanda sungguhan: berhenti
        return None

    def baca(self, n):
        """n bit sebagai int (MSB dulu)."""
        while self.jumlah_bit < n:
            b = self._byte_berikut()
            if b is None:
                raise GalatJPEG(
                    f"penanda {self.penanda:#x} muncul di tengah blok")
            self.akumulasi = (self.akumulasi << 8) | b
            self.jumlah_bit += 8
        self.jumlah_bit -= n
        nilai = self.akumulasi >> self.jumlah_bit
        self.akumulasi &= (1 << self.jumlah_bit) - 1
        return nilai

    def selaraskan(self):
        """Buang bit sisa sampai batas byte (sebelum RST)."""
        buang = self.jumlah_bit % 8
        if buang:
            self.baca(buang)

    def ambil_penanda(self):
        """Sesudah selaraskan(): konsumsi FFDn yang menunggu /
        yang ada di posisi sekarang; kembalikan n (0..7) atau
        naikkan galat. Mengonsumsi byte FF Dn dari aliran."""
        if self.penanda is not None:
            n = self.penanda
            self.penanda = None
            self.pos += 2
            if 0xD0 <= n <= 0xD7:
                return n - 0xD0
            raise GalatJPEG(f"penanda tak terduga {n:#x} saat restart")
        # Bit reader belum menyentuh penandanya: baca manual.
        if (self.pos + 1 < len(self.data)
                and self.data[self.pos] == 0xFF
                and 0xD0 <= self.data[self.pos + 1] <= 0xD7):
            n = self.data[self.pos + 1] - 0xD0
            self.pos += 2
            return n
        raise GalatJPEG("penanda restart tidak ditemukan")


def _terima(bit, s):
    """Baca s bit lalu EKSTENSI tanda ala JPEG (F.2.1): nilai
    yang bit tertingginya 0 adalah negatif dalam penyajian
    (nilai - (2^s - 1))."""
    if s == 0:
        return 0
    v = bit.baca(s)
    if v < (1 << (s - 1)):
        v -= (1 << s) - 1
    return v


# ------------------------------------------------------------------
# IDCT float separabel (A.3.3)

def _idct_baris(blok):
    keluar = [0.0] * 64
    for y in range(8):
        dasar = y * 8
        for x in range(8):
            total = 0.0
            for u in range(8):
                total += _FAKTOR[u] * blok[dasar + u] * _COS[x][u]
            keluar[dasar + x] = total * 0.5
    return keluar


def _idct_kolom(blok):
    keluar = [0.0] * 64
    for x in range(8):
        for y in range(8):
            total = 0.0
            for u in range(8):
                total += _FAKTOR[u] * blok[u * 8 + x] * _COS[y][u]
            keluar[y * 8 + x] = total * 0.5
    return keluar


def idct(blok):
    """64 koefisien (raster) -> 64 sampel float (belum digeser)."""
    return _idct_kolom(_idct_baris(blok))


# ------------------------------------------------------------------
# Struktur gambar

class Komponen:
    __slots__ = ("id", "h", "v", "tq", "td", "ta", "lebar", "tinggi",
                 "sampel")

    def __init__(self, id, h, v, tq):
        self.id = id
        self.h = h
        self.v = v
        self.tq = tq
        self.td = self.ta = 0


class GambarJPEG:
    def __init__(self, data):
        self.data = data
        self.lebar = self.tinggi = 0
        self.komponen = []
        self.kuantisasi = {}         # id -> 64 angka (urutan raster)
        self.huffman_dc = {}
        self.huffman_ac = {}
        self.interval_restart = 0
        self._urai_segmen()

    # -- segmen ------------------------------------------------------

    def _urai_segmen(self):
        data = self.data
        if len(data) < 2 or data[0] != 0xFF or data[1] != 0xD8:
            raise GalatJPEG("tidak diawali SOI (FFD8)")
        pos = 2
        while pos < len(data):
            if data[pos] != 0xFF:
                raise GalatJPEG(f"penanda diharapkan di {pos}")
            penanda = data[pos + 1]
            pos += 2
            if penanda == 0xD9:      # EOI
                return
            if penanda == 0xDA:      # SOS: header lalu data scan
                pos = self._urai_sos(pos)
                self._dekode_scan(pos)
                return
            if penanda == 0x01 or 0xD0 <= penanda <= 0xD8:
                continue             # penanda tanpa muatan
            if pos + 2 > len(data):
                raise GalatJPEG("segmen terpotong")
            panjang = (data[pos] << 8) | data[pos + 1]
            isi = data[pos + 2:pos + panjang]
            if len(isi) < panjang - 2:
                raise GalatJPEG("isi segmen terpotong")
            self._urai_satu(penanda, isi)
            pos += panjang
        raise GalatJPEG("SOS tidak ditemukan")

    def _urai_satu(self, penanda, isi):
        if penanda == 0xDB:          # DQT
            p = 0
            while p < len(isi):
                pq, tq = isi[p] >> 4, isi[p] & 0x0F
                p += 1
                if pq == 0:
                    mentah = isi[p:p + 64]
                    p += 64
                else:
                    mentah = [((isi[p + 2 * i] << 8) | isi[p + 2 * i + 1])
                              for i in range(64)]
                    p += 128
                if len(mentah) < 64:
                    raise GalatJPEG("DQT terpotong")
                tabel = [0] * 64
                for k in range(64):
                    tabel[ZIGZAG[k]] = mentah[k]
                self.kuantisasi[tq] = tabel
        elif penanda == 0xC4:        # DHT
            p = 0
            while p < len(isi):
                tc, th = isi[p] >> 4, isi[p] & 0x0F
                hitungan = list(isi[p + 1:p + 17])
                p += 17
                jumlah = sum(hitungan)
                simbol = list(isi[p:p + jumlah])
                p += jumlah
                if len(simbol) < jumlah:
                    raise GalatJPEG("DHT terpotong")
                tabel = TabelHuffman(hitungan, simbol)
                (self.huffman_dc if tc == 0 else self.huffman_ac)[th] = tabel
        elif penanda in (0xC0, 0xC1):    # SOF0 / SOF1 (baseline/ext seq)
            if isi[0] != 8:
                raise GalatJPEG(f"presisi {isi[0]} bit di luar lingkup")
            self.tinggi = (isi[1] << 8) | isi[2]
            self.lebar = (isi[3] << 8) | isi[4]
            self.komponen = []
            for i in range(isi[5]):
                cid, hv, tq = isi[6 + 3 * i:9 + 3 * i]
                self.komponen.append(
                    Komponen(cid, hv >> 4, hv & 0x0F, tq))
            if not self.komponen or not self.lebar or not self.tinggi:
                raise GalatJPEG("SOF tidak lengkap")
        elif 0xC2 <= penanda <= 0xCF and penanda not in (0xC4, 0xC8, 0xCC):
            raise GalatJPEG(
                f"SOF{penanda - 0xC0} (progresif/lossless/dll) "
                "di luar lingkup baseline")
        elif penanda == 0xDD:        # DRI
            self.interval_restart = (isi[0] << 8) | isi[1]
        elif penanda == 0xCC:
            raise GalatJPEG("pengodean aritmetik di luar lingkup")
        # APPn / COM / DNL dll: lewati diam-diam

    def _urai_sos(self, pos):
        data = self.data
        panjang = (data[pos] << 8) | data[pos + 1]
        isi = data[pos + 2:pos + panjang]
        ns = isi[0]
        if ns != len(self.komponen):
            raise GalatJPEG("jumlah komponen SOS != SOF")
        for i in range(ns):
            cid, tt = isi[1 + 2 * i], isi[2 + 2 * i]
            for k in self.komponen:
                if k.id == cid:
                    k.td, k.ta = tt >> 4, tt & 0x0F
        return pos + panjang

    # -- dekode scan ---------------------------------------------------

    def _dekode_scan(self, pos):
        if not self.komponen:
            raise GalatJPEG("SOS sebelum SOF")
        hmax = max(k.h for k in self.komponen)
        vmax = max(k.v for k in self.komponen)
        for k in self.komponen:
            k.lebar = -(-self.lebar * k.h // hmax)
            k.tinggi = -(-self.tinggi * k.v // vmax)
            blok_x = -(-k.lebar // 8)
            blok_y = -(-k.tinggi // 8)
            k.sampel = [[0] * (blok_x * 8) for _ in range(blok_y * 8)]
        mcu_x = -(-self.lebar // (8 * hmax))
        mcu_y = -(-self.tinggi // (8 * vmax))
        total_mcu = mcu_x * mcu_y

        bit = PembacaBit(self.data, pos)
        dc = {k.id: 0 for k in self.komponen}
        rst_berikut = 0
        for mcu in range(total_mcu):
            if (self.interval_restart and mcu > 0
                    and mcu % self.interval_restart == 0):
                bit.selaraskan()
                n = bit.ambil_penanda()
                if n != rst_berikut:
                    raise GalatJPEG(
                        f"RST{n} datang, RST{rst_berikut} diharapkan")
                rst_berikut = (rst_berikut + 1) % 8
                dc = {k.id: 0 for k in self.komponen}
            mx, my = mcu % mcu_x, mcu // mcu_x
            for k in self.komponen:
                for by in range(k.v):
                    for bx in range(k.h):
                        blok = self._dekode_blok(bit, k, dc)
                        self._tulis_blok(k, blok,
                                          mx * k.h + bx, my * k.v + by)

    def _dekode_blok(self, bit, k, dc):
        tdc = self.huffman_dc[k.td]
        tac = self.huffman_ac[k.ta]
        kuant = self.kuantisasi[k.tq]
        koef = [0] * 64
        s = tdc.dekode(bit)
        dc[k.id] += _terima(bit, s)
        koef[0] = dc[k.id] * kuant[0]
        idx = 1
        while idx < 64:
            rs = tac.dekode(bit)
            r, s = rs >> 4, rs & 0x0F
            if s == 0:
                if r == 15:
                    idx += 16
                    continue
                break                      # EOB
            idx += r
            if idx > 63:
                raise GalatJPEG("indeks AC melewati blok")
            koef[ZIGZAG[idx]] = _terima(bit, s) * kuant[ZIGZAG[idx]]
            idx += 1
        return koef

    def _tulis_blok(self, k, koef, bx, by):
        sampel = idct(koef)
        for y in range(8):
            baris = k.sampel[by * 8 + y]
            dasar = y * 8
            for x in range(8):
                nilai = int(round(sampel[dasar + x])) + 128
                baris[bx * 8 + x] = 0 if nilai < 0 else (
                    255 if nilai > 255 else nilai)

    # -- hasil ----------------------------------------------------------

    def ke_rgb(self):
        """(lebar, tinggi, bytearray RGB) — upsampling nearest."""
        W, H = self.lebar, self.tinggi
        keluar = bytearray(W * H * 3)
        if len(self.komponen) == 1:
            k = self.komponen[0]
            for y in range(H):
                for x in range(W):
                    v = k.sampel[y][x]
                    o = (y * W + x) * 3
                    keluar[o] = keluar[o + 1] = keluar[o + 2] = v
            return W, H, keluar
        if len(self.komponen) != 3:
            raise GalatJPEG(
                f"{len(self.komponen)} komponen di luar lingkup "
                "(hanya abu-abu & YCbCr 3 komponen)")
        ky, kcb, kcr = self.komponen
        for y in range(H):
            for x in range(W):
                yy = ky.sampel[y][x]
                cb = kcb.sampel[y * kcb.tinggi // H][x * kcb.lebar // W] - 128
                cr = kcr.sampel[y * kcr.tinggi // H][x * kcr.lebar // W] - 128
                o = (y * W + x) * 3
                r = yy + 1.402 * cr
                g = yy - 0.34414 * cb - 0.71414 * cr
                b = yy + 1.772 * cb
                keluar[o] = 0 if r < 0 else (255 if r > 255 else round(r))
                keluar[o + 1] = 0 if g < 0 else (255 if g > 255 else round(g))
                keluar[o + 2] = 0 if b < 0 else (255 if b > 255 else round(b))
        return W, H, keluar


def dekode(data):
    """Byte JPEG -> (lebar, tinggi, bytearray RGB)."""
    return GambarJPEG(data).ke_rgb()
