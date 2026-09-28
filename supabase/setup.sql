-- Run this once in the Supabase SQL Editor for the project.
-- The Streamlit server uses a Supabase secret/service-role key; never expose
-- that key to a browser or commit it to source control.

create table if not exists public.manual_values (
    asset text not null,
    field_key text not null,
    raw_value jsonb not null default '{}'::jsonb,
    primary key (asset, field_key)
);

alter table public.manual_values enable row level security;

-- The app talks to Supabase from its server using its secret key.
-- Do not grant table access to browser-facing roles.
revoke all on table public.manual_values from anon, authenticated;
grant select, insert, update, delete on table public.manual_values to service_role;
