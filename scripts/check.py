import os, subprocess, sys
from pathlib import Path
os.chdir(Path(__file__).resolve().parents[1])
os.environ["PYTHONPATH"] = str(Path("src").resolve())
mode=sys.argv[1:]
if mode not in (["unit"],["integration"]):
    raise SystemExit("NOT_RUN: gate not implemented; no false success")
if mode==["integration"] and not os.environ.get("TEST_DATABASE_URL"):
    raise SystemExit("BLOCKED_ENV: TEST_DATABASE_URL required")
raise SystemExit(subprocess.call([sys.executable,"-m","unittest","discover","-s","tests/"+mode[0],"-v"]))
