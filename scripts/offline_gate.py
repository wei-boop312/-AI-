"""Validate current CI evidence once for P0-P3/P4 mock contracts/P5-01.

This does not launch services or recycle local profiles. CI prepares evidence via
the documented native/browser/Compose/image steps before invoking this gate.
"""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
from verify_sources import verify
from verify_delivery import verify_static,verify_run

ROOT=Path(__file__).resolve().parents[1]

def main(task):
    evidence=ROOT/'work/ci-public';evidence.mkdir(parents=True,exist_ok=True)
    report={'observed_at':datetime.now(timezone.utc).isoformat(),'requested_gate':task,
            'profile':'offline','paid_calls':0,'deployed':False,
            'not_verified':{'P4-03':'WAITING_EXTERNAL: real provider call and budget authorization are absent',
                            'P5-02':'separate restore/restart drill; this gate does not rerun operations',
                            'P5-03':'WAITING_EXTERNAL: target environment, policy evidence and release decision'},
            'scope':'current native test suites + production browser + Compose migrations/persistence + locked build evidence'}
    try:
        report['source_provenance']=verify()
        report.update(verify_static());report.update(verify_run(evidence))
        plan=json.loads((ROOT/'docs/specification/CODEX_EXECUTION/tasks.json').read_text(encoding='utf-8-sig'))
        report['verified_tasks']=[x['id'] for x in plan['tasks'] if x['phase'] in ('P0','P1','P2','P3')]+['P4-01 (mock HTTP)','P4-02 (mock SDK HTTP)','P5-01']
        report['result']='OFFLINE_READY';code=0
    except EnvironmentError as error:report.update(result='BLOCKED_ENV',reason=str(error));code=3
    except Exception as error:report.update(result='FAIL',reason=str(error));code=1
    (evidence/'offline-gate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False));return code

if __name__=='__main__':raise SystemExit(main(sys.argv[1] if len(sys.argv)>1 else 'all'))
