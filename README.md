# VisionText (Flask + Supabase + Free AI)

## Setup

1. Create and activate a Python environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install Tesseract OCR and set `TESSERACT_CMD` in `.env` if it is not on PATH.

## Supabase

1. Create a Supabase project.
2. Run `supabase_schema.sql` in the Supabase SQL editor.
3. Create a Storage bucket named `uploads` (or update `SUPABASE_BUCKET` in `.env`).
4. Update `.env` with:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_KEY`

## Translation (Free)

Uses LibreTranslate. Set:
- `LIBRETRANSLATE_URL` (default: `https://libretranslate.de`)
- Optional `LIBRETRANSLATE_API_KEY`

## TTS (Free)

Uses `gTTS` (Google Translate TTS, no API key).

## Run

```bash
python app.py
```
