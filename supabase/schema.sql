-- SPDX-License-Identifier: AGPL-3.0-only
-- agragent: database schema for a new Supabase project (run once in the SQL Editor).
--
-- Access model:
--   * The browser only uses the anon key for Supabase Auth (sign-in). It cannot read or write these tables.
--   * The API functions in api/ use the service_role key and enforce ownership themselves (api/_auth.js).
--   * Row-level security below restricts any authenticated direct access to the owner's own rows.
--   * Accounts are created by an administrator. Each account needs app_metadata.tenant equal to one of
--     the values in APP_TENANTS (default 'agragent'); accounts without it are rejected by the API.

-- Conversations with the assistant
create table if not exists public.conversations (
  id         uuid primary key default gen_random_uuid(),
  user_id    text not null,
  owner      uuid references auth.users(id) on delete cascade,  -- null = anonymous chat (tenant 'public')
  tenant     text not null default 'agragent',
  title      text default 'New conversation',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.messages (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid references public.conversations(id) on delete cascade,
  role            text not null check (role in ('user', 'assistant', 'system')),
  content         text not null,
  tool_calls      jsonb default '[]'::jsonb,
  created_at      timestamptz default now()
);

-- Saved fields ("My fields")
create table if not exists public.fields (
  id          uuid primary key default gen_random_uuid(),
  user_id     text not null,
  owner       uuid references auth.users(id) on delete cascade,
  tenant      text not null default 'agragent',
  name        text not null default 'My field',
  color       text not null default '#52b788',
  description text,
  stage       text,
  crop_type   text,
  client_name text,
  geometry    jsonb not null,
  area_ha     numeric(10,4),
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

create index if not exists conversations_owner_idx on public.conversations (owner, updated_at desc);
create index if not exists conversations_user_idx  on public.conversations (user_id);
create index if not exists messages_conversation_idx on public.messages (conversation_id);
create index if not exists fields_owner_idx        on public.fields (owner, updated_at desc);

-- Daily chat quota per user (CHAT_DAILY_LIMIT in the API)
create table if not exists public.usage (
  owner    uuid not null references auth.users(id) on delete cascade,
  day      date not null default current_date,
  tenant   text not null,
  requests int  not null default 0,
  primary key (owner, day)
);

create or replace function public.bump_usage(p_owner uuid, p_tenant text)
returns int language sql security definer set search_path = public as $$
  insert into public.usage (owner, day, tenant, requests) values (p_owner, current_date, p_tenant, 1)
  on conflict (owner, day) do update set requests = public.usage.requests + 1
  returning requests;
$$;
revoke all on function public.bump_usage(uuid, text) from public, anon, authenticated;

-- Row-level security: owner only
alter table public.conversations enable row level security;
alter table public.messages      enable row level security;
alter table public.fields        enable row level security;
alter table public.usage         enable row level security;

create policy conversations_owner on public.conversations for all to authenticated
  using (owner = auth.uid()) with check (owner = auth.uid());
create policy fields_owner on public.fields for all to authenticated
  using (owner = auth.uid()) with check (owner = auth.uid());
create policy messages_owner on public.messages for all to authenticated
  using (exists (select 1 from public.conversations c where c.id = conversation_id and c.owner = auth.uid()))
  with check (exists (select 1 from public.conversations c where c.id = conversation_id and c.owner = auth.uid()));

revoke all on public.conversations, public.messages, public.fields from anon;
revoke all on public.usage from anon, authenticated;
