-- Access control and the private receipt bucket.
--
-- The API is the only writer: it uses the service role and checks membership on
-- every route. Direct browser access (anon/authenticated) is therefore
-- SELECT-only, and RLS narrows those reads to the caller's household. This is
-- stricter than allowing client writes and keeps validation in one place.

set search_path = public, extensions;

create or replace function public.is_household_member(p_household uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.household_members hm
    where hm.household_id = p_household
      and hm.user_id = auth.uid()
  );
$$;

revoke all on function public.is_household_member(uuid) from public;
grant execute on function public.is_household_member(uuid) to authenticated;

alter table public.households enable row level security;
alter table public.household_members enable row level security;
alter table public.receipts enable row level security;
alter table public.receipt_pages enable row level security;
alter table public.tags enable row level security;
alter table public.receipt_tags enable row level security;
alter table public.heartbeat enable row level security;

create policy households_select_member
  on public.households for select to authenticated
  using (public.is_household_member(id));

create policy household_members_select_member
  on public.household_members for select to authenticated
  using (public.is_household_member(household_id));

create policy receipts_select_member
  on public.receipts for select to authenticated
  using (public.is_household_member(household_id));

create policy receipt_pages_select_member
  on public.receipt_pages for select to authenticated
  using (
    exists (
      select 1 from public.receipts r
      where r.id = receipt_pages.receipt_id
        and public.is_household_member(r.household_id)
    )
  );

create policy tags_select_system_or_member
  on public.tags for select to authenticated
  using (household_id is null or public.is_household_member(household_id));

create policy receipt_tags_select_member
  on public.receipt_tags for select to authenticated
  using (
    exists (
      select 1 from public.receipts r
      where r.id = receipt_tags.receipt_id
        and public.is_household_member(r.household_id)
    )
  );

create policy heartbeat_select_public
  on public.heartbeat for select to anon, authenticated
  using (true);

grant usage on schema public to anon, authenticated, service_role;
grant select on public.households, public.household_members, public.receipts,
  public.receipt_pages, public.tags, public.receipt_tags to authenticated;
grant select on public.heartbeat to anon, authenticated;
grant all on public.households, public.household_members, public.receipts,
  public.receipt_pages, public.tags, public.receipt_tags, public.heartbeat
  to service_role;

-- Private bucket. The API writes with the service role, so direct browser
-- access is read-only: no authenticated INSERT/UPDATE/DELETE policies exist.
-- If a future client uploads straight to Storage, add a narrowly scoped insert
-- policy then, together with the upload validation it needs.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'receipts',
  'receipts',
  false,
  10485760,
  array['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
)
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

create policy receipts_storage_read
  on storage.objects for select to authenticated
  using (
    bucket_id = 'receipts'
    and public.is_household_member(((storage.foldername(name))[1])::uuid)
  );
