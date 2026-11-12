import ast
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ['PYTHONPATH']=str(ROOT/'src')
mode=sys.argv[1:]
if mode==['task','P4-02','--profile','offline']:
    raise SystemExit(subprocess.call([sys.executable,'-m','unittest','discover','-s','tests/contract','-p','test_gemini.py','-v']))
if mode==['task','P4-01','--profile','offline']:
    # Contract-only gate: always injects a local HTTP transport, never a real API key.
    raise SystemExit(subprocess.call([sys.executable,'-m','unittest','discover','-s','tests/contract','-p','test_bfl.py','-v']))
if mode==['task','P1-02']:
    if not os.environ.get('TEST_DATABASE_URL'):raise SystemExit('BLOCKED_ENV: isolated TEST_DATABASE_URL required')
    files=[p for folder in ('src','scripts') for p in (ROOT/folder).rglob('*.py')]
    for path in files:ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
    print(f'P1-02: {len(files)} Python files parsed; native PG invoker/RLS/role/pool checks follow',flush=True)
    commands=[[sys.executable,'-c','import visual_platform.api.main, visual_platform.worker.runner, visual_platform.events.publisher; print("Backend imports OK")']]
    commands.extend([sys.executable,'-m','unittest','discover','-s','tests/integration','-p',pattern,'-v'] for pattern in ('test_native.py','test_readonly.py','test_pool_context.py'))
    for command in commands:
        code=subprocess.call(command)
        if code:raise SystemExit(code)
    raise SystemExit(0)
if mode not in (['unit'],['integration']):
    raise SystemExit('NOT_RUN: gate not implemented; no false success')
if mode==['integration'] and not os.environ.get('TEST_DATABASE_URL'):
    raise SystemExit('BLOCKED_ENV: TEST_DATABASE_URL required')
raise SystemExit(subprocess.call([sys.executable,'-m','unittest','discover','-s','tests/'+mode[0],'-v']))
