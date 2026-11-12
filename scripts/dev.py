import json, shutil, sys, platform
if sys.argv[1:] != ["doctor"]:
    raise SystemExit("Only doctor implemented; service lifecycle pending")
print(json.dumps({"python":platform.python_version(),"tools":{x:shutil.which(x) for x in ["node","npm","docker","git"]}},indent=2))
