# Catatan — Build 34: JPEG Decoder (ITU T.81)

## Irisan 1 — Segmen & tabel (11 cek)

Struktur keempat berkas Pillow terurai benar: dimensi,
sampling (4:4:4 = 1×1 semua; 4:2:0 = Y 2×2; 4:2:2 = Y 2×1),
dan — pembuktian kuncinya — tabel kuantisasi luminans hasil
uraiku sama persis dengan tabel Annex K yang diskalakan
kualitas 90 memakai rumus libjpeg. Itu membuktikan pemetaan
zigzag→raster DQT, detail yang salahnya tidak terlihat oleh
mata awam di gambar hasil.

## Irisan 2 — Jalur penuh tanpa subsampling (8 cek)

| Berkas | Maks | Rerata | Dalam ±2 |
|---|---|---|---|
| abu.jpg | 1 | 0,017 | 100,00% |
| warna444.jpg | 3 | 0,023 | 99,99% |

Di sinilah seluruh jalur (entropi, dekuantisasi, IDCT,
warna) terbukti: satu-satunya sumber selisih yang tersisa
adalah IDCT float separabel-ku vs IDCT integer libjpeg.

## Irisan 3 — Subsampling, restart, penolakan (12 cek)

Metodologi toleransi dinyatakan sebelum angka: gambar uji
sengaja dua macam. `halus420.jpg` (gradien saja, fancy ≈
nearest): **maks 2, rerata 0,233, 100% dalam ±2** — jalur
kroma 4:2:0 terbukti ketat. Gambar bertepi tajam: 4:2:0
rerata 1,298 / 90,79% (maks 81 di piksel tepi), 4:2:2 rerata
0,585 / 95,79% — selisih tepi adalah harga metode upsampling
nearest, diukur dan dinamai, bukan disembunyikan di rerata.

Penanda restart dibuktikan tanpa bergantung pada encoder
luar (Pillow tidak mengekspos interval restart): aliran scan
dibangun tangan dengan tabel Huffman mini 2-simbol dan
kuantisasi seragam — satu gambar memakai DRI+RST0 dengan
prediksi DC direset, satu rujukan menulis blok yang sama
sebagai selisih dari prediksi lama. Kedua piksel **identik**,
termasuk penyelarasan bit (blok pertama sengaja 11 bit).
Satu kegagalan uji di tengah jalan bersifat instruktif:
dengan kuantisasi 1, selisih antarblok ±0,35 lenyap oleh
pembulatan sampel (semua 128) — kuantisasi dinaikkan ke 16
agar perbedaan benar-benar teramati (130 vs 128).

Progresif ditolak tegas, scan terpotong ditolak. Total
build: 11 + 8 + 12 = **31 cek** (angka kecil, cakupan penuh:
setiap tahap pipa punya wasitnya sendiri).
