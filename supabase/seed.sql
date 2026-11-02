-- Runs on `supabase db reset` (local) and can be applied manually after a push.
select private.seed_system_tags();

insert into public.heartbeat (id, last_ping)
values (1, now())
on conflict (id) do update set last_ping = now();
