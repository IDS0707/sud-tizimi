# UDIP — Universal Document Intelligence Platform

> OCR + Qidiruv + AI + Hujjat Tahlili platformasi
> *(OCR + Search + AI + Document Analysis platform)*

UDIP istalgan hujjat yoki rasmni qabul qilib, uning ichidagi matnni
aniqlaydigan (OCR), qidiradigan, ajratib oladigan va sun'iy intellekt
yordamida tahlil qiladigan platforma. Ushbu repozitoriy
`UDIP_Kengaytirilgan_TZ.docx` texnik topshirig'i asosida qurilgan.

---

## ✨ Imkoniyatlar (TZ — 2-bo'lim)

| # | Funksiya | Tavsifi |
|---|----------|---------|
| 2.1 | **OCR** | Rasm/skanlardan matn va koordinatalarni olish |
| 2.2 | **PDF tahlili** | Matnli va skan PDF (avtomatik aniqlash) |
| 2.3 | **Word tahlili** | DOCX: matn, sarlavha, jadval, rasm |
| 2.4 | **Excel tahlili** | XLSX: varaqlar va kataklar |
| 2.5 | **PowerPoint tahlili** | PPTX: slayd matni va izohlari |
| 2.6 | **Layout tahlili** | Sarlavha/matn/jadval/rasm ajratish |
| 2.7 | **Jadvallarni tanib olish** | Qator-ustun tiklash |
| 2.8 | **Formula OCR** | Matematik formulalarni matnga aylantirish |
| 2.9 | **Aqlli qidiruv** | Barcha hujjatlar bo'ylab kalit so'z qidirish |
| 2.10 | **AI tahlili** | Xulosa, muhim ma'lumot ajratish |
| 2.11 | **Hujjat bilan chat** | RAG asosida savol-javob |
| 2.12 | **Eksport** | TXT, DOCX, JSON, Markdown |

## 🧱 Texnologiyalar to'plami (TZ — 5-bo'lim)

| Qism | Texnologiya |
|------|-------------|
| Backend | Python 3.12+, FastAPI, Uvicorn |
| OCR | PaddleOCR / PP-StructureV3 *(ixtiyoriy, stub bilan)* |
| Rasm | OpenCV, Pillow |
| PDF | PyMuPDF, pdf2image |
| Word / Excel / PPT | python-docx, openpyxl + pandas, python-pptx |
| Ma'lumotlar bazasi | PostgreSQL *(default: SQLite)* |
| Cache | Redis *(default: in-memory)* |
| Fayl saqlash | MinIO *(default: lokal disk)* |

> **Eslatma:** og'ir bog'liqliklar (PaddleOCR, Postgres, Redis, MinIO)
> **ixtiyoriy**. Ular o'rnatilmagan bo'lsa, platforma yengil zaxira
> (fallback) variantlarga o'tadi va baribir ishlaydi — bu mahalliy
> ishga tushirishni osonlashtiradi.

## 📁 Loyiha tuzilishi (TZ — 9-bo'lim)

```
app/
  api/        # API yo'nalishlari (endpointlar)
  services/   # Asosiy biznes-mantiq
  parsers/    # Fayl tahlilchilari (PDF, Word, ...)
  ocr/        # OCR modullari
  ai/         # AI tahlili va chat
  database/   # Ma'lumotlar bazasi
  schemas/    # Kirish/chiqish formatlari
  utils/      # Yordamchi funksiyalar
uploads/      # Yuklangan fayllar
outputs/      # Eksport natijalari
logs/         # Loglar
tests/        # Testlar
main.py       # Ishga tushish nuqtasi
```

## 🚀 Ishga tushirish

```bash
# 1. Virtual muhit
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 2. Bog'liqliklarni o'rnatish
pip install -r requirements.txt

# 3. (ixtiyoriy) sozlamalar
copy .env.example .env

# 4. Ishga tushirish
python main.py
#   yoki: uvicorn main:app --reload
```

So'ng oching:
- Web interfeys: <http://localhost:8000>
- Boshqaruv paneli: <http://localhost:8000/admin>
- Swagger UI: <http://localhost:8000/docs>

### 🔤 Haqiqiy OCR (rasm/skandan matn) — ixtiyoriy

Standart holatda OCR **stub** rejimida (bo'sh matn). Rasmlardan matn olish uchun
OCR mexanizmini o'rnating (engine ularni avtomatik tanlaydi):

```powershell
# Variant A — Tesseract (yengil, tavsiya etiladi):
pip install pytesseract
winget install UB-Mannheim.TesseractOCR
# O'zbek/rus tillari: *.traineddata fayllarni ./.tessdata ga joylang
#   (https://github.com/tesseract-ocr/tessdata)

# Variant B — PaddleOCR (eng sifatli, og'irroq):
pip install paddlepaddle paddleocr
```

OCR tili `.env` da: `OCR_LANG=uzb+rus+eng` (Tesseract uchun `+` bilan birlashtiriladi).

## 🔌 API yo'nalishlari (TZ — 7-bo'lim)

| Turi | Yo'nalish | Vazifasi |
|------|-----------|----------|
| POST | `/api/v1/upload` | Fayl yuklash |
| POST | `/api/v1/ocr` | Rasmdan matn olish |
| POST | `/api/v1/parse` | Hujjatni tahlil qilish |
| POST | `/api/v1/search` | Hujjatlar ichida qidirish |
| POST | `/api/v1/chat` | Hujjat bilan suhbat |
| POST | `/api/v1/export` | Natijani eksport qilish |
| GET  | `/api/v1/task/{id}` | Vazifa holatini tekshirish |

## 🗺️ Yo'l xaritasi (TZ — 10-bo'lim)

- [x] **V1** — PNG/JPG/PDF uchun OCR ✅
- [x] **Web UI** — 3 ustunli brauzer interfeysi ✅
- [x] **V2** — DOCX/XLSX/PPTX/TXT/RTF tahlili ✅
- [x] **V3** — Layout tahlili, jadvallarni tanib olish ✅
- [x] **V4** — Formula OCR, aqlli qidiruv ✅
- [x] **V5** — AI tahlili, entity, chat (RAG), eksport ✅
- [x] **V6** — SaaS, API kalitlari, boshqaruv paneli ✅

**🎉 Barcha bosqichlar yakunlandi!** Platforma to'liq ishlaydi:
brauzer UI (`/`), boshqaruv paneli (`/admin`), API hujjatlari (`/docs`).

## 📜 Litsenziya

Ushbu loyiha texnik topshiriq asosida o'quv/ishlab chiqish maqsadida
yaratilmoqda.
