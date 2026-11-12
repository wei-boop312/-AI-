import asyncio
import contextlib
import hashlib
import json
from uuid import UUID,uuid4,uuid5
import asyncpg
from botocore.exceptions import BotoCoreError,ClientError
from visual_platform.providers.contract import ProviderFailure,ProviderUncertain
from visual_platform.domain.facts import Facts
from visual_platform.domain.compliance import evaluate
from visual_platform.services.upload import decode
from visual_platform.services.image_job import transform
from visual_platform.storage.s3 import StorageError

class Worker:
    def __init__(self,pool,storage,provider,owner=None):
        self.pool=pool; self.storage=storage; self.provider=provider; self.owner=owner or str(uuid4())
    async def db(self,query,*args):
        async with self.pool.acquire() as c: return await c.fetchval(query,*args)
    async def context(self,task,fence):
        return json.loads(await self.db('SELECT app.worker_context($1,$2,$3)',task,self.owner,fence))
    async def read(self,record):
        if record['bucket']!=self.storage.bucket: raise RuntimeError('bucket not configured')
        data,_,_=await asyncio.to_thread(self.storage.get,record['object_key'],version=record['storage_version_id'],limit=80*1024*1024)
        if hashlib.sha256(data).hexdigest()!=record['sha256']: raise ValueError('asset_hash_mismatch')
        return data
    async def renew(self,task,fence):
        while True:
            await asyncio.sleep(20)
            await self.db('SELECT app.renew_lease($1,$2,$3)',task,self.owner,fence)
    async def receipt(self,task,fence,attempt,receipt):
        identity=await self.db('SELECT app.append_receipt($1,$2,$3,$4,$5)',task,attempt,receipt.provider_id,receipt.response_digest,receipt.polling_url)
        await self.db('SELECT app.apply_receipt($1,$2,$3,$4)',task,self.owner,fence,identity)
        await self.db('SELECT app.record_fake_cost($1,$2,$3,$4)',task,self.owner,fence,attempt)
    async def submit(self,task,fence,step,payload):
        encoded=payload if isinstance(payload,bytes) else json.dumps(payload,sort_keys=True).encode()
        attempt=await self.db('SELECT app.record_intent($1,$2,$3,$4,$5)',task,self.owner,fence,step,hashlib.sha256(encoded).hexdigest())
        try:
            method=self.provider.submit_generate if step=='generate' else self.provider.submit_detect
            result=await asyncio.to_thread(method,attempt,payload)
        except ProviderFailure:
            await self.db('SELECT app.record_attempt_failure($1,$2,$3,$4,$5)',task,self.owner,fence,attempt,'supplier_explicit_failure')
            await self.db('SELECT app.fail_task($1,$2,$3,$4,false)',task,self.owner,fence,'supplier_explicit_failure')
            return False
        except Exception:
            # Any unclassified exception after intent is potentially a paid/accepted submission.
            await self.db('SELECT app.fail_task($1,$2,$3,$4,true)',task,self.owner,fence,'submission_outcome_unknown')
            return False
        await self.receipt(task,fence,attempt,result)
        return True
    async def asset(self,task,fence,ctx,kind,data,meta):
        version=uuid5(task,kind); asset=uuid5(task,kind+'-asset'); key='private/'+ctx['user_id']+'/'+str(version)
        storage_version=await asyncio.to_thread(self.storage.put_immutable,key,data,'image/png')
        return await self.db('SELECT app.record_task_asset($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)',task,self.owner,fence,kind,asset,version,self.storage.bucket,key,storage_version,hashlib.sha256(data).hexdigest(),meta['width'],meta['height'],len(data))
    async def run(self,task_id):
        task=UUID(str(task_id)); result=await self.db('SELECT ops.claim_task($1,$2)',task,self.owner)
        if result is None: return 'not_claimed'
        claim=json.loads(result)
        if claim['status']=='uncertain': return 'uncertain'
        fence=claim['fencing_token']; heartbeat=asyncio.create_task(self.renew(task,fence))
        try:
            for _ in range(12):
                if heartbeat.done(): await heartbeat
                ctx=await self.context(task,fence); generation=ctx['input_snapshot']['generation']; phase=ctx['phase']
                attempts={a['step']:a for a in ctx['attempts']}
                if phase=='submitting':
                    # Validate fixed source bytes before creating a possibly paid intent.
                    await self.read(ctx['source'])
                    if 'generate' in attempts:
                        await self.db('SELECT app.fail_task($1,$2,$3,$4,true)',task,self.owner,fence,'submission_outcome_unknown'); return 'uncertain'
                    if not await self.submit(task,fence,'generate',generation): return 'stopped'
                elif phase in ('polling','archiving'):
                    attempt=attempts['generate']
                    await self.db('SELECT app.record_fake_cost($1,$2,$3,$4)',task,self.owner,fence,UUID(attempt['id']))
                    if not attempt['provider_id']: raise RuntimeError('known provider id required')
                    data=await asyncio.to_thread(self.provider.fetch_image,attempt['provider_id'])
                    canonical,meta=await decode(data,'image/png')
                    await self.asset(task,fence,ctx,'generated',canonical,meta)
                elif phase=='protecting':
                    source=await self.read(ctx['source']); generated=await self.read(ctx['generated'])
                    final,meta=await transform(source,generated,generation)
                    await self.asset(task,fence,ctx,'final',final,meta)
                elif phase=='detecting':
                    final=await self.read(ctx['final']); final_hash=hashlib.sha256(final).hexdigest()
                    if 'detect' not in attempts:
                        if not await self.submit(task,fence,'detect',final): return 'stopped'
                        continue
                    attempt=attempts['detect']
                    if not attempt['provider_id']:
                        await self.db('SELECT app.fail_task($1,$2,$3,$4,true)',task,self.owner,fence,'detection_outcome_unknown'); return 'uncertain'
                    payload=await asyncio.to_thread(self.provider.fetch_facts,attempt['provider_id'])
                    try:
                        facts=Facts.model_validate(payload['facts'])
                        if payload.get('final_sha256')!=final_hash or (facts.image_width,facts.image_height)!=(ctx['final']['width'],ctx['final']['height']): raise ValueError('facts mismatch')
                    except (ValueError,KeyError,TypeError):
                        facts=Facts.model_validate({'schema_version':1,'analysis_complete':False,'image_width':ctx['final']['width'],'image_height':ctx['final']['height'],'text_items':[],'logo_items':[],'watermark_items':[],'background':{'classification':'unknown','confidence':0.0},'product_extent':None,'uncertainties':['facts_invalid_or_final_image_mismatch']})
                    source=await self.read(ctx['source']); _,proof=await transform(source,final,generation,verify=True)
                    rules=ctx['input_snapshot']['_execution']['rules']
                    check=evaluate(final_hash,[r['platform'] for r in rules],analysis_complete=facts.analysis_complete)
                    for platform,rule in zip(check['per_platform'],rules):
                        platform.update({'marketplace':rule['marketplace'],'image_type':rule['image_type'],'rule_version':rule['version'],'evidence_status':rule['evidence_status'],'checks':[{'id':'local_decode','status':'passed'},{'id':'pixel_protection','status':'passed' if proof['pixel_exact_passed'] else 'not_applicable','evidence':proof}]})
                    report={'schema_version':1,'final_asset_version_id':ctx['final_version_id'],'final_sha256':final_hash,'facts':facts.model_dump(mode='json'),'per_platform':check['per_platform'],'auto_overall':'manual_review','pixel_protection':proof,'sampling_selected':int(hashlib.sha256(str(task).encode()).hexdigest()[:8],16)%20==0,'provider_profile':'offline_fake'}
                    report_id=uuid5(task,'report'); key='private/'+ctx['user_id']+'/'+str(report_id)+'.json'; data=json.dumps(report,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
                    storage_version=await asyncio.to_thread(self.storage.put_immutable,key,data,'application/json')
                    await self.db('SELECT app.record_report($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8,$9,$10,$11,$12,$13)',task,self.owner,fence,report_id,final_hash,json.dumps(report['facts']),json.dumps(report['per_platform']),report['auto_overall'],report['sampling_selected'],hashlib.sha256(data).hexdigest(),self.storage.bucket,key,storage_version)
                elif phase=='finalizing':
                    await self.db('SELECT app.settle_task($1,$2,$3)',task,self.owner,fence); return 'succeeded'
                else: raise RuntimeError('unsupported phase')
            raise RuntimeError('phase progress limit exceeded')
        except asyncpg.ObjectNotInPrerequisiteStateError:
            return 'lease_lost'
        except (BotoCoreError,ClientError,StorageError,RuntimeError,OSError):
            return 'retryable'
        except ValueError:
            # Local validation failure is definite only if no unresolved paid attempt exists.
            try: await self.db('SELECT app.fail_task($1,$2,$3,$4,false)',task,self.owner,fence,'local_validation_failed')
            except asyncpg.RaiseError:
                await self.db('SELECT app.fail_task($1,$2,$3,$4,true)',task,self.owner,fence,'delivery_requires_reconciliation')
            return 'stopped'
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError,asyncpg.PostgresError): await heartbeat
            await self.db('SELECT app.yield_lease($1,$2,$3)',task,self.owner,fence)
