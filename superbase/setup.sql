-- Run once in the Supabase SQL Editor. Safe to re-run.
create table if not exists public.manual_values (
  asset text not null,
  field_key text not null,
  raw_value jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (asset, field_key)
);
alter table public.manual_values enable row level security;
revoke all on table public.manual_values from anon, authenticated;
grant select, insert, update, delete on table public.manual_values to service_role;
