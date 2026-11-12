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
sub.add_parser("migrate")
user=sub.add_parser("create-user"); user.add_argument("--email",required=True); user.add_argument("--name",default="私有用户"); user.add_argument("--credits",type=int,default=0)
grant=sub.add_parser("grant"); grant.add_argument("--user-id",type=UUID,required=True); grant.add_argument("--amount",type=int,required=True); grant.add_argument("--operation-id",type=UUID,required=True); grant.add_argument("--reason",required=True)
args=parser.parse_args()
if args.command=="doctor":
    import importlib.util
    print(json.dumps({"python":platform.python_version(),"tools":{x:shutil.which(x) for x in ["node","npm","pnpm","docker","git"]},"modules":{x:bool(importlib.util.find_spec(x)) for x in ["asyncpg","alembic","psycopg","aio_pika","boto3","PIL"]},"configured":{x:bool(os.environ.get(x)) for x in ["API_DATABASE_URL","AUTH_DATABASE_URL","ADMIN_DATABASE_URL","MIGRATION_DATABASE_URL"]}},indent=2))
elif args.command=="migrate":
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
