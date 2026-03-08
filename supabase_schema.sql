-- Supabase schema for VisionText
-- Run this in the Supabase SQL editor.

create extension if not exists "pgcrypto";

create table if not exists profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  full_name text,
  avatar_url text,
  created_at timestamptz default now()
);

create table if not exists scans (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  image_paths jsonb default '[]'::jsonb,
  extracted_text text,
  cleaned_text text,
  language text,
  intent text,
  confidence_avg numeric,
  low_confidence_words jsonb default '[]'::jsonb,
  summary text,
  key_points jsonb default '[]'::jsonb,
  mcqs jsonb default '[]'::jsonb,
  tags jsonb default '[]'::jsonb,
  translation jsonb,
  is_private boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz
);

create index if not exists idx_scans_user_created on scans(user_id, created_at desc);

create table if not exists exports (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid references scans(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  format text,
  file_path text,
  created_at timestamptz default now()
);

create table if not exists translations (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid references scans(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  source_lang text,
  target_lang text,
  text text,
  created_at timestamptz default now()
);

-- Optional RLS (recommended for production)
-- alter table profiles enable row level security;
-- alter table scans enable row level security;
-- alter table exports enable row level security;
-- alter table translations enable row level security;

-- create policy "Profiles are viewable by owner" on profiles
--   for select using (auth.uid() = id);
-- create policy "Profiles insert by owner" on profiles
--   for insert with check (auth.uid() = id);
-- create policy "Profiles update by owner" on profiles
--   for update using (auth.uid() = id);

-- create policy "Scans are viewable by owner" on scans
--   for select using (auth.uid() = user_id);
-- create policy "Scans insert by owner" on scans
--   for insert with check (auth.uid() = user_id);
-- create policy "Scans update by owner" on scans
--   for update using (auth.uid() = user_id);
-- create policy "Scans delete by owner" on scans
--   for delete using (auth.uid() = user_id);

-- create policy "Exports are viewable by owner" on exports
--   for select using (auth.uid() = user_id);
-- create policy "Exports insert by owner" on exports
--   for insert with check (auth.uid() = user_id);
-- create policy "Exports update by owner" on exports
--   for update using (auth.uid() = user_id);
-- create policy "Exports delete by owner" on exports
--   for delete using (auth.uid() = user_id);

-- create policy "Translations are viewable by owner" on translations
--   for select using (auth.uid() = user_id);
-- create policy "Translations insert by owner" on translations
--   for insert with check (auth.uid() = user_id);
-- create policy "Translations update by owner" on translations
--   for update using (auth.uid() = user_id);
-- create policy "Translations delete by owner" on translations
--   for delete using (auth.uid() = user_id);
