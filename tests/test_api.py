from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api.main import app


class ApiEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def get_json(self, path: str, **params):
        response = self.client.get(path, params=params or None)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def post_json(self, path: str, payload: dict):
        response = self.client.post(path, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_root_lists_finalized_endpoints(self) -> None:
        payload = self.get_json("/")
        self.assertIn("GET /rdd/group-comparison", payload["endpoints"])
        self.assertIn("GET /town-premiums/{town_name}", payload["endpoints"])
        self.assertIn("POST /predict", payload["endpoints"])

    def test_health_endpoint(self) -> None:
        payload = self.get_json("/health")
        self.assertEqual(payload["status"], "ok")

    def test_metadata_endpoint(self) -> None:
        payload = self.get_json("/metadata")
        self.assertIn("data_dir", payload)
        self.assertGreater(payload["feature_dataset_rows"], 0)
        self.assertGreaterEqual(payload["rdd_group_comparison_rows"], 0)

    def test_resales_schema_endpoint(self) -> None:
        payload = self.get_json("/resales/schema")
        self.assertIn("available_columns", payload)
        self.assertIn("town", payload["supported_filters"]["categorical_multi"])
        self.assertIn("town", payload["supported_group_by"])

    def test_resales_raw_endpoint(self) -> None:
        payload = self.get_json("/resales/raw", limit=5)
        self.assertLessEqual(payload["count"], 5)
        self.assertIn("rows", payload)

    def test_resales_summary_endpoint(self) -> None:
        payload = self.get_json("/resales/summary", group_by="town")
        self.assertIn("summary", payload)
        self.assertIn("grouped_rows", payload)

    def test_model_metrics_endpoint(self) -> None:
        payload = self.get_json("/model/metrics")
        self.assertIsInstance(payload, dict)
        self.assertGreater(len(payload), 0)

    def test_model_feature_importance_endpoint(self) -> None:
        payload = self.get_json("/model/feature-importance", limit=10)
        self.assertLessEqual(payload["count"], 10)
        self.assertIn("rows", payload)

    def test_model_coefficients_endpoints(self) -> None:
        listing = self.get_json("/model/coefficients", limit=5)
        self.assertGreater(listing["count"], 0)
        first_term = listing["rows"][0]["term"]
        detail = self.get_json(f"/model/coefficients/{first_term}")
        self.assertEqual(detail["row"]["term"], first_term)

    def test_predict_schema_endpoint(self) -> None:
        payload = self.get_json("/predict/schema")
        self.assertIn("raw_request_fields", payload)
        self.assertIn("defaults_used_when_omitted", payload)
        self.assertIn("month", payload["raw_request_fields"])

    def test_predict_endpoint(self) -> None:
        payload = self.post_json(
            "/predict",
            {
                "town": "TAMPINES",
                "flat_type": "4 ROOM",
            },
        )
        self.assertEqual(payload["currency"], "SGD")
        self.assertGreater(payload["predicted_price"], 0)
        self.assertTrue(payload["used_defaults"])
        self.assertIn("town", payload["provided_raw_fields"])

    def test_rdd_summary_endpoint(self) -> None:
        payload = self.get_json("/rdd/summary")
        self.assertIsInstance(payload, dict)
        self.assertGreater(len(payload), 0)

    def test_rdd_schools_endpoint(self) -> None:
        payload = self.get_json("/rdd/schools")
        self.assertIn("rows", payload)
        self.assertGreaterEqual(payload["count"], 0)

    def test_rdd_results_endpoints(self) -> None:
        listing = self.get_json("/rdd/results", limit=5)
        self.assertGreater(listing["count"], 0)
        school_name = listing["rows"][0]["boundary_school_name"]
        detail = self.get_json(f"/rdd/results/{school_name}")
        self.assertGreater(detail["count"], 0)

    def test_rdd_coefficients_endpoint(self) -> None:
        payload = self.get_json("/rdd/coefficients", limit=5)
        self.assertGreaterEqual(payload["count"], 0)
        self.assertIn("rows", payload)

    def test_rdd_group_comparison_endpoints(self) -> None:
        results = self.get_json("/rdd/group-comparison")
        coefficients = self.get_json("/rdd/group-comparison/coefficients", limit=5)
        self.assertGreater(results["count"], 0)
        self.assertIn("rows", coefficients)

    def test_rdd_skipped_endpoint(self) -> None:
        payload = self.get_json("/rdd/skipped")
        self.assertIn("rows", payload)
        self.assertGreaterEqual(payload["count"], 0)

    def test_town_premium_endpoints(self) -> None:
        summary = self.get_json("/town-premiums/summary")
        listing = self.get_json("/town-premiums", limit=5)
        skipped = self.get_json("/town-premiums/skipped")
        self.assertIn("count", summary)
        self.assertGreater(listing["count"], 0)
        self.assertIn("rows", skipped)
        town_name = listing["rows"][0]["town"]
        detail = self.get_json(f"/town-premiums/{town_name}")
        self.assertEqual(detail["row"]["town"], town_name)

    def test_diagnostics_endpoint(self) -> None:
        payload = self.get_json("/diagnostics/sign-trace")
        self.assertIn("rows", payload)
        self.assertGreater(payload["count"], 0)

    def test_benchmark_endpoints(self) -> None:
        summary = self.get_json("/benchmarks/summary")
        results = self.get_json("/benchmarks/results", limit=5)
        best = self.get_json("/benchmarks/best")
        metadata = self.get_json("/benchmarks/metadata")
        self.assertIn("variant_count", summary)
        self.assertGreater(results["count"], 0)
        self.assertIn("best_by_test_r2_log", best)
        self.assertIsInstance(metadata, dict)


if __name__ == "__main__":
    unittest.main()
