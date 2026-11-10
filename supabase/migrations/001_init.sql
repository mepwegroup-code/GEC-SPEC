-- Execute in the Supabase SQL editor. All files live in a private bucket.
create extension if not exists pgcrypto;
create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  name text not null check(length(name) between 2 and 150),
  created_at timestamptz not null default now()
);
create table if not exists public.luminaires (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  created_by uuid not null references auth.users(id),
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists projects_owner_idx on public.projects(owner_id);
create index if not exists luminaires_project_idx on public.luminaires(project_id);
alter table public.projects enable row level security;
alter table public.luminaires enable row level security;
create policy "projects_owner_all" on public.projects for all to authenticated using (owner_id=auth.uid()) with check (owner_id=auth.uid());
create policy "records_project_owner_select" on public.luminaires for select to authenticated using (exists(select 1 from public.projects p where p.id=project_id and p.owner_id=auth.uid()));
create policy "records_project_owner_insert" on public.luminaires for insert to authenticated with check (created_by=auth.uid() and exists(select 1 from public.projects p where p.id=project_id and p.owner_id=auth.uid()));
create policy "records_project_owner_update" on public.luminaires for update to authenticated using (exists(select 1 from public.projects p where p.id=project_id and p.owner_id=auth.uid())) with check (exists(select 1 from public.projects p where p.id=project_id and p.owner_id=auth.uid()));
create policy "records_project_owner_delete" on public.luminaires for delete to authenticated using (exists(select 1 from public.projects p where p.id=project_id and p.owner_id=auth.uid()));
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values ('project-files','project-files',false,36700160,array['application/pdf','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','application/vnd.openxmlformats-officedocument.presentationml.presentation','image/png'])
on conflict (id) do update set public=false, file_size_limit=36700160, allowed_mime_types=excluded.allowed_mime_types;
-- Path is <auth-user-uuid>/<project-uuid>/<filename>. Guard both folders.
create policy "users_upload_to_own_projects" on storage.objects for insert to authenticated
with check(bucket_id='project-files' and (storage.foldername(name))[1]=auth.uid()::text
 and exists(select 1 from public.projects p where p.id::text=(storage.foldername(name))[2] and p.owner_id=auth.uid()));
create policy "users_read_own_project_files" on storage.objects for select to authenticated
using (bucket_id='project-files' and (storage.foldername(name))[1]=auth.uid()::text
 and exists(select 1 from public.projects p where p.id::text=(storage.foldername(name))[2] and p.owner_id=auth.uid()));
