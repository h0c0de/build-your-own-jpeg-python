# Build Your Own — JPEG Decoder

**Dekoder JPEG baseline (ITU-T T.81)** dalam Python murni:
segmen & tabel, dekode entropi Huffman (DC diferensial + AC
run/size), dekuantisasi, IDCT, upsampling, dan konversi
YCbCr→RGB. Divalidasi melawan Pillow/libjpeg dengan
metodologi toleransi yang dinyatakan terbuka — JPEG itu
*lossy*, dan build ini memisahkan dengan rapi mana selisih
yang salah-implementasi dan mana yang beda-metode-sah.

## Isi

| Berkas | Isi |
|---|---|
| `jpegku.py` | Parser segmen, tabel Huffman/kuantisasi, pembaca bit, IDCT, perakit piksel |
| `uji_bersama.py` | Pembanding piksel (maks / rerata / % dalam ±2) |
| `uji_irisan1.py` … `uji_irisan3.py` | Uji per irisan (perlu Pillow dari venv build 27) |
| `../jpeg-ref/buat_gambar.py` | Pembuat gambar uji deterministik |

## Memakai

```python
from jpegku import dekode

lebar, tinggi, rgb = dekode(open("foto.jpg", "rb").read())
# rgb: bytearray RGB berurutan, lebar*tinggi*3 byte
```

## Tiga hal yang menentukan

1. **Tabel kuantisasi tersimpan dalam urutan zigzag.** Byte
   ke-k di segmen DQT adalah koefisien zigzag ke-k, bukan
   raster ke-k. Lupa memetakannya dan gambar tetap "terlihat
   jadi" — tapi semua nilai salah. Di sini dibuktikan melawan
   tabel Annex K yang diskalakan kualitas 90.
2. **DC itu selisih, AC itu (lari, ukuran).** Koefisien DC
   adalah selisih dari blok sebelumnya pada komponen yang
   sama — dan penanda restart (RSTn) memutus rantai itu:
   prediksi kembali ke nol dan aliran bit diselaraskan ke
   batas byte. Dibuktikan dengan aliran scan buatan yang
   pikselnya identik dengan rujukan tanpa restart.
3. **"Salah ±2" dan "salah metode" harus dipisah.** Pada
   4:4:4 (tanpa subsampling) build ini berjarak maks 3 dari
   libjpeg — itulah galat IDCT yang sah. Pada 4:2:0 bertepi
   tajam selisih bisa 81 di satu piksel tepi: itu upsampling
   *fancy* libjpeg vs *nearest* di sini, bukan bug — dan di
   gambar halus (fancy ≈ nearest) 4:2:0 kembali ketat
   (maks 2, 100% dalam ±2).

## Kejujuran lingkup

Hanya baseline SOF0/SOF1 8-bit Huffman: progresif, aritmetik,
lossless, 12-bit, dan CMYK ditolak dengan galat jelas.
Upsampling nearest-neighbor dengan konsekuensi terukur di
atas. Kinerja murni Python: ±0,6 detik untuk 256×192.

## Lisensi

Kode: MIT. ITU-T T.81 adalah spesifikasi publik. Pillow hanya
wasit uji, tidak disertakan.
