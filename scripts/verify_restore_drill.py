"""Prepare and verify local-only disaster-recovery fixtures without paid providers."""
import argparse
import asyncio
from datetime import datetime,timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
from uuid import UUID,uuid4
from urllib.parse import urlsplit
import httpx
import psycopg
from psycopg.types.json import Jsonb
from fastapi.testclient import TestClient
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from visual_platform.api.main import create_app
from visual_platform.core.settings import Settings
from visual_platform.core.identity import hash_password
from visual_platform.db.pool import open_pool
from visual_platform.providers.fake import DurableFakeProvider
from visual_platform.services.backup import require
from visual_platform.services.config_backup import validate_configuration
from visual_platform.services.rule_operations import publish_rule
from visual_platform.storage.s3 import S3Storage,StorageError
from visual_platform.worker.runner import Worker

p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
prepare=sub.add_parser('prepare');prepare.add_argument('--profile-dir',type=Path,default=ROOT/'.local')
verify=sub.add_parser('verify');verify.add_argument('--profile-dir',type=Path,required=True);verify.add_argument('--restore-result',type=Path,required=True)
cleanup=sub.add_parser('cleanup');cleanup.add_argument('--profile-dir',type=Path,default=ROOT/'.local')
marker=sub.add_parser('marker');marker.add_argument('--profile-dir',type=Path,default=ROOT/'.local')
for command in (prepare,verify,cleanup,marker):command.add_argument('--state',type=Path,required=True)
args=p.parse_args()
profile=json.loads((args.profile_dir.resolve()/'runtime.json').read_text())
require(profile['PROVIDER_PROFILE']=='offline','offline profile required')
require(all(urlsplit(profile[key]).hostname in ('127.0.0.1','localhost') for key in ('APP_ORIGIN','API_DATABASE_URL','AUTH_DATABASE_URL','ADMIN_DATABASE_URL','WORKER_DATABASE_URL','S3_ENDPOINT')),'drill fixtures require an explicit loopback profile')
settings=Settings(profile['API_DATABASE_URL'],profile['AUTH_DATABASE_URL'],Path(profile['JWT_PRIVATE_KEY_FILE']).read_text(),Path(profile['JWT_PUBLIC_KEY_FILE']).read_text(),profile['APP_ORIGIN'],False,profile['S3_ENDPOINT'],profile['S3_ACCESS_KEY'],profile['S3_SECRET_KEY'],profile['S3_BUCKET'],profile['S3_REGION'])
def login(client,state):
    response=client.post('/api/v1/auth/login',json={'email':state['email'],'password':state['password']},headers={'origin':profile['APP_ORIGIN']});require(response.status_code==200,'drill login failed')
    return {'origin':profile['APP_ORIGIN'],'x-csrf-token':client.cookies['visual_csrf']}
def task(client,body,headers):
    q=client.post('/api/v1/quotes',json=body,headers=headers);require(q.status_code==201,'drill quote failed')
    r=client.post('/api/v1/tasks',json={**body,'quote_id':q.json()['quote_id']},headers={**headers,'idempotency-key':str(uuid4())});require(r.status_code==201,'drill task failed');return r.json()['id']
def run_worker(task_id,mode='success',broken=False):
    class ArchiveOutage(S3Storage):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            def fail(*args,**kwargs):raise StorageError('controlled archive outage')
            self.client.put_object=fail
    async def run():
        pool=await open_pool(profile['WORKER_DATABASE_URL'],'app_worker');storage=(ArchiveOutage if broken else S3Storage)(settings)
        try:return await Worker(pool,storage,DurableFakeProvider(Path(profile['FAKE_PROVIDER_DIR']),mode=mode)).run(task_id)
        finally:await pool.close();storage.close()
    return asyncio.run(run())
def admin(query,values):
    with psycopg.connect(profile['ADMIN_DATABASE_URL']) as c:return c.execute(query,values).fetchone()[0]

if args.command=='prepare':
    require(args.state.resolve().is_relative_to(ROOT/'work') and not args.state.exists(),'new private drill state required')
    uid=uuid4();state={'user_id':str(uid),'email':'restore-'+uuid4().hex+'@example.invalid','password':uuid4().hex+uuid4().hex,'tasks':{}}
    admin("SELECT app.create_private_user(%s,%s,'backup restore drill',%s)",(uid,state['email'],hash_password(state['password'])))
    admin("SELECT app.grant_credits(%s,%s,200,'offline restore fixture credits')",(uid,uuid4()))
    storage=S3Storage(settings);evidence=b'Offline synthetic rule archive for backup restoration; not current platform policy.'
    try:
        rule=publish_rule(profile['ADMIN_DATABASE_URL'],storage,{'platform':'amazon','marketplace':'US','category':'backup-synthetic','image_type':'MAIN','version':'backup-'+uuid4().hex,'evidence_status':'unverified','evidence_sha256':hashlib.sha256(evidence).hexdigest(),'config':{}},evidence,uuid4(),'archive synthetic backup rule fixture')
    finally:storage.close()
    state['rule_id']=rule['rule_id']
    with TestClient(create_app(settings)) as client:
        headers=login(client,state);state['old_access']=client.cookies['visual_access']
        product=client.post('/api/v1/products',json={'name':'restore synthetic product','category':'backup-synthetic'},headers=headers);require(product.status_code==201,'drill product failed');state['product_id']=product.json()['id']
        stream=BytesIO();Image.new('RGB',(16,16),(201,15,35)).save(stream,'PNG');data=stream.getvalue()
        intent=client.post('/api/v1/assets/upload-intents',json={'product_id':state['product_id'],'filename':'restore.png','mime':'image/png','size':len(data)},headers=headers).json()
        require(httpx.put(intent['upload_url'],content=data,headers=intent['headers']).status_code==200,'drill upload failed')
        complete=client.post('/api/v1/assets/upload-intents/'+intent['intent_id']+'/complete',headers=headers);require(complete.status_code==200,'drill normalize failed');source=complete.json()
        appearance=client.post('/api/v1/products/'+state['product_id']+'/appearances',json={'name':'restore appearance','config':{'colors':['red']}},headers=headers);require(appearance.status_code==201,'drill appearance failed')
        body={'product_id':state['product_id'],'source_asset_version_id':source['version_id'],'appearance_profile_id':appearance.json()['id'],'generation':{'type':'scene','prompt':'offline backup fixture','output':{'width':16,'height':16},'protection_mode':'pixel_exact','regions':[{'source_x':0,'source_y':0,'width':4,'height':4,'target_x':8,'target_y':8}]},'targets':[{'platform':'amazon','marketplace':'US','category':'backup-synthetic','image_type':'MAIN'}]}
        state['tasks']['completed']=task(client,body,headers);require(run_worker(state['tasks']['completed'])=='succeeded','drill completed task failed')
        report=client.get('/api/v1/tasks/'+state['tasks']['completed']+'/compliance').json();state['report_sha256']=report['report_sha256'];state['final_sha256']=report['final_sha256']
        admin('SELECT app.review_check(%s,%s,%s,%s,%s,%s,%s)',(state['tasks']['completed'],report['id'],uuid4(),uid,'approved','synthetic fixture manual review',Jsonb(['local:restore-drill'])))
        state['tasks']['known']=task(client,body,headers);require(run_worker(state['tasks']['known'],broken=True)=='retryable','known-id outage fixture failed')
        known=admin('SELECT ops.task_details(%s)',(state['tasks']['known'],));state['known_receipt_id']=known['receipts'][0]['id']
        state['tasks']['unknown']=task(client,body,headers);require(run_worker(state['tasks']['unknown'],'uncertain')=='stopped','unknown fixture failed')
        state['tasks']['queued']=task(client,body,headers)
        state['balance']=client.get('/api/v1/credits/balance').json();require((state['balance']['available'],state['balance']['reserved'],state['balance']['spent_total'])==(136,48,16),'fixture balance mismatch')
    args.state.parent.mkdir(parents=True,exist_ok=True);args.state.write_text(json.dumps(state));print('Prepared isolated restore fixtures; private state retained in work.')
elif args.command=='marker':
    state=json.loads(args.state.read_text())
    with TestClient(create_app(settings)) as client:
        headers=login(client,state);response=client.post('/api/v1/products',json={'name':'post-backup marker','category':'backup-synthetic'},headers=headers);require(response.status_code==201,'marker failed');state['post_snapshot_product_id']=response.json()['id']
    args.state.write_text(json.dumps(state));print('Post-snapshot marker created.')
elif args.command=='verify':
    state=json.loads(args.state.read_text());result=json.loads(args.restore_result.read_text())
    configuration=result.get('configuration_restore',{})
    require(configuration.get('status')=='verified_snapshot_restored' and configuration.get('applied_to_runtime') is False,'configuration snapshot restoration proof missing')
    config_root=Path(configuration['output']);config_manifest=json.loads((config_root/'application.json').read_text())
    verified_config=validate_configuration(config_root,config_manifest)
    require(all(configuration[key]==verified_config[key] for key in ('application_commit','files_verified','snapshot_sha256')),'restored configuration version or checksum differs')
    with TestClient(create_app(settings)) as client:
        require(client.get('/api/v1/health/ready').status_code==200,'restored API not ready')
        require(client.get('/api/v1/auth/me',headers={'cookie':'visual_access='+state['old_access']}).status_code==401,'old access accepted')
        client.cookies.clear();headers=login(client,state)
        require(client.get('/api/v1/products/'+state['post_snapshot_product_id']).status_code==404,'post-snapshot marker unexpectedly restored')
        require(client.get('/api/v1/credits/balance').json()==state['balance'],'restored frozen wallet mismatch')
        report=client.get('/api/v1/tasks/'+state['tasks']['completed']+'/compliance').json()
        require(report['report_sha256']==state['report_sha256'] and report['final_sha256']==state['final_sha256'] and report['effective_source']=='human_review','restored report/review mismatch')
        download=client.get('/api/v1/tasks/'+state['tasks']['completed']+'/download',follow_redirects=False)
        image=httpx.get(download.headers['location']).content;require(hashlib.sha256(image).hexdigest()==state['final_sha256'],'restored final download mismatch')
        with Image.open(BytesIO(image)) as final:require(final.convert('RGB').crop((8,8,12,12)).tobytes()==Image.new('RGB',(4,4),(201,15,35)).tobytes(),'restored protection pixels mismatch')
        for key in ('queued','known','unknown'):require(client.get('/api/v1/tasks/'+state['tasks'][key]).json()['status']=='uncertain','pending task not quarantined')
        require(run_worker(state['tasks']['queued'])=='not_claimed' and run_worker(state['tasks']['unknown'])=='not_claimed','restored unresolved task was claimed')
        before=admin('SELECT ops.task_details(%s)',(state['tasks']['known'],));require(len([a for a in before['attempts'] if a['step']=='generate'])==1,'generation attempt mismatch')
        admin('SELECT ops.reconcile_task(%s,%s,%s,%s,%s,%s)',(state['tasks']['known'],uuid4(),'resume',state['known_receipt_id'],'source workers were fenced before snapshot; original generation receipt verified','a'*64))
        require(run_worker(state['tasks']['known'])=='succeeded','restored known result recovery failed')
        after=admin('SELECT ops.task_details(%s)',(state['tasks']['known'],));require(len([a for a in after['attempts'] if a['step']=='generate'])==1,'generation resubmitted after restore')
        final_balance=client.get('/api/v1/credits/balance').json();require((final_balance['available'],final_balance['reserved'],final_balance['spent_total'])==(136,32,32),'post-recovery wallet mismatch')
    result['verification']={'api_ready':True,'old_access_rejected':True,'post_snapshot_marker_absent':True,'completed_report_review_and_download_hash_preserved':True,'pixel_protection_preserved':True,'three_fixture_tasks_quarantined':True,'unknown_and_queued_cannot_submit':True,'known_id_recovered_without_new_generate':True,'balance_at_snapshot':state['balance'],'balance_after_one_safe_recovery':final_balance,'verified_at':datetime.now(timezone.utc).isoformat()}
    result['configuration_restore']={key:value for key,value in result['configuration_restore'].items() if key!='output'}
    (ROOT/'docs/evidence/backup-restore-drill.json').write_text(json.dumps(result,indent=2)+'\n');print('Restore API, artifacts, quarantine and known-id recovery verified.')
else:
    state=json.loads(args.state.read_text())
    with TestClient(create_app(settings)) as client:
        headers=login(client,state);require(client.post('/api/v1/tasks/'+state['tasks']['queued']+'/cancel',headers=headers).status_code==200,'source fixture cancel failed')
        outcome=run_worker(state['tasks']['known']);require(outcome in ('succeeded','not_claimed') and client.get('/api/v1/tasks/'+state['tasks']['known']).json()['status']=='succeeded','source fixture safe finish failed')
        unknown=client.get('/api/v1/tasks/'+state['tasks']['unknown']).json()
        if unknown['status']!='failed':
            operation=state.setdefault('cleanup_operation_id',str(uuid4()));args.state.write_text(json.dumps(state))
            admin('SELECT ops.reconcile_task(%s,%s,%s,NULL,%s,%s)',(state['tasks']['unknown'],UUID(operation),'fail','offline restore fixture closed; internal credits released','a'*64))
        require(client.get('/api/v1/credits/balance').json()['reserved']==0,'source cleanup left reserved credits')
    print('Source fixture pending balances closed through normal API/operations.')
