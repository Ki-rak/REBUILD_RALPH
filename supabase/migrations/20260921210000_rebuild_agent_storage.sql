begin;

create table if not exists public.rb_entities (
    owner_id uuid not null default auth.uid(),
    id text not null,
    kind text not null check (kind ~ '^[a-z][a-z0-9_-]{0,63}$'),
    project_id text,
    payload jsonb not null default '{}'::jsonb check (jsonb_typeof(payload) = 'object'),
    version bigint not null default 1 check (version > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (owner_id, id)
);

create index if not exists rb_entities_owner_kind_idx
    on public.rb_entities (owner_id, kind, updated_at desc);
create index if not exists rb_entities_owner_project_idx
    on public.rb_entities (owner_id, project_id, kind)
    where project_id is not null;

create or replace function public.rb_entities_guard_update()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
    old_status text := coalesce(old.payload ->> 'status', old.payload ->> 'approval_status');
    new_status text := coalesce(new.payload ->> 'status', new.payload ->> 'approval_status');
    old_history_length integer := case
        when jsonb_typeof(old.payload -> 'approval_history') = 'array'
        then jsonb_array_length(old.payload -> 'approval_history')
        else 0
    end;
    new_history_length integer := case
        when jsonb_typeof(new.payload -> 'approval_history') = 'array'
        then jsonb_array_length(new.payload -> 'approval_history')
        else 0
    end;
    invalidating_approval boolean;
begin
    invalidating_approval :=
        old_status = 'approved'
        and new_status = 'draft'
        and new_history_length > old_history_length;

    if new.owner_id is distinct from old.owner_id
       or new.id is distinct from old.id
       or new.kind is distinct from old.kind
       or new.project_id is distinct from old.project_id
       or new.created_at is distinct from old.created_at then
        raise exception 'entity identity and ownership fields are immutable' using errcode = '23514';
    end if;

    if new.version <> old.version + 1 then
        raise exception 'entity version must increment by one' using errcode = '40001';
    end if;

    if nullif(old.payload ->> 'sha256', '') is not null
       and new.payload ->> 'sha256' is distinct from old.payload ->> 'sha256' then
        raise exception 'source hash is immutable' using errcode = '23514';
    end if;

    if old.kind in ('approval', 'template') and new.payload is distinct from old.payload then
        raise exception 'approval snapshot and template version are immutable' using errcode = '23514';
    end if;

    if nullif(old.payload ->> 'approval_fingerprint', '') is not null
       and new.payload ->> 'approval_fingerprint'
           is distinct from old.payload ->> 'approval_fingerprint'
       and not invalidating_approval then
        raise exception 'approval fingerprint is immutable' using errcode = '23514';
    end if;

    if old_status = 'approved'
       and new.payload is distinct from old.payload
       and not invalidating_approval then
        raise exception 'approved content must be invalidated with appended approval history'
            using errcode = '23514';
    end if;

    new.updated_at := now();
    return new;
end;
$$;

drop trigger if exists rb_entities_guard_update on public.rb_entities;
create trigger rb_entities_guard_update
before update on public.rb_entities
for each row execute function public.rb_entities_guard_update();

alter table public.rb_entities enable row level security;

revoke all on table public.rb_entities from anon;
grant select, insert, update on table public.rb_entities to authenticated;

drop policy if exists rb_entities_select_own on public.rb_entities;
create policy rb_entities_select_own
on public.rb_entities for select
to authenticated
using ((select auth.uid()) = owner_id);

drop policy if exists rb_entities_insert_own on public.rb_entities;
create policy rb_entities_insert_own
on public.rb_entities for insert
to authenticated
with check ((select auth.uid()) = owner_id);

drop policy if exists rb_entities_update_own on public.rb_entities;
create policy rb_entities_update_own
on public.rb_entities for update
to authenticated
using ((select auth.uid()) = owner_id)
with check ((select auth.uid()) = owner_id);


insert into storage.buckets (id, name, public)
values ('rebuild-agent', 'rebuild-agent', false)
on conflict (id) do update set public = false;

drop policy if exists rb_storage_select_own on storage.objects;
create policy rb_storage_select_own
on storage.objects for select
to authenticated
using (
    bucket_id = 'rebuild-agent'
    and (storage.foldername(name))[1] = (select auth.uid())::text
);

drop policy if exists rb_storage_insert_own on storage.objects;
create policy rb_storage_insert_own
on storage.objects for insert
to authenticated
with check (
    bucket_id = 'rebuild-agent'
    and (storage.foldername(name))[1] = (select auth.uid())::text
);

drop policy if exists rb_storage_update_own on storage.objects;




-- Atomic approval: both records are written or neither is. Caller remains subject to RLS.
create or replace function public.rb_approve_draft(
    draft_id text, expected_version bigint, draft_payload jsonb,
    approval_id text, approval_payload jsonb
)
returns setof public.rb_entities
language plpgsql
security invoker
set search_path = ''
as $$
declare
    current_row public.rb_entities;
begin
    select * into current_row from public.rb_entities e
    where e.owner_id = auth.uid() and e.id = draft_id and e.kind = 'draft'
    for update;
    if not found or current_row.version <> expected_version then
        raise exception 'draft version conflict' using errcode = '40001';
    end if;
    if draft_payload ->> 'status' <> 'approved'
       or draft_payload ->> 'approval_id' <> approval_id
       or approval_payload ->> 'draft_id' <> draft_id then
        raise exception 'invalid approval envelope' using errcode = '23514';
    end if;
    insert into public.rb_entities (id,kind,project_id,payload)
    values (approval_id,'approval',current_row.project_id,approval_payload);
    return query update public.rb_entities e
        set payload = draft_payload, version = e.version + 1
        where e.owner_id = auth.uid() and e.id = draft_id
        returning e.*;
end;
$$;
revoke all on function public.rb_approve_draft(text,bigint,jsonb,text,jsonb) from public,anon;
grant execute on function public.rb_approve_draft(text,bigint,jsonb,text,jsonb) to authenticated;

commit;