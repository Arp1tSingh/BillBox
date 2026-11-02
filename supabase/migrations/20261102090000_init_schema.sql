-- BillBox initial schema.
-- All rows that hold household data point at households, so access control is
-- one membership check.

set search_path = public, extensions;

create extension if not exists pg_trgm with schema extensions;

create schema if not exists private;
revoke all on schema private from public;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.households (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(btrim(name)) between 1 and 80),
  invite_code text not null unique
    check (invite_code ~ '^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$'),
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.household_members (
  household_id uuid not null references public.households(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'member')),
  created_at timestamptz not null default now(),
  primary key (household_id, user_id),
  -- MVP: one household per account. Private vaults later are container-level,
  -- not a second membership.
  unique (user_id)
);

create table if not exists public.receipts (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households(id) on delete cascade,
  created_by uuid references auth.users(id) on delete set null,
  title text,
  merchant text,
  amount numeric(12, 2) check (amount is null or amount >= 0),
  currency char(3) not null default 'INR',
  bill_date date,
  bill_type text,
  language text,
  status text not null default 'processing'
    check (status in ('processing', 'ready', 'failed')),
  raw_text text,
  extracted jsonb,
  search_vector tsvector,
  vault_id uuid,
  ai_skipped boolean not null default false,
  failure_reason text,
  processing_started_at timestamptz,
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.receipt_pages (
  id uuid primary key default gen_random_uuid(),
  receipt_id uuid not null references public.receipts(id) on delete cascade,
  page_no integer not null check (page_no between 1 and 10),
  storage_path text not null,
  mime_type text not null,
  size_bytes bigint not null check (size_bytes >= 0),
  created_at timestamptz not null default now(),
  unique (receipt_id, page_no)
);

create table if not exists public.tags (
  id uuid primary key default gen_random_uuid(),
  household_id uuid references public.households(id) on delete cascade,
  slug text not null,
  label_en text not null,
  label_hi text,
  label_mr text,
  kind text not null check (kind in ('bill_type', 'merchant', 'custom')),
  keywords text[] not null default '{}',
  created_at timestamptz not null default now()
);

create unique index if not exists tags_system_slug_key
  on public.tags (slug) where household_id is null;
create unique index if not exists tags_household_slug_key
  on public.tags (household_id, slug) where household_id is not null;

create table if not exists public.receipt_tags (
  receipt_id uuid not null references public.receipts(id) on delete cascade,
  tag_id uuid not null references public.tags(id) on delete cascade,
  source text not null check (source in ('rule', 'ai', 'user')),
  confidence numeric(4, 3) check (confidence is null or confidence between 0 and 1),
  created_at timestamptz not null default now(),
  removed_at timestamptz,
  removed_by uuid references auth.users(id) on delete set null,
  primary key (receipt_id, tag_id)
);

create table if not exists public.heartbeat (
  id integer primary key default 1 check (id = 1),
  last_ping timestamptz not null default now()
);

create index if not exists receipts_household_date_idx
  on public.receipts (household_id, bill_date desc);
create index if not exists receipts_household_amount_idx
  on public.receipts (household_id, amount);
create index if not exists receipts_search_vector_idx
  on public.receipts using gin (search_vector);
create index if not exists receipts_merchant_trgm_idx
  on public.receipts using gin (merchant gin_trgm_ops);
create index if not exists receipt_tags_tag_idx
  on public.receipt_tags (tag_id);

create trigger households_set_updated_at
  before update on public.households
  for each row execute function private.set_updated_at();
create trigger receipts_set_updated_at
  before update on public.receipts
  for each row execute function private.set_updated_at();

-- The API checks the cap, but the database also enforces it so two concurrent
-- joins cannot create a ninth member. Locking the household serialises joins.
create or replace function private.enforce_household_member_cap()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform 1 from public.households where id = new.household_id for update;
  if (
    select count(*) from public.household_members
    where household_id = new.household_id
  ) >= 8 then
    raise exception 'household_full' using errcode = 'P0001';
  end if;
  return new;
end;
$$;

create trigger household_members_enforce_cap
  before insert on public.household_members
  for each row execute function private.enforce_household_member_cap();

comment on table public.receipts is
  'Bill images/PDFs with extracted fields. search_vector is filled in Section 4.';
comment on table public.heartbeat is
  'Operational only: keep-alive ping for the Supabase free tier.';
