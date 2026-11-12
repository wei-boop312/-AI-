import argparse
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
from visual_platform.db.pool import open_pool
from visual_platform.providers.fake import DurableFakeProvider
from visual_platform.storage.s3 import S3Storage
from visual_platform.worker.runner import Worker

async def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--task',type=UUID,required=True); args=parser.parse_args()
    if os.environ.get('PROVIDER_PROFILE','offline')!='offline': raise SystemExit('Only offline provider is enabled')
    settings=SimpleNamespace(**{name.lower():os.environ[name] for name in ('S3_ENDPOINT','S3_ACCESS_KEY','S3_SECRET_KEY','S3_BUCKET')},s3_region=os.environ.get('S3_REGION','us-east-1'))
    pool=await open_pool(os.environ['WORKER_DATABASE_URL'],'app_worker'); storage=S3Storage(settings)
    directory=Path(os.environ.get('FAKE_PROVIDER_DIR',str(Path(__file__).resolve().parents[3]/'work'/'fake-provider')))
    try:
        result=await Worker(pool,storage,DurableFakeProvider(directory)).run(args.task)
        print(json.dumps({'task_id':str(args.task),'result':result}))
    finally: await pool.close(); storage.close()

if __name__=='__main__': asyncio.run(main())
