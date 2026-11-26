# Rencana — Build 34: JPEG Decoder (ITU T.81)

Sumber: ITU-T T.81 (baseline DCT, Huffman) + konvensi JFIF.
Wasit: Pillow 13.0.0 / libjpeg (venv build 27,
`../png-ref/venv`) — perbandingan BERTOLERANSI, dinyatakan di
depan: JPEG itu lossy dan implementasi IDCT/upsampling yang
berbeda sah menghasilkan piksel berbeda ±beberapa tingkat.
4:4:4 (tanpa subsampling) adalah pembuktian ketat jalur
entropi+DCT; 4:2:0/4:2:2 longgar terdokumentasi (upsampling
nearest-ku vs fancy libjpeg).

## Irisan

- [x] Irisan 1 — Kerangka segmen + tabel: penanda, DQT (urutan
      zigzag!), DHT (tabel Huffman kanonik), SOF0, DRI, SOS;
      pembaca bit MSB-first dengan unstuffing FF00. Uji: urai
      gambar Pillow cocok (dimensi, komponen, sampling, isi
      tabel kuantisasi vs yang Pillow tanamkan).
- [x] Irisan 2 — Dekode entropi + IDCT: DC diferensial +
      ekstensi tanda, AC run/size + ZRL/EOB, dekuantisasi,
      IDCT float separabel, geser level. Uji: abu-abu dan
      warna 4:4:4 melawan Pillow dengan toleransi ketat
      (maks <= 3, rerata <= 0.5) — membuktikan seluruh jalur
      tanpa variabel upsampling.
- [x] Irisan 3 — Sampling + warna + penanda restart: MCU
      4:2:0/4:2:2/4:1:1, upsampling nearest, YCbCr->RGB JFIF,
      RSTn (reset DC + selaraskan bit) dibuktikan dengan
      aliran scan buatan bertabel Huffman mini; progresif
      ditolak tegas sebagai di luar lingkup.

## Keputusan lingkup

- Baseline saja (SOF0, 8-bit, Huffman). Progresif, aritmetik,
  lossless, 12-bit, CMYK: ditolak dengan galat jelas.
- Upsampling nearest-neighbor (libjpeg memakai "fancy"
  segitiga) — selisih tepi kroma pada 4:2:0 adalah konsekuensi
  terdokumentasi, diukur terpisah dari galat IDCT.

## Pagar selesai

- [x] Semua uji irisan 1–3 hijau.
- [x] README.md + CATATAN.md lengkap.
- [ ] Terbit di github.com/h0c0de/build-your-own-jpeg-python
