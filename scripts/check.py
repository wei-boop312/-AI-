import os, subprocess, sys
from pathlib import Path
os.chdir(Path(__file__).resolve().parents[1])
os.environ["PYTHONPATH"] = str(Path("src").resolve())
if sys.argv[1:] != ["unit"]:
    raise SystemExit("NOT_RUN: requested gate not implemented; native integration pending")
raise SystemExit(subprocess.call([sys.executable,"-m","unittest","discover","-s","tests/unit","-v"]))
