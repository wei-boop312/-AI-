"""Run built non-root API/web/publisher/worker images against disposable services.

Linux loopback host networking is a CI rehearsal, not a production topology.
Private roles/keys stay in an owned ignored profile; no model credentials.
"""
from datetime import datetime,timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from uuid import uuid4
import httpx
from PIL import Image
from compose_runtime import ComposeRuntime

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

def main():
    if os.name=='nt' or not os.environ.get('CI'):raise EnvironmentError('BLOCKED_ENV: Linux disposable CI container rehearsal only')
    for port in (8000,8080):
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1',port))==0:raise EnvironmentError('BLOCKED_ENV: application port already occupied')
    identity=uuid4().hex;folder=ROOT/'work'/('container-smoke-'+identity)
    runtime=ComposeRuntime(folder,ephemeral=True)
    private=folder/'logs';private.mkdir();containers=[]
    public=ROOT/'work/ci-public';public.mkdir(parents=True,exist_ok=True)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    report={'commit':commit,'observed_at':datetime.now(timezone.utc).isoformat(),'paid_calls':0,'profile':'offline_fake','scope':'built non-root containers; Linux host-network loopback rehearsal; no deployment'}
    def require(value,message):
        if not value:raise ValueError(message)
    def docker(args):
        result=subprocess.run(['docker',*args],cwd=ROOT,capture_output=True,text=True)
        if result.returncode:
            with (private/'docker.log').open('a') as log:log.write(result.stdout+result.stderr)
            raise RuntimeError('Owned runtime container command failed; private log retained')
        return result.stdout
    def command(args,name):
        with (private/(name+'.log')).open('wb') as output:
            result=subprocess.run([sys.executable,*args],cwd=ROOT,env={**runtime.env,'PYTHONPATH':str(ROOT/'src')},stdout=output,stderr=subprocess.STDOUT)
        require(result.returncode==0,name+' failed; private log retained')
    def launch(name,image,values=None,command_args=(),mounts=(),options=()):
        name='visual-runtime-'+identity[:12]+'-'+name
        containers.append(name)
        args=['run','-d','--name',name,'--label','visual.rehearsal='+identity,'--network','host',*options]
        if values is not None:
            envfile=folder/(name+'.env')
            require(all('\n' not in str(v) and '\r' not in str(v) for v in values.values()),'multiline container environment refused')
            runtime.write_private(envfile,'\n'.join(k+'='+str(v) for k,v in values.items())+'\n')
            args+=['--env-file',str(envfile)]
        for source,target in mounts:args+=['--mount','type=bind,src='+str(source)+',dst='+target+',readonly']
        docker([*args,image,*command_args]);return name
    def wait(predicate,label):
        deadline=time.monotonic()+100
        while time.monotonic()<deadline:
            try:
                if predicate():return
            except (httpx.HTTPError,KeyError,ValueError):pass
            time.sleep(.5)
        raise ValueError(label+' did not become ready')
    started=time.monotonic()
    try:
        inspections=[]
        for name,expected in (('visual-api:ci','10001:10001'),('visual-web:ci','101:101')):
            item=json.loads(docker(['image','inspect',name]))[0]
            require(item['Config']['User']==expected and item['Config']['Labels']['org.opencontainers.image.revision']==commit,'image identity or revision mismatch')
            inspections.append({'image':name,'id':item['Id'],'user':expected})
        runtime.up()
        profile_dir=folder/'profile'
        command(['scripts/setup_local.py','--profile-dir',str(profile_dir),'--origin','http://127.0.0.1:8080','--demo-account'],'bootstrap')
        profile=json.loads((profile_dir/'runtime.json').read_text());account=json.loads((profile_dir/'account.json').read_text())
        os.chmod(profile_dir,0o700)
        mounts=[]
        for key,target in (('JWT_PRIVATE_KEY_FILE','/run/visual/private.pem'),('JWT_PUBLIC_KEY_FILE','/run/visual/public.pem')):
            source=Path(profile[key]);os.chmod(source,0o644);mounts.append((source,target));profile[key]=target
        s3=['S3_ENDPOINT','S3_ACCESS_KEY','S3_SECRET_KEY','S3_BUCKET','S3_REGION']
        # Each container receives only its service role; admin/DDL remain host-only.
        api_keys=['API_DATABASE_URL','AUTH_DATABASE_URL','JWT_PRIVATE_KEY_FILE','JWT_PUBLIC_KEY_FILE','APP_ORIGIN','COOKIE_SECURE',*s3]
        api=launch('api','visual-api:ci',{k:profile[k] for k in api_keys},['uvicorn','visual_platform.api.main:app','--host','127.0.0.1','--port','8000'],mounts=mounts)
        launch('publisher','visual-api:ci',{k:profile[k] for k in ('DISPATCH_DATABASE_URL','AMQP_URL','QUEUE_PREFIX')},['python','-m','visual_platform.events'])
        worker_keys=['WORKER_DATABASE_URL','AMQP_URL','QUEUE_PREFIX','PROVIDER_PROFILE',*s3]
        launch('worker','visual-api:ci',{**{k:profile[k] for k in worker_keys},'FAKE_PROVIDER_DIR':'/app/work/fake-runtime'},['python','-m','visual_platform.worker','--consume'])
        nginx=(ROOT/'ops/nginx.conf').read_text()
        require(nginx.count('listen 8080;')==1,'unexpected Nginx listener configuration')
        nginx_path=folder/'nginx-loopback.conf'
        runtime.write_private(nginx_path,nginx.replace('listen 8080;','listen 127.0.0.1:8080;'));os.chmod(nginx_path,0o644)
        launch('web','visual-web:ci',mounts=[(nginx_path,'/etc/nginx/nginx.conf')],options=['--add-host','api:127.0.0.1'])
        with httpx.Client(base_url='http://127.0.0.1:8080',trust_env=False,timeout=10,follow_redirects=False) as client:
            wait(lambda:client.get('/api/v1/health/ready').status_code==200,'proxied API')
            html=client.get('/');require(html.status_code==200 and '<div id="root">' in html.text,'Nginx static application missing')
            scripts=re.findall(r'src="([^"]+\.js)"',html.text);require(bool(scripts),'production script manifest empty')
            for script in scripts:require(client.get(script).status_code==200,'production script missing')
            origin={'origin':profile['APP_ORIGIN']}
            response=client.post('/api/v1/auth/login',json={'email':account['email'],'password':account['password']},headers=origin)
            require(response.status_code==200,'container private login failed')
            headers={**origin,'x-csrf-token':client.cookies['visual_csrf']}
            def post(path,body,expected=201,extra=None):
                response=client.post('/api/v1/'+path,json=body,headers={**headers,**(extra or {})})
                require(response.status_code==expected,'container API operation failed: '+path);return response.json()
            product=post('products',{'name':'容器闭环验收','category':'generic'})['id']
            source=Image.new('RGB',(320,256),(201,15,35));stream=BytesIO();source.save(stream,'PNG');data=stream.getvalue()
            upload=post('assets/upload-intents',{'product_id':product,'filename':'source.png','mime':'image/png','size':len(data)})
            uploaded=httpx.put(upload['upload_url'],content=data,headers=upload['headers'],trust_env=False,timeout=10)
            require(uploaded.status_code==200,'container private upload failed')
            version=post('assets/upload-intents/'+upload['intent_id']+'/complete',{},200)['version_id']
            body={'product_id':product,'source_asset_version_id':version,'generation':{'type':'scene','prompt':'offline container rehearsal','output':{'width':320,'height':256},'protection_mode':'pixel_exact','regions':[{'source_x':0,'source_y':0,'width':5,'height':6,'target_x':8,'target_y':7}]},'targets':[{'platform':'amazon','marketplace':'US','category':'generic','image_type':'MAIN'}]}
            quote=post('quotes',body);task=post('tasks',{**body,'quote_id':quote['quote_id']},extra={'idempotency-key':str(uuid4())})['id']
            wait(lambda:client.get('/api/v1/tasks/'+task).json()['status']=='succeeded','container MQ Worker task')
            result=client.get('/api/v1/tasks/'+task).json()
            redirect=client.get('/api/v1/tasks/'+task+'/download');require(redirect.status_code==302,'container final download missing')
            final=httpx.get(redirect.headers['location'],trust_env=False,timeout=10);require(final.status_code==200,'private final artifact unavailable')
            digest=hashlib.sha256(final.content).hexdigest();require(digest==result['result']['sha256'],'final artifact hash mismatch')
            with Image.open(BytesIO(final.content)) as image:require(image.convert('RGB').crop((8,7,13,13)).tobytes()==source.crop((0,0,5,6)).tobytes(),'container protected pixels differ')
            redirect=client.get('/api/v1/tasks/'+task+'/report/download');require(redirect.status_code==302,'container report missing')
            artifact=httpx.get(redirect.headers['location'],trust_env=False,timeout=10);require(artifact.status_code==200,'container report unavailable');check=artifact.json()
            require(check['final_sha256']==digest and check['pixel_protection']['pixel_exact_passed'] and check['auto_overall']=='manual_review','container report mismatch or unverified policy auto-approved')
            balance=client.get('/api/v1/credits/balance').json();require(balance['available']==184 and balance['reserved']==0 and balance['spent_total']==16,'container financial settlement incorrect')
            ledger=client.get('/api/v1/credits/transactions').json()['items']
            require(sum(row['type']=='charge' and row['task_id']==task for row in ledger)==1,'container task must have exactly one charge')
            inspection=json.loads(docker(['inspect',api]))[0];require(inspection['State']['Running'],'API container exited')
            report.update(result='PASS',runtime_images=inspections,final_sha256=digest,pixel_exact=True,report_bound_to_final=True,manual_review=True,wallet=balance,seconds=round(time.monotonic()-started,3))
    except Exception:
        report.update(result='FAIL',reason='Runtime container rehearsal failed; inspect sanitized diagnostic and private owned profile')
        diagnostics=[]
        for name in containers:
            output=subprocess.run(['docker','logs','--tail','40',name],capture_output=True,text=True)
            diagnostics.append(output.stdout+output.stderr)
        text='\n'.join(diagnostics)
        for value in runtime.state.values():
            if isinstance(value,str) and len(value)>12:text=text.replace(value,'[redacted]')
        text=re.sub(r'(?:postgres(?:ql)?|amqps?|https?)://\S+','[redacted-url]',text)
        text=re.sub(r'-----BEGIN .*?PRIVATE KEY-----.*?-----END .*?PRIVATE KEY-----','[redacted-private-key]',text,flags=re.S)
        (public/'container-diagnostics.log').write_text(text[-24000:],encoding='utf-8')
        raise
    finally:
        (public/'container-runtime.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        try:
            for name in reversed(containers):
                inspected=subprocess.run(['docker','inspect','--format','{{ index .Config.Labels "visual.rehearsal" }}',name],capture_output=True,text=True)
                if inspected.returncode==0 and inspected.stdout.strip()==identity:docker(['rm','-f','-v',name])
        finally:runtime.down(remove_volumes=True)
    print(json.dumps(report))

if __name__=='__main__':
    try:main()
    except EnvironmentError as error:print(str(error));raise SystemExit(3)
    except Exception:print('FAIL: container rehearsal; inspect public sanitized diagnostics and private owned profile');raise SystemExit(1)
