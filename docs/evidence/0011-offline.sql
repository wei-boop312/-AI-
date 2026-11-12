BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE SCHEMA app;
CREATE SCHEMA auth;
CREATE SCHEMA ops;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE ROLE app_api NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE app_auth NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE app_worker NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE ops_dispatcher NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE ops_admin NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE app_readonly NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE TABLE app.users (
 id uuid PRIMARY KEY, email_normalized text NOT NULL UNIQUE,
 display_name text NOT NULL, status text NOT NULL CHECK(status IN ('active','disabled')),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE auth.credentials (
 user_id uuid PRIMARY KEY REFERENCES app.users(id) ON DELETE RESTRICT,
 password_hash text NOT NULL, password_version integer NOT NULL DEFAULT 1,
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE auth.refresh_sessions (
 id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES app.users(id) ON DELETE RESTRICT,
 family_id uuid NOT NULL, token_digest text NOT NULL UNIQUE, expires_at timestamptz NOT NULL,
 revoked_at timestamptz, replaced_by uuid REFERENCES auth.refresh_sessions(id),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app.products (
 id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES app.users(id) ON DELETE RESTRICT,
 name text NOT NULL CHECK(length(name) BETWEEN 1 AND 255), category text NOT NULL,
 revision bigint NOT NULL DEFAULT 1 CHECK(revision>0), archived_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(user_id,id)
);
CREATE TABLE app.appearance_profiles (
 id uuid PRIMARY KEY, user_id uuid NOT NULL, product_id uuid NOT NULL,
 name text NOT NULL, config jsonb NOT NULL CHECK(jsonb_typeof(config)='object'),
 revision bigint NOT NULL DEFAULT 1 CHECK(revision>0), archived_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(user_id,id), UNIQUE(user_id,product_id,id),
 FOREIGN KEY(user_id,product_id) REFERENCES app.products(user_id,id) ON DELETE RESTRICT
);
CREATE TABLE app.assets (
 id uuid PRIMARY KEY, user_id uuid NOT NULL, product_id uuid NOT NULL,
 kind text NOT NULL CHECK(kind IN ('original','generated','final','preview')),
 status text NOT NULL CHECK(status IN ('uploading','validating','ready','rejected')),
 current_version_id uuid, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(user_id,id), UNIQUE(user_id,product_id,id),
 FOREIGN KEY(user_id,product_id) REFERENCES app.products(user_id,id) ON DELETE RESTRICT,
 CHECK(status<>'ready' OR current_version_id IS NOT NULL)
);
CREATE TABLE app.asset_versions (
 id uuid PRIMARY KEY, user_id uuid NOT NULL, product_id uuid NOT NULL, asset_id uuid NOT NULL,
 version_number integer NOT NULL CHECK(version_number>0), bucket text NOT NULL, object_key text NOT NULL,
 storage_version_id text, sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'), mime text NOT NULL,
 width integer NOT NULL CHECK(width>0), height integer NOT NULL CHECK(height>0), byte_size bigint NOT NULL CHECK(byte_size>0),
 color_space text NOT NULL, canonical boolean NOT NULL, source_version_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(user_id,id), UNIQUE(user_id,product_id,id), UNIQUE(user_id,product_id,asset_id,id),
 UNIQUE(asset_id,version_number), UNIQUE(bucket,object_key),
 FOREIGN KEY(user_id,product_id,asset_id) REFERENCES app.assets(user_id,product_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(user_id,product_id,source_version_id) REFERENCES app.asset_versions(user_id,product_id,id) ON DELETE RESTRICT
);
ALTER TABLE app.assets ADD CONSTRAINT current_version_owned FOREIGN KEY(user_id,product_id,id,current_version_id)
 REFERENCES app.asset_versions(user_id,product_id,asset_id,id) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE app.wallets (
 user_id uuid PRIMARY KEY REFERENCES app.users(id) ON DELETE RESTRICT,
 available bigint NOT NULL DEFAULT 0 CHECK(available>=0), reserved bigint NOT NULL DEFAULT 0 CHECK(reserved>=0),
 funded_total bigint NOT NULL DEFAULT 0 CHECK(funded_total>=0), spent_total bigint NOT NULL DEFAULT 0 CHECK(spent_total>=0),
 revision bigint NOT NULL DEFAULT 1 CHECK(revision>0), updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK(available+reserved=funded_total-spent_total)
);
ALTER TABLE app.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.products FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.products USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)
 WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.appearance_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.appearance_profiles FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.appearance_profiles USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)
 WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.assets FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.assets USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)
 WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.asset_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.asset_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.asset_versions USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)
 WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.wallets ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.wallets FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.wallets USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)
 WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.users FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.users USING(id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY auth_identity ON app.users TO app_auth USING(true);
GRANT USAGE ON SCHEMA app TO app_api,app_worker,app_auth,app_readonly;
GRANT USAGE ON SCHEMA auth TO app_auth;
GRANT SELECT(id,email_normalized,display_name,status) ON app.users TO app_api,app_auth;
GRANT SELECT,INSERT,UPDATE ON app.products,app.appearance_profiles TO app_api;
GRANT SELECT ON app.assets,app.asset_versions,app.wallets TO app_api;
GRANT SELECT,INSERT,UPDATE ON auth.credentials,auth.refresh_sessions TO app_auth;
ALTER TABLE auth.credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth.credentials FORCE ROW LEVEL SECURITY;
CREATE POLICY authentication ON auth.credentials TO app_auth USING(true) WITH CHECK(true);
ALTER TABLE auth.refresh_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth.refresh_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY authentication ON auth.refresh_sessions TO app_auth USING(true) WITH CHECK(true);;

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Running upgrade 0001 -> 0002

CREATE TABLE app.quotes (
 id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES app.users(id), operation text NOT NULL DEFAULT 'generate',
 input_hash text NOT NULL CHECK(input_hash ~ '^[0-9a-f]{64}$'), input_snapshot jsonb NOT NULL,
 input_sha256 text NOT NULL CHECK(input_sha256 ~ '^[0-9a-f]{64}$'), price_version text NOT NULL, provider_model text NOT NULL, rules_snapshot jsonb NOT NULL,
 credits bigint NOT NULL CHECK(credits>0), expires_at timestamptz NOT NULL, consumed_task_id uuid UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(user_id,id)
);
CREATE TABLE app.generation_tasks (
 id uuid PRIMARY KEY, user_id uuid NOT NULL, product_id uuid NOT NULL, appearance_profile_id uuid,
 source_asset_version_id uuid NOT NULL, operation text NOT NULL DEFAULT 'generate',
 idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 200), request_hash text NOT NULL,
 quote_id uuid NOT NULL UNIQUE, status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','processing','succeeded','failed','cancelled','uncertain')),
 phase text NOT NULL DEFAULT 'queued' CHECK(phase IN ('queued','submitting','polling','archiving','protecting','detecting','validating_rules','finalizing')),
 credits_status text NOT NULL DEFAULT 'frozen' CHECK(credits_status IN ('frozen','charged','refunded')),
 reserved_credits bigint NOT NULL CHECK(reserved_credits>0), input_snapshot jsonb NOT NULL, input_sha256 text NOT NULL,
 final_version_id uuid, compliance_id uuid, cancel_requested_at timestamptz, lease_owner text, lease_until timestamptz,
 fencing_token bigint NOT NULL DEFAULT 0, revision bigint NOT NULL DEFAULT 1 CHECK(revision>0), error_code text,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 UNIQUE(user_id,id), UNIQUE(user_id,product_id,id), UNIQUE(user_id,operation,idempotency_key),
 FOREIGN KEY(user_id,product_id) REFERENCES app.products(user_id,id),
 FOREIGN KEY(user_id,product_id,appearance_profile_id) REFERENCES app.appearance_profiles(user_id,product_id,id),
 FOREIGN KEY(user_id,product_id,source_asset_version_id) REFERENCES app.asset_versions(user_id,product_id,id),
 FOREIGN KEY(user_id,product_id,final_version_id) REFERENCES app.asset_versions(user_id,product_id,id),
 FOREIGN KEY(user_id,quote_id) REFERENCES app.quotes(user_id,id),
 CHECK(status<>'succeeded' OR (final_version_id IS NOT NULL AND compliance_id IS NOT NULL AND completed_at IS NOT NULL AND credits_status='charged')),
 CHECK(status NOT IN ('failed','cancelled') OR (completed_at IS NOT NULL AND credits_status='refunded'))
);
ALTER TABLE app.quotes ADD CONSTRAINT consumed_task_owned FOREIGN KEY(user_id,consumed_task_id) REFERENCES app.generation_tasks(user_id,id);
CREATE TABLE app.credit_transactions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES app.wallets(user_id), task_id uuid,
 operation_id uuid NOT NULL UNIQUE, type text NOT NULL CHECK(type IN ('grant','freeze','charge','refund')),
 amount bigint NOT NULL CHECK(amount>0), available_delta bigint NOT NULL, reserved_delta bigint NOT NULL,
 funded_delta bigint NOT NULL, spent_delta bigint NOT NULL,
 available_after bigint NOT NULL CHECK(available_after>=0), reserved_after bigint NOT NULL CHECK(reserved_after>=0),
 actor_ref text NOT NULL, reason text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(user_id,task_id) REFERENCES app.generation_tasks(user_id,id),
 CHECK((type='grant' AND task_id IS NULL AND available_delta=amount AND reserved_delta=0 AND funded_delta=amount AND spent_delta=0)
 OR (type='freeze' AND task_id IS NOT NULL AND available_delta=-amount AND reserved_delta=amount AND funded_delta=0 AND spent_delta=0)
 OR (type='charge' AND task_id IS NOT NULL AND available_delta=0 AND reserved_delta=-amount AND funded_delta=0 AND spent_delta=amount)
 OR (type='refund' AND task_id IS NOT NULL AND available_delta=amount AND reserved_delta=-amount AND funded_delta=0 AND spent_delta=0))
);
CREATE UNIQUE INDEX credit_once_per_task_type ON app.credit_transactions(task_id,type) WHERE task_id IS NOT NULL;
CREATE UNIQUE INDEX one_terminal_credit ON app.credit_transactions(task_id) WHERE type IN ('charge','refund');
CREATE TABLE app.task_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id uuid NOT NULL, task_id uuid NOT NULL,
 type text NOT NULL, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(user_id,task_id) REFERENCES app.generation_tasks(user_id,id)
);
CREATE INDEX event_cursor ON app.task_events(user_id,task_id,id);
CREATE TABLE ops.outbox (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, task_id uuid NOT NULL, event_type text NOT NULL,
 dedupe_key text NOT NULL UNIQUE, created_at timestamptz NOT NULL DEFAULT now(), publish_attempts integer NOT NULL DEFAULT 0,
 next_attempt_at timestamptz NOT NULL DEFAULT now(), locked_until timestamptz, published_at timestamptz,
 FOREIGN KEY(user_id,task_id) REFERENCES app.generation_tasks(user_id,id)
);
CREATE INDEX outbox_pending ON ops.outbox(next_attempt_at) WHERE published_at IS NULL;
CREATE TABLE ops.task_dispatch (
 task_id uuid PRIMARY KEY, user_id uuid NOT NULL, ready_at timestamptz NOT NULL DEFAULT now(),
 lease_until timestamptz, fencing_token bigint NOT NULL DEFAULT 0, state text NOT NULL DEFAULT 'queued',
 FOREIGN KEY(user_id,task_id) REFERENCES app.generation_tasks(user_id,id)
);
CREATE TABLE ops.audit_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), actor text NOT NULL, action text NOT NULL, target_type text NOT NULL,
 target_id uuid NOT NULL, reason text NOT NULL, evidence_digest text, before_state jsonb, after_state jsonb,
 request_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app.provider_attempts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, task_id uuid NOT NULL,
 step text NOT NULL CHECK(step IN ('generate','detect')), attempt_number integer NOT NULL DEFAULT 1 CHECK(attempt_number=1),
 provider text NOT NULL, model text NOT NULL, status text NOT NULL CHECK(status IN ('intent_recorded','submitted','polling','succeeded','failed','uncertain')),
 intent_at timestamptz NOT NULL DEFAULT now(), request_hash text NOT NULL, local_request_id uuid NOT NULL,
 provider_id text, polling_url_private text, response_digest text, error_code text,
 submitted_at timestamptz, last_polled_at timestamptz, finished_at timestamptz,
 UNIQUE(task_id,step), UNIQUE(user_id,id), FOREIGN KEY(user_id,task_id) REFERENCES app.generation_tasks(user_id,id)
);
CREATE FUNCTION app.reject_mutation() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN RAISE EXCEPTION 'immutable_record' USING ERRCODE='55000'; END $$;
CREATE TRIGGER immutable_ledger BEFORE UPDATE OR DELETE ON app.credit_transactions FOR EACH ROW EXECUTE FUNCTION app.reject_mutation();
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON ops.audit_events FOR EACH ROW EXECUTE FUNCTION app.reject_mutation();
ALTER TABLE app.quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.quotes FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.quotes USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.generation_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.generation_tasks FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.generation_tasks USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.credit_transactions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.credit_transactions USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.task_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.task_events FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.task_events USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.provider_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.provider_attempts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.provider_attempts USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE ops.outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE ops.outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY internal_dispatch ON ops.outbox TO ops_dispatcher USING(true) WITH CHECK(true);
ALTER TABLE ops.task_dispatch ENABLE ROW LEVEL SECURITY;
ALTER TABLE ops.task_dispatch FORCE ROW LEVEL SECURITY;
CREATE POLICY internal_dispatch ON ops.task_dispatch TO ops_dispatcher USING(true) WITH CHECK(true);
ALTER TABLE ops.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ops.audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY internal_dispatch ON ops.audit_events TO ops_dispatcher USING(true) WITH CHECK(true);
GRANT SELECT ON app.quotes,app.generation_tasks,app.credit_transactions,app.task_events TO app_api;
GRANT USAGE ON SCHEMA ops TO ops_dispatcher,ops_admin;
GRANT SELECT,UPDATE ON ops.outbox,ops.task_dispatch TO ops_dispatcher;
REVOKE ALL ON FUNCTION app.reject_mutation() FROM PUBLIC;;

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

-- Running upgrade 0002 -> 0003

CREATE ROLE app_executor NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT USAGE ON SCHEMA app,ops TO app_executor;
GRANT SELECT ON app.users,app.products,app.appearance_profiles,app.assets,app.asset_versions TO app_executor;
GRANT SELECT,INSERT,UPDATE ON app.wallets,app.quotes,app.generation_tasks TO app_executor;
GRANT SELECT,INSERT ON app.credit_transactions,app.task_events,ops.outbox,ops.task_dispatch,ops.audit_events TO app_executor;
GRANT USAGE ON SEQUENCE app.task_events_id_seq TO app_executor;
CREATE POLICY executor_outbox ON ops.outbox TO app_executor USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY executor_dispatch ON ops.task_dispatch TO app_executor USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY executor_audit ON ops.audit_events TO app_executor WITH CHECK(true);
CREATE FUNCTION app.grant_credits(p_user uuid,p_operation uuid,p_amount bigint,p_reason text) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE w app.wallets; prior app.credit_transactions;
BEGIN
 IF p_amount<=0 OR p_reason IS NULL OR length(p_reason)=0 THEN RAISE EXCEPTION 'invalid_grant'; END IF;
 PERFORM set_config('app.user_id',p_user::text,true);
 INSERT INTO app.wallets(user_id) VALUES(p_user) ON CONFLICT DO NOTHING;
 SELECT * INTO w FROM app.wallets WHERE user_id=p_user FOR UPDATE;
 SELECT * INTO prior FROM app.credit_transactions WHERE operation_id=p_operation;
 IF FOUND THEN
  IF prior.user_id<>p_user OR prior.type<>'grant' OR prior.amount<>p_amount THEN RAISE EXCEPTION 'operation_conflict'; END IF;
  RETURN;
 END IF;
 UPDATE app.wallets SET available=available+p_amount,funded_total=funded_total+p_amount,revision=revision+1,updated_at=now() WHERE user_id=p_user RETURNING * INTO w;
 INSERT INTO app.credit_transactions(user_id,operation_id,type,amount,available_delta,reserved_delta,funded_delta,spent_delta,available_after,reserved_after,actor_ref,reason)
 VALUES(p_user,p_operation,'grant',p_amount,p_amount,0,p_amount,0,w.available,w.reserved,session_user,p_reason);
 INSERT INTO ops.audit_events(actor,action,target_type,target_id,reason,request_id,after_state)
 VALUES(session_user,'grant','user',p_user,p_reason,p_operation,jsonb_build_object('amount',p_amount));
END $$;
ALTER FUNCTION app.grant_credits(uuid,uuid,bigint,text) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.grant_credits(uuid,uuid,bigint,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.grant_credits(uuid,uuid,bigint,text) TO ops_admin;
GRANT USAGE ON SCHEMA app TO ops_admin;
CREATE FUNCTION app.submit_task(p_id uuid,p_quote uuid,p_key text,p_hash text) RETURNS uuid
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE u uuid; q app.quotes; t app.generation_tasks; w app.wallets; product uuid; source uuid; appearance uuid;
BEGIN
 u:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF u IS NULL THEN RAISE EXCEPTION 'identity_required' USING ERRCODE='42501'; END IF;
 IF NOT EXISTS(SELECT 1 FROM app.users WHERE id=u AND status='active') THEN RAISE EXCEPTION 'inactive_user'; END IF;
 IF p_hash !~ '^[0-9a-f]{64}$' OR length(p_key) NOT BETWEEN 1 AND 200 THEN RAISE EXCEPTION 'invalid_request'; END IF;
 SELECT * INTO w FROM app.wallets WHERE user_id=u FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'insufficient_credits'; END IF;
 SELECT * INTO t FROM app.generation_tasks WHERE user_id=u AND operation='generate' AND idempotency_key=p_key;
 IF FOUND THEN
  IF t.request_hash<>p_hash OR t.quote_id<>p_quote THEN RAISE EXCEPTION 'idempotency_conflict'; END IF;
  RETURN t.id;
 END IF;
 SELECT * INTO q FROM app.quotes WHERE user_id=u AND id=p_quote FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'quote_not_found'; END IF;
 IF q.consumed_task_id IS NOT NULL THEN RAISE EXCEPTION 'quote_consumed'; END IF;
 IF q.expires_at<=now() THEN RAISE EXCEPTION 'quote_expired'; END IF;
 IF w.available<q.credits THEN RAISE EXCEPTION 'insufficient_credits'; END IF;
 product:=(q.input_snapshot->>'product_id')::uuid;
 source:=(q.input_snapshot->>'source_asset_version_id')::uuid;
 appearance:=(q.input_snapshot->>'appearance_profile_id')::uuid;
 PERFORM 1 FROM app.products WHERE user_id=u AND id=product AND archived_at IS NULL FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'product_unavailable'; END IF;
 IF NOT EXISTS(SELECT 1 FROM app.asset_versions v JOIN app.assets a ON a.id=v.asset_id AND a.user_id=v.user_id
   WHERE v.id=source AND v.user_id=u AND v.product_id=product AND v.canonical AND a.status='ready') THEN RAISE EXCEPTION 'source_unavailable'; END IF;
 IF appearance IS NOT NULL AND NOT EXISTS(SELECT 1 FROM app.appearance_profiles WHERE id=appearance AND user_id=u AND product_id=product AND archived_at IS NULL) THEN RAISE EXCEPTION 'appearance_unavailable'; END IF;
 INSERT INTO app.generation_tasks(id,user_id,product_id,appearance_profile_id,source_asset_version_id,idempotency_key,request_hash,quote_id,reserved_credits,input_snapshot,input_sha256)
 VALUES(p_id,u,product,appearance,source,p_key,p_hash,q.id,q.credits,q.input_snapshot,q.input_sha256);
 UPDATE app.wallets SET available=available-q.credits,reserved=reserved+q.credits,revision=revision+1,updated_at=now() WHERE user_id=u RETURNING * INTO w;
 INSERT INTO app.credit_transactions(user_id,task_id,operation_id,type,amount,available_delta,reserved_delta,funded_delta,spent_delta,available_after,reserved_after,actor_ref,reason)
 VALUES(u,p_id,gen_random_uuid(),'freeze',q.credits,-q.credits,q.credits,0,0,w.available,w.reserved,'system','task_created');
 UPDATE app.quotes SET consumed_task_id=p_id WHERE id=q.id;
 INSERT INTO ops.outbox(user_id,task_id,event_type,dedupe_key) VALUES(u,p_id,'task.queued',p_id::text||':queued');
 INSERT INTO ops.task_dispatch(user_id,task_id) VALUES(u,p_id);
 INSERT INTO app.task_events(user_id,task_id,type,payload) VALUES(u,p_id,'task.updated',jsonb_build_object('status','queued','revision',1));
 RETURN p_id;
END $$;
ALTER FUNCTION app.submit_task(uuid,uuid,text,text) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.submit_task(uuid,uuid,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.submit_task(uuid,uuid,text,text) TO app_api;

GRANT SELECT ON app.provider_attempts TO app_executor;
CREATE FUNCTION app.cancel_task(p_task uuid) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE u uuid; w app.wallets; t app.generation_tasks;
BEGIN
 u:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF u IS NULL THEN RAISE EXCEPTION 'identity_required' USING ERRCODE='42501'; END IF;
 SELECT * INTO w FROM app.wallets WHERE user_id=u FOR UPDATE;
 SELECT * INTO t FROM app.generation_tasks WHERE id=p_task AND user_id=u FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'task_not_found'; END IF;
 IF t.status='cancelled' THEN RETURN; END IF;
 IF t.status<>'queued' OR EXISTS(SELECT 1 FROM app.provider_attempts WHERE task_id=t.id AND step='generate') THEN RAISE EXCEPTION 'already_started'; END IF;
 UPDATE app.wallets SET available=available+t.reserved_credits,reserved=reserved-t.reserved_credits,revision=revision+1,updated_at=now() WHERE user_id=u RETURNING * INTO w;
 INSERT INTO app.credit_transactions(user_id,task_id,operation_id,type,amount,available_delta,reserved_delta,funded_delta,spent_delta,available_after,reserved_after,actor_ref,reason)
 VALUES(u,t.id,gen_random_uuid(),'refund',t.reserved_credits,t.reserved_credits,-t.reserved_credits,0,0,w.available,w.reserved,'system','cancelled');
 UPDATE app.generation_tasks SET status='cancelled',credits_status='refunded',completed_at=now(),updated_at=now(),revision=revision+1 WHERE id=t.id;
 INSERT INTO app.task_events(user_id,task_id,type,payload) VALUES(u,t.id,'task.updated',jsonb_build_object('status','cancelled','revision',t.revision+1));
END $$;
ALTER FUNCTION app.cancel_task(uuid) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.cancel_task(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.cancel_task(uuid) TO app_api;;

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0002';

-- Running upgrade 0003 -> 0004

GRANT UPDATE(archived_at) ON app.products TO app_executor;;

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0003';

-- Running upgrade 0004 -> 0005

CREATE TABLE auth.session_families (
 id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES app.users(id), csrf_digest text NOT NULL,
 expires_at timestamptz NOT NULL, revoked_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE auth.refresh_sessions ADD CONSTRAINT refresh_family FOREIGN KEY(family_id) REFERENCES auth.session_families(id);
CREATE INDEX refresh_family_idx ON auth.refresh_sessions(family_id);
CREATE TABLE auth.login_limits (
 bucket text PRIMARY KEY, window_start timestamptz NOT NULL DEFAULT now(), attempts integer NOT NULL CHECK(attempts>0)
);
ALTER TABLE auth.session_families ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth.session_families FORCE ROW LEVEL SECURITY;
ALTER TABLE auth.login_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth.login_limits FORCE ROW LEVEL SECURITY;
CREATE POLICY authentication ON auth.session_families TO app_auth USING(true) WITH CHECK(true);
CREATE POLICY authentication ON auth.login_limits TO app_auth USING(true) WITH CHECK(true);
GRANT SELECT,INSERT,UPDATE ON auth.session_families,auth.login_limits TO app_auth;;

UPDATE alembic_version SET version_num='0005' WHERE alembic_version.version_num = '0004';

-- Running upgrade 0005 -> 0006

CREATE ROLE app_provisioner NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT USAGE ON SCHEMA app,auth TO app_provisioner;
GRANT INSERT(id,email_normalized,display_name,status) ON app.users TO app_provisioner;
GRANT INSERT(user_id,password_hash) ON auth.credentials TO app_provisioner;
CREATE POLICY private_provision ON app.users FOR INSERT TO app_provisioner WITH CHECK(true);
CREATE POLICY private_provision ON auth.credentials FOR INSERT TO app_provisioner WITH CHECK(true);
CREATE FUNCTION app.create_private_user(p_id uuid,p_email text,p_name text,p_password_hash text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF p_email IS NULL OR length(p_email) NOT BETWEEN 3 AND 320 OR p_email<>lower(trim(p_email))
 OR p_name IS NULL OR length(p_name) NOT BETWEEN 1 AND 255 OR p_password_hash NOT LIKE '$argon2id$%%' THEN RAISE EXCEPTION 'invalid_private_account'; END IF;
 INSERT INTO app.users(id,email_normalized,display_name,status) VALUES(p_id,p_email,p_name,'active');
 INSERT INTO auth.credentials(user_id,password_hash) VALUES(p_id,p_password_hash);
 RETURN p_id;
END $$;
ALTER FUNCTION app.create_private_user(uuid,text,text,text) OWNER TO app_provisioner;
REVOKE ALL ON FUNCTION app.create_private_user(uuid,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.create_private_user(uuid,text,text,text) TO ops_admin;;

UPDATE alembic_version SET version_num='0006' WHERE alembic_version.version_num = '0005';

-- Running upgrade 0006 -> 0007

CREATE TABLE app.platform_rules (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), platform text NOT NULL, marketplace text NOT NULL, category text NOT NULL,
 image_type text NOT NULL, version text NOT NULL, evidence_status text NOT NULL CHECK(evidence_status IN ('unverified','verified')),
 source_urls jsonb NOT NULL DEFAULT '[]', retrieved_at timestamptz, config jsonb NOT NULL,
 config_sha256 text NOT NULL CHECK(config_sha256 ~ '^[0-9a-f]{64}$'), published_at timestamptz,
 UNIQUE(platform,marketplace,category,image_type,version)
);
ALTER TABLE app.platform_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.platform_rules FORCE ROW LEVEL SECURITY;
CREATE POLICY published_rules ON app.platform_rules FOR SELECT TO app_api,app_worker,app_executor,app_readonly USING(published_at IS NOT NULL);
GRANT SELECT ON app.platform_rules TO app_api,app_executor;
CREATE FUNCTION app.quote_immutable() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'immutable_quote' USING ERRCODE='55000'; END IF;
 IF (to_jsonb(NEW)-'consumed_task_id') IS DISTINCT FROM (to_jsonb(OLD)-'consumed_task_id')
 OR (OLD.consumed_task_id IS NOT NULL AND NEW.consumed_task_id IS DISTINCT FROM OLD.consumed_task_id)
 THEN RAISE EXCEPTION 'immutable_quote' USING ERRCODE='55000'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable_quote BEFORE UPDATE OR DELETE ON app.quotes FOR EACH ROW EXECUTE FUNCTION app.quote_immutable();
REVOKE ALL ON FUNCTION app.quote_immutable() FROM PUBLIC;
CREATE FUNCTION app.create_quote(p_id uuid,p_input_hash text,p_snapshot_hash text,p_snapshot jsonb,p_rules jsonb) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE u uuid; product uuid; source uuid; appearance uuid; v app.asset_versions;
BEGIN
 u:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF u IS NULL THEN RAISE EXCEPTION 'identity_required' USING ERRCODE='42501'; END IF;
 IF NOT EXISTS(SELECT 1 FROM app.users WHERE id=u AND status='active') THEN RAISE EXCEPTION 'inactive_user'; END IF;
 IF p_input_hash !~ '^[0-9a-f]{64}$' OR p_snapshot_hash !~ '^[0-9a-f]{64}$' OR jsonb_typeof(p_snapshot)<>'object' THEN RAISE EXCEPTION 'invalid_quote'; END IF;
 product:=(p_snapshot->>'product_id')::uuid;
 source:=(p_snapshot->>'source_asset_version_id')::uuid;
 appearance:=(p_snapshot->>'appearance_profile_id')::uuid;
 PERFORM 1 FROM app.products WHERE user_id=u AND id=product AND archived_at IS NULL FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'product_unavailable'; END IF;
 SELECT av.* INTO v FROM app.asset_versions av JOIN app.assets a ON a.user_id=av.user_id AND a.id=av.asset_id
 WHERE av.user_id=u AND av.product_id=product AND av.id=source AND av.canonical AND a.status='ready';
 IF NOT FOUND THEN RAISE EXCEPTION 'source_unavailable'; END IF;
 IF p_snapshot->'_execution'->>'source_sha256' IS DISTINCT FROM v.sha256 THEN RAISE EXCEPTION 'source_hash_mismatch'; END IF;
 IF appearance IS NOT NULL AND NOT EXISTS(SELECT 1 FROM app.appearance_profiles WHERE user_id=u AND product_id=product AND id=appearance AND archived_at IS NULL) THEN RAISE EXCEPTION 'appearance_unavailable'; END IF;
 INSERT INTO app.quotes(id,user_id,input_hash,input_sha256,input_snapshot,price_version,provider_model,rules_snapshot,credits,expires_at)
 VALUES(p_id,u,p_input_hash,p_snapshot_hash,p_snapshot,'trial-fake-v1','fake-v1',p_rules,16,now()+interval '10 minutes');
 RETURN p_id;
END $$;
ALTER FUNCTION app.create_quote(uuid,text,text,jsonb,jsonb) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.create_quote(uuid,text,text,jsonb,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.create_quote(uuid,text,text,jsonb,jsonb) TO app_api;
REVOKE EXECUTE ON FUNCTION app.submit_task(uuid,uuid,text,text) FROM app_api;
CREATE FUNCTION app.submit_quoted_task(p_id uuid,p_quote uuid,p_key text,p_hash text,p_input_hash text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE u uuid; q app.quotes;
BEGIN
 u:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF u IS NULL THEN RAISE EXCEPTION 'identity_required' USING ERRCODE='42501'; END IF;
 SELECT * INTO q FROM app.quotes WHERE user_id=u AND id=p_quote;
 IF NOT FOUND THEN RAISE EXCEPTION 'quote_not_found'; END IF;
 IF q.input_hash IS DISTINCT FROM p_input_hash THEN RAISE EXCEPTION 'quote_input_mismatch'; END IF;
 RETURN app.submit_task(p_id,p_quote,p_key,p_hash);
END $$;
ALTER FUNCTION app.submit_quoted_task(uuid,uuid,text,text,text) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.submit_quoted_task(uuid,uuid,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.submit_quoted_task(uuid,uuid,text,text,text) TO app_api;;

UPDATE alembic_version SET version_num='0007' WHERE alembic_version.version_num = '0006';

-- Running upgrade 0007 -> 0008

CREATE TABLE app.upload_intents (
 id uuid PRIMARY KEY, user_id uuid NOT NULL, product_id uuid NOT NULL, asset_id uuid NOT NULL,
 temp_key text NOT NULL UNIQUE, expected_mime text NOT NULL CHECK(expected_mime IN ('image/jpeg','image/png','image/webp')),
 expected_size bigint NOT NULL CHECK(expected_size BETWEEN 1 AND 20971520), expires_at timestamptz NOT NULL,
 status text NOT NULL CHECK(status IN ('pending','validating','ready','rejected')), completed_version_id uuid,
 original_version_id uuid, lease_owner uuid, lease_until timestamptz, error_code text, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(user_id,id), FOREIGN KEY(user_id,product_id,asset_id) REFERENCES app.assets(user_id,product_id,id),
 FOREIGN KEY(user_id,product_id,asset_id,completed_version_id) REFERENCES app.asset_versions(user_id,product_id,asset_id,id),
 FOREIGN KEY(user_id,product_id,asset_id,original_version_id) REFERENCES app.asset_versions(user_id,product_id,asset_id,id),
 CHECK(status<>'ready' OR (completed_version_id IS NOT NULL AND original_version_id IS NOT NULL))
);
ALTER TABLE app.provider_attempts ADD CONSTRAINT attempt_task_owned UNIQUE(user_id,task_id,id);
CREATE TABLE app.task_cost_records (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, task_id uuid NOT NULL, attempt_id uuid NOT NULL,
 cost_record_kind text NOT NULL CHECK(cost_record_kind IN ('estimate','settlement')), provider text NOT NULL, model text NOT NULL,
 currency text NOT NULL, amount numeric(20,8) CHECK(amount>=0), cost_status text NOT NULL CHECK(cost_status IN ('estimated','confirmed','unknown')),
 usage jsonb NOT NULL DEFAULT '{}', price_source text NOT NULL, price_version text NOT NULL, observed_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(attempt_id,cost_record_kind), FOREIGN KEY(user_id,task_id,attempt_id) REFERENCES app.provider_attempts(user_id,task_id,id),
 CHECK((cost_status='unknown' AND amount IS NULL) OR (cost_status<>'unknown' AND amount IS NOT NULL))
);
CREATE TABLE app.compliance_checks (
 id uuid PRIMARY KEY, user_id uuid NOT NULL, product_id uuid NOT NULL, task_id uuid NOT NULL,
 final_version_id uuid NOT NULL, final_sha256 text NOT NULL CHECK(final_sha256 ~ '^[0-9a-f]{64}$'), facts jsonb NOT NULL,
 facts_schema_version integer NOT NULL CHECK(facts_schema_version=1), rule_snapshots jsonb NOT NULL, per_platform_results jsonb NOT NULL,
 auto_overall text NOT NULL CHECK(auto_overall IN ('compliant','non_compliant','manual_review')),
 sampling_selected boolean NOT NULL, report_sha256 text NOT NULL CHECK(report_sha256 ~ '^[0-9a-f]{64}$'),
 report_bucket text NOT NULL, report_object_key text NOT NULL, report_storage_version_id text,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(user_id,id), UNIQUE(user_id,task_id,id),
 FOREIGN KEY(user_id,product_id,task_id) REFERENCES app.generation_tasks(user_id,product_id,id),
 FOREIGN KEY(user_id,product_id,final_version_id) REFERENCES app.asset_versions(user_id,product_id,id)
);
ALTER TABLE app.generation_tasks ADD CONSTRAINT compliance_task_owned FOREIGN KEY(user_id,id,compliance_id) REFERENCES app.compliance_checks(user_id,task_id,id);
CREATE TABLE app.compliance_reviews (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, check_id uuid NOT NULL,
 reviewer_id uuid NOT NULL REFERENCES app.users(id), operation_id uuid NOT NULL UNIQUE,
 decision text NOT NULL CHECK(decision IN ('approved','rejected','needs_review')), reason text NOT NULL CHECK(length(reason)>0),
 evidence_refs jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(user_id,check_id) REFERENCES app.compliance_checks(user_id,id)
);
CREATE TABLE ops.provider_receipts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), task_id uuid NOT NULL, user_id uuid NOT NULL, attempt_id uuid NOT NULL,
 provider_id text NOT NULL, response_digest text NOT NULL, polling_url_private text, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(user_id,task_id,attempt_id) REFERENCES app.provider_attempts(user_id,task_id,id), UNIQUE(attempt_id,provider_id,response_digest)
);
CREATE TRIGGER immutable_versions BEFORE UPDATE OR DELETE ON app.asset_versions FOR EACH ROW EXECUTE FUNCTION app.reject_mutation();
CREATE TRIGGER immutable_compliance BEFORE UPDATE OR DELETE ON app.compliance_checks FOR EACH ROW EXECUTE FUNCTION app.reject_mutation();
CREATE TRIGGER immutable_reviews BEFORE UPDATE OR DELETE ON app.compliance_reviews FOR EACH ROW EXECUTE FUNCTION app.reject_mutation();
CREATE TRIGGER immutable_cost BEFORE UPDATE OR DELETE ON app.task_cost_records FOR EACH ROW EXECUTE FUNCTION app.reject_mutation();
CREATE TRIGGER immutable_receipts BEFORE UPDATE OR DELETE ON ops.provider_receipts FOR EACH ROW EXECUTE FUNCTION app.reject_mutation();
ALTER TABLE app.upload_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.upload_intents FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.upload_intents USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.task_cost_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.task_cost_records FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.task_cost_records USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.compliance_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.compliance_checks FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.compliance_checks USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE app.compliance_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.compliance_reviews FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant ON app.compliance_reviews USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE ops.provider_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE ops.provider_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY executor_receipts ON ops.provider_receipts TO app_executor USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid) WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
GRANT SELECT ON app.upload_intents,app.compliance_checks,app.compliance_reviews TO app_api;
GRANT SELECT,INSERT,UPDATE ON app.upload_intents,app.assets TO app_executor;
GRANT INSERT ON app.asset_versions TO app_executor;
GRANT SELECT,INSERT ON app.compliance_checks,app.compliance_reviews,app.task_cost_records,ops.provider_receipts TO app_executor;
GRANT INSERT,UPDATE ON app.provider_attempts TO app_executor;
GRANT UPDATE ON ops.task_dispatch,ops.outbox TO app_executor;
CREATE POLICY executor_dispatch_lookup ON ops.task_dispatch FOR SELECT TO app_executor USING(true);
CREATE POLICY executor_outbox_lookup ON ops.outbox FOR SELECT TO app_executor USING(true);
GRANT USAGE ON SCHEMA ops,app TO app_worker;;

UPDATE alembic_version SET version_num='0008' WHERE alembic_version.version_num = '0007';

-- Running upgrade 0008 -> 0009

CREATE FUNCTION app.assert_lease(p_task uuid,p_owner text,p_fence bigint) RETURNS app.generation_tasks
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE u uuid; t app.generation_tasks;
BEGIN
 SELECT user_id INTO u FROM ops.task_dispatch WHERE task_id=p_task;
 IF u IS NULL THEN RAISE EXCEPTION 'task_not_found'; END IF;
 PERFORM set_config('app.user_id',u::text,true);
 SELECT * INTO t FROM app.generation_tasks WHERE id=p_task AND user_id=u FOR UPDATE;
 IF t.status<>'processing' OR t.lease_owner IS DISTINCT FROM p_owner OR t.fencing_token IS DISTINCT FROM p_fence OR t.lease_until IS NULL OR t.lease_until<=clock_timestamp()
 THEN RAISE EXCEPTION 'stale_lease' USING ERRCODE='55000'; END IF;
 RETURN t;
END $$;
CREATE FUNCTION ops.claim_task(p_task uuid,p_owner text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE u uuid; t app.generation_tasks;
BEGIN
 IF p_owner IS NULL OR length(p_owner) NOT BETWEEN 1 AND 200 THEN RAISE EXCEPTION 'invalid_owner'; END IF;
 SELECT user_id INTO u FROM ops.task_dispatch WHERE task_id=p_task;
 IF u IS NULL THEN RETURN NULL; END IF;
 PERFORM set_config('app.user_id',u::text,true);
 SELECT * INTO t FROM app.generation_tasks WHERE id=p_task AND user_id=u FOR UPDATE;
 IF t.status IN ('succeeded','failed','cancelled','uncertain') OR (t.lease_until IS NOT NULL AND t.lease_until>clock_timestamp()) THEN RETURN NULL; END IF;
 IF EXISTS(SELECT 1 FROM app.provider_attempts WHERE task_id=t.id AND provider_id IS NULL AND status IN ('intent_recorded','uncertain')) THEN
  UPDATE app.generation_tasks SET status='uncertain',lease_owner=NULL,lease_until=NULL,revision=revision+1,updated_at=now(),error_code='submission_outcome_unknown' WHERE id=t.id;
  UPDATE ops.task_dispatch SET state='uncertain',lease_until=NULL WHERE task_id=t.id;
  INSERT INTO app.task_events(user_id,task_id,type,payload) VALUES(u,t.id,'task.updated',jsonb_build_object('status','uncertain','revision',t.revision+1));
  RETURN jsonb_build_object('id',t.id,'status','uncertain');
 END IF;
 UPDATE app.generation_tasks SET status='processing',phase=CASE WHEN status='queued' THEN 'submitting' ELSE phase END,
  lease_owner=p_owner,lease_until=clock_timestamp()+interval '60 seconds',fencing_token=fencing_token+1,revision=revision+1,updated_at=now()
 WHERE id=t.id RETURNING * INTO t;
 UPDATE ops.task_dispatch SET state='processing',lease_until=t.lease_until,fencing_token=t.fencing_token WHERE task_id=t.id;
 INSERT INTO app.task_events(user_id,task_id,type,payload) VALUES(u,t.id,'task.updated',jsonb_build_object('status',t.status,'phase',t.phase,'revision',t.revision));
 RETURN jsonb_build_object('id',t.id,'status',t.status,'phase',t.phase,'fencing_token',t.fencing_token);
END $$;
CREATE FUNCTION app.renew_lease(p_task uuid,p_owner text,p_fence bigint) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE t app.generation_tasks;
BEGIN
 t:=app.assert_lease(p_task,p_owner,p_fence);
 UPDATE app.generation_tasks SET lease_until=clock_timestamp()+interval '60 seconds' WHERE id=t.id;
 UPDATE ops.task_dispatch SET lease_until=clock_timestamp()+interval '60 seconds' WHERE task_id=t.id;
END $$;
CREATE FUNCTION app.worker_context(p_task uuid,p_owner text,p_fence bigint) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE t app.generation_tasks; source app.asset_versions;
BEGIN
 t:=app.assert_lease(p_task,p_owner,p_fence);
 SELECT * INTO source FROM app.asset_versions WHERE id=t.source_asset_version_id AND user_id=t.user_id;
 RETURN to_jsonb(t)||jsonb_build_object('source',to_jsonb(source),'attempts',COALESCE((SELECT jsonb_agg(to_jsonb(a)) FROM app.provider_attempts a WHERE task_id=t.id),'[]'::jsonb));
END $$;
CREATE FUNCTION app.record_intent(p_task uuid,p_owner text,p_fence bigint,p_step text,p_request_hash text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE t app.generation_tasks; a uuid;
BEGIN
 t:=app.assert_lease(p_task,p_owner,p_fence);
 IF p_step NOT IN ('generate','detect') OR p_request_hash !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'invalid_intent'; END IF;
 IF (p_step='generate' AND t.phase<>'submitting') OR (p_step='detect' AND (t.phase<>'detecting' OR t.final_version_id IS NULL)) THEN RAISE EXCEPTION 'invalid_phase'; END IF;
 IF EXISTS(SELECT 1 FROM app.provider_attempts WHERE task_id=t.id AND step=p_step) THEN RAISE EXCEPTION 'intent_exists' USING ERRCODE='55000'; END IF;
 INSERT INTO app.provider_attempts(user_id,task_id,step,provider,model,status,request_hash,local_request_id)
 VALUES(t.user_id,t.id,p_step,'fake',CASE WHEN p_step='generate' THEN t.input_snapshot->'_execution'->>'provider_model' ELSE 'fake-facts-v1' END,'intent_recorded',p_request_hash,gen_random_uuid()) RETURNING id INTO a;
 RETURN a;
END $$;
CREATE FUNCTION app.append_receipt(p_task uuid,p_attempt uuid,p_provider_id text,p_digest text,p_polling_url text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE u uuid; receipt uuid;
BEGIN
 SELECT user_id INTO u FROM ops.task_dispatch WHERE task_id=p_task;
 IF u IS NULL THEN RAISE EXCEPTION 'task_not_found'; END IF;
 PERFORM set_config('app.user_id',u::text,true);
 IF p_provider_id IS NULL OR length(p_provider_id)=0 OR p_digest !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'invalid_receipt'; END IF;
 INSERT INTO ops.provider_receipts(user_id,task_id,attempt_id,provider_id,response_digest,polling_url_private)
 VALUES(u,p_task,p_attempt,p_provider_id,p_digest,p_polling_url)
 ON CONFLICT(attempt_id,provider_id,response_digest) DO NOTHING RETURNING id INTO receipt;
 IF receipt IS NULL THEN SELECT id INTO receipt FROM ops.provider_receipts WHERE attempt_id=p_attempt AND provider_id=p_provider_id AND response_digest=p_digest; END IF;
 RETURN receipt;
END $$;
CREATE FUNCTION app.apply_receipt(p_task uuid,p_owner text,p_fence bigint,p_receipt uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE t app.generation_tasks; r ops.provider_receipts; a app.provider_attempts;
BEGIN
 t:=app.assert_lease(p_task,p_owner,p_fence);
 SELECT * INTO r FROM ops.provider_receipts WHERE id=p_receipt AND user_id=t.user_id AND task_id=t.id;
 IF NOT FOUND THEN RAISE EXCEPTION 'receipt_not_found'; END IF;
 SELECT * INTO a FROM app.provider_attempts WHERE id=r.attempt_id AND task_id=t.id FOR UPDATE;
 IF a.provider_id IS NOT NULL AND a.provider_id<>r.provider_id THEN RAISE EXCEPTION 'receipt_conflict'; END IF;
 IF a.status IN ('succeeded','failed') THEN RETURN; END IF;
 UPDATE app.provider_attempts SET provider_id=r.provider_id,polling_url_private=r.polling_url_private,response_digest=r.response_digest,status='submitted',submitted_at=COALESCE(submitted_at,now()) WHERE id=a.id;
 UPDATE app.generation_tasks SET phase=CASE WHEN a.step='generate' THEN 'polling' ELSE 'detecting' END,revision=revision+1,updated_at=now() WHERE id=t.id;
END $$;
ALTER FUNCTION app.assert_lease(uuid,text,bigint) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.assert_lease(uuid,text,bigint) FROM PUBLIC;
ALTER FUNCTION ops.claim_task(uuid,text) OWNER TO app_executor;
REVOKE ALL ON FUNCTION ops.claim_task(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops.claim_task(uuid,text) TO app_worker;
ALTER FUNCTION app.renew_lease(uuid,text,bigint) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.renew_lease(uuid,text,bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.renew_lease(uuid,text,bigint) TO app_worker;
ALTER FUNCTION app.worker_context(uuid,text,bigint) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.worker_context(uuid,text,bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.worker_context(uuid,text,bigint) TO app_worker;
ALTER FUNCTION app.record_intent(uuid,text,bigint,text,text) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.record_intent(uuid,text,bigint,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.record_intent(uuid,text,bigint,text,text) TO app_worker;
ALTER FUNCTION app.append_receipt(uuid,uuid,text,text,text) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.append_receipt(uuid,uuid,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.append_receipt(uuid,uuid,text,text,text) TO app_worker;
ALTER FUNCTION app.apply_receipt(uuid,text,bigint,uuid) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.apply_receipt(uuid,text,bigint,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.apply_receipt(uuid,text,bigint,uuid) TO app_worker;;

UPDATE alembic_version SET version_num='0009' WHERE alembic_version.version_num = '0008';

-- Running upgrade 0009 -> 0010

ALTER TABLE app.generation_tasks ADD COLUMN generated_version_id uuid;
ALTER TABLE app.generation_tasks ADD CONSTRAINT generated_version_owned FOREIGN KEY(user_id,product_id,generated_version_id) REFERENCES app.asset_versions(user_id,product_id,id);
CREATE FUNCTION app.record_task_asset(p_task uuid,p_owner text,p_fence bigint,p_kind text,p_asset uuid,p_version uuid,p_bucket text,p_key text,p_storage_version text,p_sha text,p_width integer,p_height integer,p_bytes bigint) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE t app.generation_tasks;
BEGIN
 t:=app.assert_lease(p_task,p_owner,p_fence);
 IF p_kind NOT IN ('generated','final') THEN RAISE EXCEPTION 'invalid_asset_kind'; END IF;
 IF p_kind='generated' AND t.generated_version_id IS NOT NULL THEN RETURN t.generated_version_id; END IF;
 IF p_kind='final' AND t.final_version_id IS NOT NULL THEN RETURN t.final_version_id; END IF;
 IF (p_kind='generated' AND t.phase NOT IN ('polling','archiving')) OR (p_kind='final' AND t.phase<>'protecting') THEN RAISE EXCEPTION 'invalid_phase'; END IF;
 IF p_width IS DISTINCT FROM (t.input_snapshot->'generation'->'output'->>'width')::integer
 OR p_height IS DISTINCT FROM (t.input_snapshot->'generation'->'output'->>'height')::integer THEN RAISE EXCEPTION 'output_size_mismatch'; END IF;
 IF p_kind='generated' AND NOT EXISTS(SELECT 1 FROM app.provider_attempts WHERE task_id=t.id AND step='generate' AND provider_id IS NOT NULL AND status IN ('submitted','polling','succeeded')) THEN RAISE EXCEPTION 'generation_receipt_required'; END IF;
 INSERT INTO app.assets(id,user_id,product_id,kind,status) VALUES(p_asset,t.user_id,t.product_id,p_kind,'uploading');
 INSERT INTO app.asset_versions(id,user_id,product_id,asset_id,version_number,bucket,object_key,storage_version_id,sha256,mime,width,height,byte_size,color_space,canonical,source_version_id)
 VALUES(p_version,t.user_id,t.product_id,p_asset,1,p_bucket,p_key,p_storage_version,p_sha,'image/png',p_width,p_height,p_bytes,'sRGB',true,CASE WHEN p_kind='final' THEN t.generated_version_id ELSE t.source_asset_version_id END);
 UPDATE app.assets SET status='ready',current_version_id=p_version WHERE id=p_asset;
 IF p_kind='generated' THEN
  UPDATE app.provider_attempts SET status='succeeded',finished_at=now() WHERE task_id=t.id AND step='generate';
  UPDATE app.generation_tasks SET generated_version_id=p_version,phase='protecting',revision=revision+1,updated_at=now() WHERE id=t.id;
 ELSE
  UPDATE app.generation_tasks SET final_version_id=p_version,phase='detecting',revision=revision+1,updated_at=now() WHERE id=t.id;
 END IF;
 RETURN p_version;
END $$;
CREATE FUNCTION app.record_report(p_task uuid,p_owner text,p_fence bigint,p_id uuid,p_final_sha text,p_facts jsonb,p_results jsonb,p_overall text,p_sampling boolean,p_report_sha text,p_bucket text,p_key text,p_storage_version text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE t app.generation_tasks; v app.asset_versions;
BEGIN
 t:=app.assert_lease(p_task,p_owner,p_fence);
 IF t.compliance_id IS NOT NULL THEN RETURN t.compliance_id; END IF;
 IF t.phase<>'detecting' THEN RAISE EXCEPTION 'invalid_phase'; END IF;
 SELECT * INTO v FROM app.asset_versions WHERE id=t.final_version_id;
 IF NOT FOUND OR v.sha256 IS DISTINCT FROM p_final_sha THEN RAISE EXCEPTION 'final_hash_mismatch'; END IF;
 IF NOT EXISTS(SELECT 1 FROM app.provider_attempts WHERE task_id=t.id AND step='detect') THEN RAISE EXCEPTION 'detection_intent_required'; END IF;
 IF p_overall='compliant' AND (COALESCE((p_facts->>'analysis_complete')::boolean,false)=false
 OR EXISTS(SELECT 1 FROM jsonb_array_elements(t.input_snapshot->'_execution'->'rules') AS rule WHERE rule->>'evidence_status' IS DISTINCT FROM 'verified')) THEN RAISE EXCEPTION 'unverified_cannot_pass'; END IF;
 INSERT INTO app.compliance_checks(id,user_id,product_id,task_id,final_version_id,final_sha256,facts,facts_schema_version,rule_snapshots,per_platform_results,auto_overall,sampling_selected,report_sha256,report_bucket,report_object_key,report_storage_version_id)
 VALUES(p_id,t.user_id,t.product_id,t.id,v.id,v.sha256,p_facts,1,t.input_snapshot->'_execution'->'rules',p_results,p_overall,p_sampling,p_report_sha,p_bucket,p_key,p_storage_version);
 UPDATE app.provider_attempts SET status='succeeded',finished_at=now() WHERE task_id=t.id AND step='detect';
 UPDATE app.generation_tasks SET compliance_id=p_id,phase='finalizing',revision=revision+1,updated_at=now() WHERE id=t.id;
 RETURN p_id;
END $$;
CREATE FUNCTION app.settle_task(p_task uuid,p_owner text,p_fence bigint) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE u uuid; t app.generation_tasks; w app.wallets;
BEGIN
 SELECT user_id INTO u FROM ops.task_dispatch WHERE task_id=p_task;
 IF u IS NULL THEN RAISE EXCEPTION 'task_not_found'; END IF;
 PERFORM set_config('app.user_id',u::text,true);
 SELECT * INTO w FROM app.wallets WHERE user_id=u FOR UPDATE;
 SELECT * INTO t FROM app.generation_tasks WHERE id=p_task AND user_id=u FOR UPDATE;
 IF t.status='succeeded' THEN RETURN; END IF;
 t:=app.assert_lease(p_task,p_owner,p_fence);
 IF t.phase<>'finalizing' OR NOT EXISTS(
  SELECT 1 FROM app.compliance_checks c JOIN app.asset_versions v ON v.id=c.final_version_id AND v.user_id=c.user_id
  JOIN app.assets a ON a.id=v.asset_id AND a.user_id=v.user_id
  WHERE c.id=t.compliance_id AND c.task_id=t.id AND v.id=t.final_version_id AND v.sha256=c.final_sha256
  AND v.canonical AND a.status='ready' AND c.report_object_key<>'' AND c.report_bucket<>'') THEN RAISE EXCEPTION 'delivery_incomplete'; END IF;
 UPDATE app.wallets SET reserved=reserved-t.reserved_credits,spent_total=spent_total+t.reserved_credits,revision=revision+1,updated_at=now() WHERE user_id=u RETURNING * INTO w;
 INSERT INTO app.credit_transactions(user_id,task_id,operation_id,type,amount,available_delta,reserved_delta,funded_delta,spent_delta,available_after,reserved_after,actor_ref,reason)
 VALUES(u,t.id,gen_random_uuid(),'charge',t.reserved_credits,0,-t.reserved_credits,0,t.reserved_credits,w.available,w.reserved,'system','delivered');
 UPDATE app.generation_tasks SET status='succeeded',credits_status='charged',completed_at=now(),lease_owner=NULL,lease_until=NULL,revision=revision+1,updated_at=now() WHERE id=t.id;
 UPDATE ops.task_dispatch SET state='succeeded',lease_until=NULL WHERE task_id=t.id;
 INSERT INTO app.task_events(user_id,task_id,type,payload) VALUES(u,t.id,'task.updated',jsonb_build_object('status','succeeded','revision',t.revision+1));
END $$;
CREATE FUNCTION app.fail_task(p_task uuid,p_owner text,p_fence bigint,p_code text,p_uncertain boolean) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE u uuid; t app.generation_tasks; w app.wallets;
BEGIN
 SELECT user_id INTO u FROM ops.task_dispatch WHERE task_id=p_task;
 IF u IS NULL THEN RAISE EXCEPTION 'task_not_found'; END IF;
 PERFORM set_config('app.user_id',u::text,true);
 SELECT * INTO w FROM app.wallets WHERE user_id=u FOR UPDATE;
 SELECT * INTO t FROM app.generation_tasks WHERE id=p_task AND user_id=u FOR UPDATE;
 IF t.status='failed' AND NOT p_uncertain THEN RETURN; END IF;
 t:=app.assert_lease(p_task,p_owner,p_fence);
 IF p_uncertain THEN
  UPDATE app.generation_tasks SET status='uncertain',lease_owner=NULL,lease_until=NULL,error_code=p_code,revision=revision+1,updated_at=now() WHERE id=t.id;
  UPDATE app.provider_attempts SET status='uncertain' WHERE task_id=t.id AND status NOT IN ('succeeded','failed');
 ELSE
  IF EXISTS(SELECT 1 FROM app.provider_attempts WHERE task_id=t.id AND status IN ('intent_recorded','submitted','polling','uncertain')) THEN RAISE EXCEPTION 'unresolved_attempt_requires_reconciliation'; END IF;
  UPDATE app.wallets SET available=available+t.reserved_credits,reserved=reserved-t.reserved_credits,revision=revision+1,updated_at=now() WHERE user_id=u RETURNING * INTO w;
  INSERT INTO app.credit_transactions(user_id,task_id,operation_id,type,amount,available_delta,reserved_delta,funded_delta,spent_delta,available_after,reserved_after,actor_ref,reason)
  VALUES(u,t.id,gen_random_uuid(),'refund',t.reserved_credits,t.reserved_credits,-t.reserved_credits,0,0,w.available,w.reserved,'system',p_code);
  UPDATE app.generation_tasks SET status='failed',credits_status='refunded',completed_at=now(),lease_owner=NULL,lease_until=NULL,error_code=p_code,revision=revision+1,updated_at=now() WHERE id=t.id;
 END IF;
 UPDATE ops.task_dispatch SET state=CASE WHEN p_uncertain THEN 'uncertain' ELSE 'failed' END,lease_until=NULL WHERE task_id=t.id;
 INSERT INTO app.task_events(user_id,task_id,type,payload) VALUES(u,t.id,'task.updated',jsonb_build_object('status',CASE WHEN p_uncertain THEN 'uncertain' ELSE 'failed' END,'revision',t.revision+1));
END $$;
ALTER FUNCTION app.record_task_asset(uuid,text,bigint,text,uuid,uuid,text,text,text,text,integer,integer,bigint) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.record_task_asset(uuid,text,bigint,text,uuid,uuid,text,text,text,text,integer,integer,bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.record_task_asset(uuid,text,bigint,text,uuid,uuid,text,text,text,text,integer,integer,bigint) TO app_worker;
ALTER FUNCTION app.record_report(uuid,text,bigint,uuid,text,jsonb,jsonb,text,boolean,text,text,text,text) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.record_report(uuid,text,bigint,uuid,text,jsonb,jsonb,text,boolean,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.record_report(uuid,text,bigint,uuid,text,jsonb,jsonb,text,boolean,text,text,text,text) TO app_worker;
ALTER FUNCTION app.settle_task(uuid,text,bigint) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.settle_task(uuid,text,bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.settle_task(uuid,text,bigint) TO app_worker;
ALTER FUNCTION app.fail_task(uuid,text,bigint,text,boolean) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.fail_task(uuid,text,bigint,text,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.fail_task(uuid,text,bigint,text,boolean) TO app_worker;;

UPDATE alembic_version SET version_num='0010' WHERE alembic_version.version_num = '0009';

-- Running upgrade 0010 -> 0011

CREATE OR REPLACE FUNCTION app.assert_lease(p_task uuid,p_owner text,p_fence bigint) RETURNS app.generation_tasks
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE u uuid; t app.generation_tasks;
BEGIN
 SELECT user_id INTO u FROM ops.task_dispatch WHERE task_id=p_task;
 IF u IS NULL THEN RAISE EXCEPTION 'task_not_found'; END IF;
 PERFORM set_config('app.user_id',u::text,true);
 SELECT * INTO t FROM app.generation_tasks WHERE id=p_task AND user_id=u FOR UPDATE;
 IF t.status<>'processing' OR t.lease_owner IS DISTINCT FROM p_owner OR t.fencing_token IS DISTINCT FROM p_fence OR t.lease_until IS NULL OR t.lease_until<=clock_timestamp()
 THEN RAISE EXCEPTION 'stale_lease' USING ERRCODE='55000'; END IF;
 RETURN t;
END $$;
CREATE FUNCTION app.record_attempt_failure(p_task uuid,p_owner text,p_fence bigint,p_attempt uuid,p_code text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE t app.generation_tasks;
BEGIN
 t:=app.assert_lease(p_task,p_owner,p_fence);
 UPDATE app.provider_attempts SET status='failed',error_code=p_code,finished_at=now() WHERE id=p_attempt AND task_id=t.id AND status<>'succeeded';
 IF NOT FOUND THEN RAISE EXCEPTION 'attempt_not_found'; END IF;
END $$;
ALTER FUNCTION app.record_attempt_failure(uuid,text,bigint,uuid,text) OWNER TO app_executor;
REVOKE ALL ON FUNCTION app.record_attempt_failure(uuid,text,bigint,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.record_attempt_failure(uuid,text,bigint,uuid,text) TO app_worker;
CREATE OR REPLACE FUNCTION app.fail_task(p_task uuid,p_owner text,p_fence bigint,p_code text,p_uncertain boolean) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE u uuid; t app.generation_tasks; w app.wallets;
BEGIN
 SELECT user_id INTO u FROM ops.task_dispatch WHERE task_id=p_task;
 IF u IS NULL THEN RAISE EXCEPTION 'task_not_found'; END IF;
 PERFORM set_config('app.user_id',u::text,true);
 SELECT * INTO w FROM app.wallets WHERE user_id=u FOR UPDATE;
 SELECT * INTO t FROM app.generation_tasks WHERE id=p_task AND user_id=u FOR UPDATE;
 IF t.status='failed' AND NOT p_uncertain THEN RETURN; END IF;
 t:=app.assert_lease(p_task,p_owner,p_fence);
 IF p_uncertain THEN
  UPDATE app.generation_tasks SET status='uncertain',lease_owner=NULL,lease_until=NULL,error_code=p_code,revision=revision+1,updated_at=now() WHERE id=t.id;
  UPDATE app.provider_attempts SET status='uncertain' WHERE task_id=t.id AND status NOT IN ('succeeded','failed');
 ELSE
  IF EXISTS(SELECT 1 FROM app.provider_attempts WHERE task_id=t.id AND status IN ('intent_recorded','submitted','polling','uncertain')) THEN RAISE EXCEPTION 'unresolved_attempt_requires_reconciliation'; END IF;
  UPDATE app.wallets SET available=available+t.reserved_credits,reserved=reserved-t.reserved_credits,revision=revision+1,updated_at=now() WHERE user_id=u RETURNING * INTO w;
  INSERT INTO app.credit_transactions(user_id,task_id,operation_id,type,amount,available_delta,reserved_delta,funded_delta,spent_delta,available_after,reserved_after,actor_ref,reason)
  VALUES(u,t.id,gen_random_uuid(),'refund',t.reserved_credits,t.reserved_credits,-t.reserved_credits,0,0,w.available,w.reserved,'system',p_code);
  UPDATE app.generation_tasks SET status='failed',credits_status='refunded',completed_at=now(),lease_owner=NULL,lease_until=NULL,error_code=p_code,revision=revision+1,updated_at=now() WHERE id=t.id;
 END IF;
 UPDATE ops.task_dispatch SET state=CASE WHEN p_uncertain THEN 'uncertain' ELSE 'failed' END,lease_until=NULL WHERE task_id=t.id;
 INSERT INTO app.task_events(user_id,task_id,type,payload) VALUES(u,t.id,'task.updated',jsonb_build_object('status',CASE WHEN p_uncertain THEN 'uncertain' ELSE 'failed' END,'revision',t.revision+1));
END $$;;

UPDATE alembic_version SET version_num='0011' WHERE alembic_version.version_num = '0010';

COMMIT;

