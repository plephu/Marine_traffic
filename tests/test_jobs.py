"""Kiem thu job runner va API web, chay offline bang du lieu demo."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vnports.jobs import JobStore, job_rows, run_job
from vnports.tables import best_table

DEMO_PARAMS = {"demo": True, "days": 30, "from_days": 0,
               "ports": ["all"], "kinds": ["port_authority"], "sources": ["all"]}


class TestDemoData(unittest.TestCase):
    def test_demo_html_parses_and_lands_in_window(self):
        from vnports.demo import demo_html

        rows = best_table(demo_html("https://vi.du/test?d=0"))
        self.assertGreaterEqual(len(rows), 5)
        self.assertTrue(all(row.get("vessel_name") for row in rows))
        self.assertTrue(all(row.get("eta") for row in rows))


class TestJobRunner(unittest.TestCase):
    def setUp(self):
        self.store = JobStore()

    def test_demo_job_produces_results(self):
        job = run_job(self.store.create(dict(DEMO_PARAMS)))
        self.assertEqual(job.status, "done")
        self.assertGreater(len(job.results), 0)
        self.assertEqual(job.progress, 100.0)
        self.assertEqual(job.done_sources, job.total_sources)
        self.assertGreaterEqual(job.stats["raw_count"], job.stats["merged_count"])
        # Moi ket qua phai nam trong cua so ETA da yeu cau
        for arrival in job.results:
            self.assertIsNotNone(arrival.eta)
            self.assertGreaterEqual(arrival.eta.isoformat(), job.stats["window_start"])
            self.assertLessEqual(arrival.eta.isoformat(), job.stats["window_end"])

    def test_rows_carry_merge_info(self):
        job = run_job(self.store.create(dict(DEMO_PARAMS, kinds=["all"])))
        rows = job_rows(job)
        self.assertEqual(len(rows), len(job.results))
        self.assertIn("merged_sources", rows[0])
        # Nhieu nguon cung mo ta mot tau -> phai co it nhat mot dong duoc gop
        self.assertTrue(any(row["merged_sources"] for row in rows))

    def test_invalid_params_mark_job_error(self):
        job = run_job(self.store.create(dict(DEMO_PARAMS, ports=["khong-ton-tai"])))
        self.assertEqual(job.status, "error")
        self.assertIn("Khong khop cang", job.message)

    def test_cancel_before_run(self):
        job = self.store.create(dict(DEMO_PARAMS))
        self.assertTrue(self.store.cancel(job.id))
        run_job(job)
        self.assertEqual(job.status, "cancelled")
        self.assertEqual(job.results, [])

    def test_store_evicts_oldest(self):
        store = JobStore(max_jobs=3)
        ids = [store.create({}).id for _ in range(5)]
        self.assertIsNone(store.get(ids[0]))
        self.assertIsNotNone(store.get(ids[-1]))
        self.assertEqual(len(store.list()), 3)


class TestWebApi(unittest.TestCase):
    """Kiem thu API bang TestClient; bo qua neu chua cai fastapi/httpx."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient

            from webapp.server import app
        except Exception as exc:
            raise unittest.SkipTest("thieu fastapi/httpx: %s" % exc)
        cls.client = TestClient(app)

    def test_config_lists_ports_and_sources(self):
        data = self.client.get("/api/config").json()
        self.assertGreaterEqual(len(data["ports"]), 5)
        self.assertGreaterEqual(len(data["sources"]), 20)
        self.assertIn("kind", data["sources"][0])

    def test_job_lifecycle(self):
        created = self.client.post("/api/jobs", json=dict(DEMO_PARAMS)).json()
        job_id = created["id"]
        for _ in range(200):
            status = self.client.get("/api/jobs/%s" % job_id).json()
            if status["status"] in ("done", "error", "cancelled"):
                break
        self.assertEqual(status["status"], "done")
        self.assertGreater(status["result_count"], 0)

        results = self.client.get("/api/jobs/%s/results" % job_id).json()
        self.assertEqual(results["count"], status["result_count"])
        self.assertIn("vessel_name", results["rows"][0])

        csv_response = self.client.get("/api/jobs/%s/results.csv" % job_id)
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("vessel_name", csv_response.text.splitlines()[0])

    def test_bad_window_rejected(self):
        response = self.client.post("/api/jobs", json=dict(DEMO_PARAMS, days=1, from_days=5))
        self.assertEqual(response.status_code, 400)

    def test_unknown_job_returns_404(self):
        self.assertEqual(self.client.get("/api/jobs/khongcothat").status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
