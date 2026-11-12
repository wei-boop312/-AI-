"""Owned local infrastructure only. Default down keeps all named data volumes."""
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import time
from types import SimpleNamespace
from urllib.parse import quote
from uuid import uuid4
import psycopg
ROOT=Path(__file__).resolve().parents[1]

class ComposeRuntime:
    def __init__(self,folder,*,ephemeral=None):
        self.folder=Path(folder).resolve()
        if not any(self.folder.is_relative_to(ROOT/name) for name in ('.local','work')):raise ValueError('private Compose profile must stay in ignored .local/work')
        self.docker=shutil.which('docker')
        if not self.docker:raise EnvironmentError('BLOCKED_ENV: Docker engine required; existing native services were not touched')
        checked=subprocess.run([self.docker,'version','--format','{{.Server.Version}}'],capture_output=True,text=True)
        if checked.returncode:raise EnvironmentError('BLOCKED_ENV: Docker engine unavailable')
        if ephemeral and not self.folder.is_relative_to(ROOT/'work'):raise ValueError('volume-removing test profiles are restricted to isolated work directories')
        self.folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.chmod(self.folder,0o700)
        state_file=self.folder/'state.json'
        if state_file.exists():
            self.state=json.loads(state_file.read_text())
            if self.state['workspace']!=str(ROOT) or (ephemeral is not None and self.state['ephemeral']!=ephemeral):raise ValueError('Compose profile ownership or lifecycle mismatch')
            if self.state['ephemeral'] and not self.folder.is_relative_to(ROOT/'work'):raise ValueError('ephemeral profile escaped isolated work directory')
        else:
            self.state={'workspace':str(ROOT),'owner':uuid4().hex,'project':'visual-'+hashlib.sha256(str(self.folder).encode()).hexdigest()[:16],'ephemeral':bool(ephemeral),'pg_user':'vp_owner','pg_password':secrets.token_urlsafe(32),'mq_user':'vp_mq','mq_password':secrets.token_urlsafe(32),'s3_access':secrets.token_urlsafe(18),'s3_secret':secrets.token_urlsafe(32),'ports':{'test':55432,'dev':55433,'mq':5679,'s3':18333}}
            self.write_private(state_file,json.dumps(self.state,indent=2))
        s=self.state;p=s['ports'];owner=hashlib.sha256(str(ROOT).encode()).hexdigest()
        config=self.folder/'s3.json'
        self.write_private(config,json.dumps({'identities':[{'name':'visual_local','credentials':[{'accessKey':s['s3_access'],'secretKey':s['s3_secret']}],'actions':['Admin','Read','Write','List','Tagging']}]}))
        # The image uses a non-root UID. A read-only file bind bypasses the private
        # host parent directory, so permit reads inside that container while the
        # 0700 host directory still prevents other local users traversing it.
        os.chmod(config,0o644)
        values={'VISUAL_OWNER':s['owner'],'VISUAL_WORKSPACE':owner,'PG_BOOTSTRAP_USER':s['pg_user'],'PG_BOOTSTRAP_PASSWORD':s['pg_password'],'MQ_BOOTSTRAP_USER':s['mq_user'],'MQ_BOOTSTRAP_PASSWORD':s['mq_password'],'S3_CONFIG_FILE':config.as_posix(),'PG_TEST_PORT':p['test'],'PG_DEV_PORT':p['dev'],'MQ_PORT':p['mq'],'S3_PORT':p['s3']}
        self.write_private(self.folder/'compose.env','\n'.join(k+'='+json.dumps(str(v),ensure_ascii=False) for k,v in values.items())+'\n')
        self.env={**os.environ,'MIGRATION_DATABASE_URL':'postgresql://'+s['pg_user']+':'+quote(s['pg_password'],safe='')+'@127.0.0.1:'+str(p['dev'])+'/postgres','AMQP_URL':'amqp://'+s['mq_user']+':'+quote(s['mq_password'],safe='')+'@127.0.0.1:'+str(p['mq'])+'/visual-test','S3_ENDPOINT':'http://127.0.0.1:'+str(p['s3']),'S3_ACCESS_KEY':s['s3_access'],'S3_SECRET_KEY':s['s3_secret'],'S3_BUCKET':'visual-compose-private','S3_REGION':'us-east-1','PROVIDER_PROFILE':'offline'}
        self.prefix=[self.docker,'compose','--project-name',s['project'],'--env-file',str(self.folder/'compose.env'),'-f',str(ROOT/'compose.yaml')]
    @staticmethod
    def write_private(path,text):
        path.write_text(text,encoding='utf-8');os.chmod(path,0o600)
    def invoke(self,args):
        with (self.folder/'compose.log').open('ab') as log:
            result=subprocess.run([*self.prefix,*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise RuntimeError('Compose command failed; inspect ignored private compose.log')
    def owned_resources(self):
        for kind,args,label_expr in [('container',['ps','-aq'],'{{json .Config.Labels}}'),('volume',['volume','ls','-q'],'{{json .Labels}}'),('network',['network','ls','-q'],'{{json .Labels}}')]:
            ids=subprocess.check_output([self.docker,*args,'--filter','label=com.docker.compose.project='+self.state['project']],text=True).split()
            for identity in ids:
                command=[self.docker,'inspect','--format',label_expr,identity] if kind=='container' else [self.docker,kind,'inspect','--format',label_expr,identity]
                labels=json.loads(subprocess.check_output(command,text=True))
                if labels.get('visual.owner')!=self.state['owner']:raise ValueError('unowned Compose resource: refusing lifecycle operation')
    def config_summary(self):
        result=subprocess.run([*self.prefix,'config','--format','json'],capture_output=True,text=True)
        if result.returncode:raise RuntimeError('Compose configuration invalid; private required settings must be supplied')
        data=json.loads(result.stdout);images=json.loads((ROOT/'ops/build-images.json').read_text())['images']
        for name,service in data['services'].items():
            expected=images['postgres' if name.startswith('postgres') else 'seaweedfs' if name=='s3' else 'rabbitmq']['image']
            if service['image']!=expected:raise ValueError('Compose image digest differs from registry inventory')
            if any(port.get('host_ip')!='127.0.0.1' for port in service.get('ports',[])):raise ValueError('Compose ports must bind loopback only')
        return {'services':sorted(data['services']),'loopback_only':True,'pinned_images':True,'project':self.state['project']}
    def up(self):
        self.config_summary();self.owned_resources()
        current=subprocess.check_output([*self.prefix,'ps','-q'],text=True).strip()
        if not current:
            for port in self.state['ports'].values():
                with socket.socket() as sock:
                    if sock.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('loopback port occupied; existing native service preserved')
        self.invoke(['up','-d','--wait','--wait-timeout','150'])
        self.wait_ready()
    def wait_ready(self):
        import aio_pika
        from visual_platform.storage.s3 import S3Storage
        for name in ('aio_pika','aiormq'):logging.getLogger(name).setLevel(logging.CRITICAL)
        storage=S3Storage(SimpleNamespace(**{k.lower():self.env[k] for k in ('S3_ENDPOINT','S3_ACCESS_KEY','S3_SECRET_KEY','S3_BUCKET','S3_REGION')}))
        async def mq():
            connection=await aio_pika.connect(self.env['AMQP_URL'],timeout=2);await connection.close()
        deadline=time.monotonic()+90
        try:
            while time.monotonic()<deadline:
                try:
                    with psycopg.connect(self.env['MIGRATION_DATABASE_URL'],connect_timeout=2) as c:c.execute('SELECT 1')
                    asyncio.run(mq());storage.client.list_buckets();return
                except Exception:time.sleep(.5)
            raise RuntimeError('Compose PG/MQ/S3 readiness timed out; inspect private logs')
        finally:storage.close()
    def down(self,*,remove_volumes=False):
        if remove_volumes and not self.state['ephemeral']:raise ValueError('daily profile volumes cannot be removed by this helper')
        self.owned_resources();self.invoke(['down',*(['--volumes'] if remove_volumes else [])])
