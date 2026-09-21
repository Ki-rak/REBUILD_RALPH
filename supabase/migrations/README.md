# RE:Build Agent Supabase migration

Apply 20260921210000_rebuild_agent_storage.sql to the configured Supabase
project. It adds only public.rb_entities, the public.rb_entities_guard_update
function, rb_ policies, and the private rebuild-agent bucket. Re-running it is
safe and does not delete rows or objects.

The migration keeps source sha256 and approval fingerprints immutable after
they are set. An approved payload cannot be edited in place. Create a new entity
revision when source inputs change. Every update must increase version by one,
while the product client filters updates by the previous version.

## Manual rollback

Rollback is intentionally not an automatically applied migration. Export any
required rows and bucket objects first, then run the following in the Supabase
SQL editor:

    begin;
    drop policy if exists rb_storage_update_own on storage.objects;
    drop policy if exists rb_storage_insert_own on storage.objects;
    drop policy if exists rb_storage_select_own on storage.objects;
    drop policy if exists rb_entities_update_own on public.rb_entities;
    drop policy if exists rb_entities_insert_own on public.rb_entities;
    drop policy if exists rb_entities_select_own on public.rb_entities;
    drop table if exists public.rb_entities;
    drop function if exists public.rb_entities_guard_update();
    -- Only remove the bucket after confirming it has no objects:
    -- delete from storage.buckets where id = 'rebuild-agent';
    commit;

The commented bucket deletion prevents accidental loss of uploaded originals.