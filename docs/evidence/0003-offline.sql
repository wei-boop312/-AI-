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
 INSERT INTO ops.outbox(user_id,task_id,event_type,dedupe_key) VALUES(u,p_id,'task.queued',p_id::text||'NULL');
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

COMMIT;

