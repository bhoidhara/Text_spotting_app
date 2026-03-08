# VisionText (Flask + Supabase)

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

Notes:
- If `SUPABASE_SERVICE_KEY` is set, the backend can read/write scans regardless of RLS.
- If you want to rely on RLS + user auth only, enable the policies in `supabase_schema.sql` and ensure the anon key has access.

## Run

```bash
python app.py
```

The app will be available at `http://127.0.0.1:5000`.
