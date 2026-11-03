-- Full-text search: maintain receipts.search_vector and rank/filter in one RPC.

set search_path = public, extensions;

create or replace function private.receipts_search_vector_trigger()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  new.search_vector := to_tsvector(
    'simple',
    coalesce(new.title, '') || ' ' ||
    coalesce(new.merchant, '') || ' ' ||
    coalesce(new.bill_type, '') || ' ' ||
    coalesce(new.raw_text, '') || ' ' ||
    coalesce(
      (
        select string_agg(
          coalesce(t.label_en, '') || ' ' ||
          coalesce(t.label_hi, '') || ' ' ||
          coalesce(t.label_mr, ''),
          ' '
        )
        from public.receipt_tags rt
        join public.tags t on t.id = rt.tag_id
        where rt.receipt_id = new.id and rt.removed_at is null
      ),
      ''
    )
  );
  return new;
end;
$$;

create trigger receipts_search_vector
  before insert or update on public.receipts
  for each row execute function private.receipts_search_vector_trigger();

create or replace function private.receipt_tags_search_vector_trigger()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  target uuid;
begin
  target := coalesce(new.receipt_id, old.receipt_id);
  -- Re-saving the row fires the receipts trigger, which recomputes the vector
  -- with the now-visible tag rows.
  update public.receipts set updated_at = updated_at where id = target;
  return null;
end;
$$;

create trigger receipt_tags_search_vector
  after insert or update or delete on public.receipt_tags
  for each row execute function private.receipt_tags_search_vector_trigger();

create index if not exists receipts_search_vector_idx
  on public.receipts using gin (search_vector);

create or replace function public.search_receipts(
  p_household uuid,
  p_query text default null,
  p_tag_ids uuid[] default null,
  p_from date default null,
  p_to date default null,
  p_min numeric default null,
  p_max numeric default null,
  p_sort text default 'date',
  p_limit integer default 20,
  p_offset integer default 0
)
returns table (
  id uuid,
  household_id uuid,
  title text,
  merchant text,
  amount numeric,
  currency char(3),
  bill_date date,
  bill_type text,
  status text,
  ai_skipped boolean,
  failure_reason text,
  created_at timestamptz,
  relevance integer,
  total bigint
)
language sql
stable
security definer
set search_path = ''
as $$
  with q as (
    select nullif(btrim(coalesce(p_query, '')), '') as term
  ),
  base as (
    select
      r.*,
      case
        when q.term is null then 0
        when r.search_vector @@ websearch_to_tsquery('simple', q.term) then 1
        else 0
      end as fts_hit,
      case
        when q.term is null then 0
        when extensions.word_similarity(q.term, coalesce(r.merchant, '')) > 0.5 then 1
        else 0
      end as merchant_hit,
      case
        when coalesce(array_length(p_tag_ids, 1), 0) = 0 then 0
        else (
          select count(distinct rt.tag_id)::integer
          from public.receipt_tags rt
          where rt.receipt_id = r.id
            and rt.removed_at is null
            and rt.tag_id = any(p_tag_ids)
        )
      end as tag_hits
    from public.receipts r, q
    where r.household_id = p_household
      and (p_from is null or r.bill_date >= p_from)
      and (p_to is null or r.bill_date <= p_to)
      and (p_min is null or r.amount >= p_min)
      and (p_max is null or r.amount <= p_max)
  ),
  filtered as (
    select
      b.*,
      case
        when b.tag_hits > 0 then 3
        when b.merchant_hit > 0 then 2
        when b.fts_hit > 0 then 1
        else 0
      end as relevance
    from base b
    where (coalesce(array_length(p_tag_ids, 1), 0) = 0
           or b.tag_hits = array_length(p_tag_ids, 1))
      and (
        (select term from q) is null
        or b.fts_hit > 0
        or b.merchant_hit > 0
        or b.tag_hits > 0
      )
  )
  select
    f.id,
    f.household_id,
    f.title,
    f.merchant,
    f.amount,
    f.currency,
    f.bill_date,
    f.bill_type,
    f.status,
    f.ai_skipped,
    f.failure_reason,
    f.created_at,
    f.relevance,
    count(*) over() as total
  from filtered f
  order by
    case when p_sort = 'relevance' then f.relevance end desc nulls last,
    case when p_sort = 'amount' then f.amount end desc nulls last,
    case
      when p_sort is null or p_sort in ('date', 'relevance') then f.bill_date
    end desc nulls last,
    f.created_at desc
  limit greatest(1, least(coalesce(p_limit, 20), 50))
  offset greatest(0, coalesce(p_offset, 0));
$$;

revoke all on function public.search_receipts(
  uuid, text, uuid[], date, date, numeric, numeric, text, integer, integer
) from public;
grant execute on function public.search_receipts(
  uuid, text, uuid[], date, date, numeric, numeric, text, integer, integer
) to authenticated, service_role;
