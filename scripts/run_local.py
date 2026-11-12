import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('component',choices=['api','publisher','worker','web']);args=p.parse_args()
profile=ROOT/'.local'/'runtime.json'
if not profile.exists(): raise SystemExit('Run scripts/setup_local.py first')
env={**os.environ,**json.loads(profile.read_text(encoding='utf-8')),'PYTHONPATH':str(ROOT/'src')}
commands={'api':[sys.executable,'-m','uvicorn','visual_platform.api.main:app','--host','127.0.0.1','--port','8000'],'publisher':[sys.executable,'-m','visual_platform.events'],'worker':[sys.executable,'-m','visual_platform.worker','--consume'],'web':['pnpm','--dir','apps/web','dev']}
command=commands[args.component]
if args.component=='web' and os.name=='nt':
    import shutil
    command[0]=shutil.which('pnpm') or 'pnpm'
raise SystemExit(subprocess.call(command,cwd=ROOT,env=env))
