-- Run this entire file in Supabase SQL Editor (Dashboard → SQL Editor → New query)

-- Profiles table (one row per user)
create table public.profiles (
  id uuid references auth.users on delete cascade primary key,
  stripe_customer_id text unique,
  subscription_status text not null default 'free',
  subscription_id text,
  current_period_end timestamptz,
  created_at timestamptz default now()
);

-- Monthly usage tracking
create table public.usage (
  id bigserial primary key,
  user_id uuid references auth.users on delete cascade not null,
  month text not null,
  analyses_count int not null default 0,
  constraint usage_user_month_unique unique(user_id, month)
);

-- Profiles already analyzed this month (re-analysis of the same profile is free)
create table if not exists public.analyzed_profiles (
  user_id uuid references auth.users on delete cascade not null,
  username text not null,
  month text not null,
  created_at timestamptz default now(),
  primary key (user_id, username, month)
);

alter table public.analyzed_profiles enable row level security;

-- Waitlist for Chrome Web Store launch
create table if not exists public.waitlist (
  email text primary key,
  created_at timestamptz default now()
);

alter table public.waitlist enable row level security;

-- Auto-create profile row when a new user signs up
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id)
  values (new.id)
  on conflict (id) do nothing;
  return new;
end;
$$;

create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Atomic usage increment (avoids race conditions)
create or replace function public.increment_usage(p_user_id uuid, p_month text)
returns int
language plpgsql
security definer
as $$
declare
  new_count int;
begin
  insert into public.usage (user_id, month, analyses_count)
  values (p_user_id, p_month, 1)
  on conflict (user_id, month)
  do update set analyses_count = public.usage.analyses_count + 1
  returning analyses_count into new_count;
  return new_count;
end;
$$;

-- Row Level Security (users can only read their own data)
alter table public.profiles enable row level security;
alter table public.usage enable row level security;

create policy "Users can view own profile"
  on public.profiles for select
  using (auth.uid() = id);

create policy "Users can view own usage"
  on public.usage for select
  using (auth.uid() = user_id);
