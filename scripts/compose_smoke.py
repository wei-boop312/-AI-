"""Exercise a new owned Compose project, including data survival across down/up."""
import asyncio
from datetime import datetime,timezone
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit
from types import SimpleNamespace
from uuid import uuid4
import aio_pika
import psycopg
from alembic.config import Config
from alembic.script import ScriptDirectory
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from compose_runtime import ComposeRuntime
from visual_platform.storage.s3 import S3Storage

def main():
    folder=ROOT/'work'/('compose-smoke-'+uuid4().hex)
    runtime=ComposeRuntime(folder,ephemeral=True);env={**runtime.env,'PYTHONPATH':str(ROOT/'src')};private=folder/'logs';private.mkdir()
    public=ROOT/'work/ci-public';public.mkdir(parents=True,exist_ok=True)
    def command(args,name,child_env=None):
        with (private/(name+'.log')).open('wb') as log:result=subprocess.run([sys.executable,*args],cwd=ROOT,env=child_env or env,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise RuntimeError(name+' failed; private diagnostics retained')
    async def fixture(phase):
        connection=await aio_pika.connect(env['AMQP_URL'],timeout=5)
        try:
            channel=await connection.channel(publisher_confirms=True);queue=await channel.declare_queue('compose-persist',durable=True,arguments={'x-queue-type':'quorum'})
            if phase=='prepare':await channel.default_exchange.publish(aio_pika.Message(b'compose-persistent-message',delivery_mode=aio_pika.DeliveryMode.PERSISTENT),routing_key=queue.name,mandatory=True)
            else:
                message=await queue.get(timeout=5)
                if message.body!=b'compose-persistent-message':raise ValueError('MQ message content lost across recreation')
                await message.ack();await queue.delete(if_unused=False,if_empty=True)
        finally:await connection.close()
    def pg_identity():
        with psycopg.connect(env['MIGRATION_DATABASE_URL']) as c:
            identity=str(c.execute('SELECT system_identifier FROM pg_control_system()').fetchone()[0]);users=c.execute('SELECT count(*) FROM app.users').fetchone()[0]
        return identity,users
    storage=S3Storage(SimpleNamespace(**{k.lower():env[k] for k in ('S3_ENDPOINT','S3_ACCESS_KEY','S3_SECRET_KEY','S3_BUCKET','S3_REGION')}))
    clock=time.monotonic()
    try:
        runtime.up();summary=runtime.config_summary()
        script=ScriptDirectory.from_config(Config(str(ROOT/'alembic.ini')));head=script.get_current_head();previous=script.get_revision(head).down_revision
        test_env={**env,'MIGRATION_DATABASE_URL':env['MIGRATION_DATABASE_URL'].replace(':'+str(runtime.state['ports']['dev'])+'/',':'+str(runtime.state['ports']['test'])+'/')}
        command(['-m','alembic','upgrade','head'],'empty-test-upgrade',test_env)
        command(['-m','alembic','upgrade',previous],'previous-dev-upgrade')
        with psycopg.connect(env['MIGRATION_DATABASE_URL']) as c:
            if c.execute('SELECT version_num FROM alembic_version').fetchone()[0]!=previous:raise ValueError('previous migration setup failed')
        command(['scripts/dev.py','bootstrap','--compose-profile',str(folder),'--profile-dir',str(folder/'profile'),'--demo-account'],'setup')
        command(['scripts/verify_bootstrap.py','--profile-dir',str(folder/'profile')],'bootstrap-verification')
        before=pg_identity();data=b'compose-private-object-survives-container-recreation';version=storage.put_immutable('compose-smoke/persist',data,'application/octet-stream')
        asyncio.run(fixture('prepare'))
        runtime.down();runtime.up()
        if pg_identity()!=before:raise ValueError('PG identity/data changed across volume-preserving down/up')
        read,_,_=storage.get('compose-smoke/persist',version=version)
        if read!=data:raise ValueError('S3 content changed across container recreation')
        asyncio.run(fixture('verify'))
        bootstrap=json.loads((ROOT/'docs/evidence/bootstrap-health-readonly.json').read_text())
        result={'observed_at':datetime.now(timezone.utc).isoformat(),'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'compose':summary,'fresh_bootstrap':bootstrap,'empty_upgrade_to_head':head,'previous_upgrade_from':previous,'previous_upgrade_to':bootstrap['migration_head'],'postgres_system_identifier_preserved':True,'postgres_user_count_preserved':before[1],'private_s3_sha256':hashlib.sha256(read).hexdigest(),'rabbit_quorum_message_preserved':True,'recreated_container_services':True,'seconds':round(time.monotonic()-clock,3),'paid_calls':0,'result':'PASS'}
        (ROOT/'docs/evidence/compose-smoke.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');(public/'compose-smoke.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'result':'PASS','services':summary['services'],'data_survived_down_up':True,'migration_head':bootstrap['migration_head'],'paid_calls':0}))
    except Exception:
        logs=[]
        try:
            runtime.owned_resources()
            output=subprocess.run([*runtime.prefix,'logs','--no-color','--tail','30'],capture_output=True,text=True)
            logs.append(output.stdout+output.stderr)
        except Exception:logs.append('Owned container diagnostics unavailable')
        for path in [folder/'compose.log',*private.glob('*.log')]:
            if path.is_file():logs.append(path.read_text(encoding='utf-8',errors='replace'))
        text='\n'.join(logs)
        for name in ('pg_password','mq_password','s3_access','s3_secret'):text=text.replace(runtime.state[name],'[redacted]')
        for path in (folder/'profile').glob('*.json'):
            values=json.loads(path.read_text())
            for name,value in values.items():
                if not isinstance(value,str):continue
                if name.endswith('_DATABASE_URL'):
                    password=urlsplit(value).password
                    if password:text=text.replace(password,'[redacted]')
                elif 'password' in name.lower() or name=='S3_SECRET_KEY':text=text.replace(value,'[redacted]')
        text=re.sub(r'(?:postgres(?:ql)?|amqps?|https?)://\S+','[redacted-url]',text)
        text=re.sub(r'-----BEGIN .*?PRIVATE KEY-----.*?-----END .*?PRIVATE KEY-----','[redacted-private-key]',text,flags=re.S)
        (public/'compose-diagnostics.log').write_text(text[-40000:],encoding='utf-8')
        raise
    finally:storage.close();runtime.down(remove_volumes=True)

if __name__=='__main__':
    try:main()
    except EnvironmentError as error:print(str(error));raise SystemExit(3)
