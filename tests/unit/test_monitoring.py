import unittest
from visual_platform.services.monitoring import Thresholds,alerts,prometheus

class MonitoringTests(unittest.TestCase):
    def healthy(self):return {'tasks':{},'outbox_pending':0,'heartbeat_age_seconds':{'publisher':1,'worker':1},'task_duration_24h':{'samples':0,'p95_seconds':None}}
    def test_healthy_no_samples_does_not_invent_latency(self):
        value=self.healthy();self.assertEqual(alerts(value),[]);text=prometheus(value)
        self.assertNotIn('None',text);self.assertNotIn('p95_seconds',text);self.assertIn('visual_task_duration_24h_samples 0',text)
    def test_unknown_and_outbox_alerts_are_read_only_warnings(self):
        value=self.healthy();value.update(tasks={'uncertain':1},unknown_oldest_seconds=301,outbox_pending=1,outbox_oldest_seconds=31)
        result=alerts(value);self.assertEqual({r['code'] for r in result},{'unknown_backlog','outbox_lag'});self.assertTrue(all(r['severity']=='warning' for r in result));self.assertEqual(value['tasks']['uncertain'],1)
    def test_ledger_and_dependency_failure_are_critical(self):
        value=self.healthy();value['ledger_total_errors']=1
        self.assertEqual({x['code'] for x in alerts(value,dependencies={'mq':'unavailable','storage':'ready'})},{'ledger_total_errors','mq_unavailable'})
        self.assertTrue(all(x['severity']=='critical' for x in alerts(value,dependencies={'mq':'unavailable'})))
    def test_missing_and_stale_heartbeat(self):
        value=self.healthy();value['heartbeat_age_seconds']={'worker':16}
        self.assertEqual({x['code'] for x in alerts(value)},{'publisher_heartbeat_missing','worker_heartbeat_missing'})
    def test_invalid_thresholds_and_nonfinite_metrics_rejected(self):
        for v in (True,0,-1,float('inf'),float('nan')):
            with self.assertRaises(ValueError):Thresholds(unknown_seconds=v)
        value=self.healthy();value['outbox_pending']=float('nan')
        with self.assertRaises(ValueError):prometheus(value)
    def test_only_fixed_low_cardinality_labels_are_exported(self):
        value=self.healthy();value['tasks']['user-secret-label']=2;value['heartbeat_age_seconds']['private-instance-id']=1
        output=prometheus(value,dependencies={'mq':'ready','storage':'ready'});self.assertNotIn('secret',output);self.assertNotIn('private',output);self.assertIn('visual_dependency_up{component="mq"} 1',output)
