import argparse
import getpass
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import UUID,uuid4

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT); sys.path.insert(0,str(ROOT/"src"))
parser=argparse.ArgumentParser()
sub=parser.add_subparsers(dest="command",required=True)
sub.add_parser("doctor")
migrate=sub.add_parser("migrate");migrate.add_argument('--compose-profile',type=Path)
for name in ('up','down'):
    command=sub.add_parser(name);command.add_argument('--profile-dir',type=Path,default=ROOT/'.local/compose')
bootstrap=sub.add_parser('bootstrap');bootstrap.add_argument('--compose-profile',type=Path,default=ROOT/'.local/compose');bootstrap.add_argument('--profile-dir',type=Path,default=ROOT/'.local');bootstrap.add_argument('--demo-account',action='store_true')
user=sub.add_parser("create-user"); user.add_argument("--email",required=True); user.add_argument("--name",default="私有用户"); user.add_argument("--credits",type=int,default=0)
grant=sub.add_parser("grant"); grant.add_argument("--user-id",type=UUID,required=True); grant.add_argument("--amount",type=int,required=True); grant.add_argument("--operation-id",type=UUID,required=True); grant.add_argument("--reason",required=True)
args=parser.parse_args()
if args.command in ('up','down'):
    from compose_runtime import ComposeRuntime
    try:
        runtime=ComposeRuntime(args.profile_dir)
        if args.command=='up':runtime.up()
        else:runtime.down()
        print(json.dumps({'status':args.command,'profile_dir':str(runtime.folder),'volumes':'retained','project':runtime.state['project']}))
    except EnvironmentError as exc:print(str(exc));raise SystemExit(3)
elif args.command=='bootstrap':
    from compose_runtime import ComposeRuntime
    runtime=ComposeRuntime(args.compose_profile);runtime.owned_resources();runtime.wait_ready()
    command=[sys.executable,'scripts/setup_local.py','--profile-dir',str(args.profile_dir)]
    if args.demo_account:command.append('--demo-account')
    raise SystemExit(subprocess.call(command,cwd=ROOT,env=runtime.env))
elif args.command=="doctor":
    import importlib.util
    image_inventory=json.loads((ROOT/'ops/build-images.json').read_text())
    print(json.dumps({"python":platform.python_version(),"platform":platform.platform(),"tools":{x:shutil.which(x) for x in ["node","npm","pnpm","docker","git"]},"modules":{x:bool(importlib.util.find_spec(x)) for x in ["asyncpg","alembic","psycopg","aio_pika","boto3","PIL"]},"configured":{x:bool(os.environ.get(x)) for x in ["API_DATABASE_URL","AUTH_DATABASE_URL","ADMIN_DATABASE_URL","MIGRATION_DATABASE_URL"]},"container_images":image_inventory['images'],"image_requirement":"Linux Docker engine; native services remain a separate verified path"},indent=2))
elif args.command=="migrate":
    if args.compose_profile:
        from compose_runtime import ComposeRuntime
        runtime=ComposeRuntime(args.compose_profile);runtime.owned_resources();runtime.wait_ready();os.environ.update({k:v for k,v in runtime.env.items() if k in ('MIGRATION_DATABASE_URL',)})
    if not os.environ.get("MIGRATION_DATABASE_URL"): parser.error("MIGRATION_DATABASE_URL required")
    raise SystemExit(subprocess.call([sys.executable,"-m","alembic","upgrade","head"]))
else:
    import psycopg
    from visual_platform.core.identity import hash_password
    dsn=os.environ.get("ADMIN_DATABASE_URL")
    if not dsn: parser.error("ADMIN_DATABASE_URL required")
    if args.command=="create-user":
        if args.credits<0: parser.error("credits must be nonnegative")
        password=getpass.getpass("New account password (12+ characters): ")
        if password!=getpass.getpass("Confirm password: "): parser.error("password mismatch")
        try: password_hash=hash_password(password)
        except ValueError as exc: parser.error(str(exc))
        uid=uuid4()
    try:
        with psycopg.connect(dsn) as c:
            role=c.execute("SELECT rolsuper,rolbypassrls,pg_has_role(current_user,'ops_admin','MEMBER') FROM pg_roles WHERE rolname=current_user").fetchone()
            if role[0] or role[1] or not role[2]: parser.error("admin CLI requires a dedicated non-superuser ops_admin login")
            if args.command=="create-user":
                c.execute("SELECT app.create_private_user(%s,%s,%s,%s)",(uid,args.email.strip().casefold(),args.name,password_hash))
                if args.credits: c.execute("SELECT app.grant_credits(%s,%s,%s,'initial test credits')",(uid,uuid4(),args.credits))
                print(json.dumps({"user_id":str(uid),"email":args.email.strip().casefold()}))
            else:
                if args.amount<=0: parser.error("amount must be positive")
                c.execute("SELECT app.grant_credits(%s,%s,%s,%s)",(args.user_id,args.operation_id,args.amount,args.reason))
                print(json.dumps({"operation_id":str(args.operation_id),"status":"granted"}))
    except psycopg.Error:
        raise SystemExit("Database operation failed; verify credentials, uniqueness and input. No secrets printed.")
