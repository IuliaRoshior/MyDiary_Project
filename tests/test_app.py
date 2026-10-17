"""Run: python -m unittest discover -s tests -v"""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from app import DiaryServer


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = DiaryServer(("127.0.0.1", 0), database=str(Path(cls.temp.name) / "test.sqlite3"), seed_demo=False)
        cls.server.quiet = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def call(self, method, path, body=None):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        headers = {"Content-Type": "application/json"}
        client.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
        resp = client.getresponse()
        raw = resp.read()
        status = resp.status
        client.close()
        return status, json.loads(raw) if raw and resp.getheader("Content-Type", "").startswith("application/json") else None

    def add(self, **kwargs):
        return self.call("POST", "/api/tasks", {"title": "Write report", "due_date": "2026-10-20", "priority": "medium", **kwargs})

    def test_01_health_and_empty_stats(self):
        self.assertEqual(self.call("GET", "/api/health")[1]["status"], "ok")
        self.assertEqual(self.call("GET", "/api/stats")[1]["total"], 0)
        self.assertEqual(self.call("GET", "/")[0], 200)
        self.assertEqual(self.call("GET", "/static/css/styles.css")[0], 200)

    def test_02_crud(self):
        status, body = self.add()
        self.assertEqual(status, 201)
        task_id = body["task"]["id"]
        self.assertEqual(self.call("GET", "/api/tasks?date=2026-10-20")[1]["tasks"][0]["id"], task_id)
        self.assertTrue(self.call("PATCH", f"/api/tasks/{task_id}", {"completed":True})[1]["task"]["completed"])
        self.assertGreaterEqual(self.call("GET", "/api/stats")[1]["completed"], 1)
        self.assertEqual(self.call("DELETE", f"/api/tasks/{task_id}")[0], 204)

    def test_03_validation(self):
        self.assertEqual(self.add(title=" ")[0], 400)
        self.assertEqual(self.add(due_date="tomorrow")[0], 400)
        self.assertEqual(self.add(priority="urgent")[0], 400)
        self.assertEqual(self.call("POST", "/api/tasks", {})[0], 400)
        self.assertEqual(self.call("PATCH", "/api/tasks/123", {"completed":"yes"})[0], 400)
        self.assertEqual(self.call("GET", "/api/calendar?month=bad")[0], 400)
        self.assertEqual(self.call("GET", "/static/../../app.py")[0], 404)

    def test_04_filters_and_calendar(self):
        self.add()
        self.add(title="Write summary", priority="high")
        self.assertEqual(len(self.call("GET", "/api/tasks?q=summary")[1]["tasks"]), 1)
        self.assertEqual(self.call("GET", "/api/calendar?month=2026-10")[1]["days"]["2026-10-20"]["total"], 2)
        self.assertEqual(len(self.call("GET", "/api/tasks?status=completed")[1]["tasks"]), 0)


if __name__ == "__main__":
    unittest.main()
