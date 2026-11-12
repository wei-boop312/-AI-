"""Opt-in native PostgreSQL smoke; requires disposable database and privileged migration role."""
import os
import unittest
import psycopg
class NativeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"),"native PostgreSQL not configured")
    def test_rls_catalog(self):
        with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as conn:
            rows=conn.execute("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='app' AND c.relkind IN ('r','p')").fetchall()
            self.assertTrue(rows)
            self.assertTrue(all(r[1] and r[2] for r in rows))
