"""Sanitized monitoring output. No mutations or automated reconciliation."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Thresholds:
    unknown_seconds:float=300
    outbox_seconds:float=30
    heartbeat_seconds:float=15
    def __post_init__(self):
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in (self.unknown_seconds,self.outbox_seconds,self.heartbeat_seconds)):raise ValueError('finite positive monitoring thresholds required')

def alerts(snapshot,thresholds=Thresholds(),dependencies=None):
    result=[]
    def emit(code,severity):result.append({'code':code,'severity':severity})
    for key in ('wallet_equation_errors','ledger_total_errors','reservation_link_errors','task_credit_state_errors','duplicate_terminal_settlements'):
        if snapshot.get(key,0)>0:emit(key,'critical')
    if snapshot.get('tasks',{}).get('uncertain',0)>0 and (snapshot.get('unknown_oldest_seconds') or 0)>=thresholds.unknown_seconds:emit('unknown_backlog','warning')
    if snapshot.get('outbox_pending',0)>0 and (snapshot.get('outbox_oldest_seconds') or 0)>=thresholds.outbox_seconds:emit('outbox_lag','warning')
    if snapshot.get('expired_leases',0)>0:emit('expired_task_lease','warning')
    for component in ('publisher','worker'):
        age=snapshot.get('heartbeat_age_seconds',{}).get(component)
        if age is None or age>=thresholds.heartbeat_seconds:emit(component+'_heartbeat_missing','critical')
    for component,status in (dependencies or {}).items():
        if status!='ready':emit(component+'_unavailable','critical')
    return result

def prometheus(snapshot,thresholds=Thresholds(),dependencies=None):
    values=['visual_monitor_scrape_error 0']
    def gauge(name,value,labels=''):
        if value is None:return
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value):raise ValueError('invalid metric value')
        values.append('visual_'+name+labels+' '+str(value))
    for status in ('queued','processing','uncertain','succeeded','failed','cancelled'):gauge('tasks',snapshot.get('tasks',{}).get(status,0),'{status="'+status+'"}')
    for key in ('outbox_pending','outbox_oldest_seconds','unknown_oldest_seconds','queued_oldest_seconds','expired_leases','manual_dispatch','wallet_equation_errors','ledger_total_errors','reservation_link_errors','task_credit_state_errors','duplicate_terminal_settlements'):gauge(key,snapshot.get(key))
    for component in ('publisher','worker'):
        age=snapshot.get('heartbeat_age_seconds',{}).get(component)
        gauge('service_alive',int(age is not None and age<thresholds.heartbeat_seconds),'{component="'+component+'"}')
        gauge('heartbeat_age_seconds',age,'{component="'+component+'"}')
    gauge('task_duration_24h_samples',snapshot.get('task_duration_24h',{}).get('samples',0))
    gauge('task_duration_24h_p95_seconds',snapshot.get('task_duration_24h',{}).get('p95_seconds'))
    for component in ('mq','storage'):
        if dependencies is not None:gauge('dependency_up',int(dependencies.get(component)=='ready'),'{component="'+component+'"}')
    return '\n'.join(values)+'\n'
