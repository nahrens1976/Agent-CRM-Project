-- Apply this schema to initialize an Orbit CRM database.
-- The production project is seeded through the Supabase management integration.
create table public.contacts (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text not null unique,
  company text,
  title text,
  status text not null default 'lead' check (status in ('lead','active','customer','inactive')),
  created_at timestamptz not null default now()
);

create table public.deals (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid not null references public.contacts(id) on delete cascade,
  name text not null,
  value numeric(12,2) not null default 0 check (value >= 0),
  stage text not null default 'lead' check (stage in ('lead','qualified','proposal','negotiation','won','lost')),
  expected_close date,
  updated_at timestamptz not null default now()
);

create table public.activities (
  id uuid primary key default gen_random_uuid(),
  contact_id uuid not null references public.contacts(id) on delete cascade,
  activity_type text not null check (activity_type in ('call','email','meeting','note')),
  subject text not null,
  occurred_at timestamptz not null default now()
);

create index deals_contact_id_idx on public.deals(contact_id);
create index deals_stage_idx on public.deals(stage);
create index activities_contact_occurred_idx on public.activities(contact_id, occurred_at desc);

alter table public.contacts enable row level security;
alter table public.deals enable row level security;
alter table public.activities enable row level security;
revoke all on public.contacts, public.deals, public.activities from anon, authenticated;
create policy "No direct client access to contacts" on public.contacts for all to anon, authenticated using (false) with check (false);
create policy "No direct client access to deals" on public.deals for all to anon, authenticated using (false) with check (false);
create policy "No direct client access to activities" on public.activities for all to anon, authenticated using (false) with check (false);

create table public.follow_up_drafts (
  id uuid primary key default gen_random_uuid(), contact_id uuid not null references public.contacts(id) on delete cascade,
  deal_id uuid not null references public.deals(id) on delete cascade, rationale text not null,
  subject text not null, body text not null, suggested_next_action text not null,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  created_at timestamptz not null default now(), reviewed_at timestamptz
);
create table public.agent_runs (
  id uuid primary key default gen_random_uuid(), status text not null check (status in ('completed','failed')),
  draft_count integer not null default 0, error text, created_at timestamptz not null default now()
);
alter table public.follow_up_drafts enable row level security;
alter table public.agent_runs enable row level security;
revoke all on public.follow_up_drafts, public.agent_runs from anon, authenticated;
create policy "No direct client access to drafts" on public.follow_up_drafts for all to anon, authenticated using (false) with check (false);
create policy "No direct client access to agent runs" on public.agent_runs for all to anon, authenticated using (false) with check (false);

