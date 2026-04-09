from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api.main import app


class ApiIntegrationTests(unittest.TestCase):
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

    def test_metadata_counts_align_with_core_endpoints(self) -> None:
        metadata = self.get_json("/metadata")
        feature_importance = self.get_json("/model/feature-importance", limit=1000)
        rdd_results = self.get_json("/rdd/results", limit=5000)
        town_premiums = self.get_json("/town-premiums", limit=1000)
        diagnostics = self.get_json("/diagnostics/sign-trace")
        benchmarks = self.get_json("/benchmarks/results", limit=1000)

        self.assertEqual(metadata["feature_importance_rows"], feature_importance["count"])
        self.assertEqual(metadata["rdd_result_rows"], rdd_results["count"])
        self.assertEqual(metadata["town_premium_rows"], town_premiums["count"])
        self.assertEqual(metadata["sign_trace_rows"], diagnostics["count"])
        self.assertEqual(metadata["benchmark_rows"], benchmarks["count"])

    def test_resales_raw_and_summary_are_consistent_for_same_filter(self) -> None:
        raw = self.get_json("/resales/raw", town="TAMPINES", limit=50)
        summary = self.get_json("/resales/summary", town="TAMPINES")

        self.assertGreaterEqual(summary["summary"]["count"], raw["count"])
        self.assertEqual(raw["dataset_kind"], summary["dataset_kind"])
        self.assertEqual(raw["dataset_path"], summary["dataset_path"])

    def test_predict_schema_and_prediction_defaults_work_together(self) -> None:
        schema = self.get_json("/predict/schema")
        prediction = self.post_json("/predict", {"flat_type": "4 ROOM"})

        self.assertIn("flat_type", schema["raw_request_fields"])
        self.assertTrue(prediction["used_defaults"])
        self.assertIn("flat_type", prediction["provided_raw_fields"])
        self.assertGreater(len(prediction["defaulted_raw_fields"]), 0)
        self.assertGreater(prediction["predicted_price"], 0)

    def test_rdd_school_detail_matches_listing_filter(self) -> None:
        listing = self.get_json("/rdd/results", limit=20)
        self.assertGreater(listing["count"], 0)

        school_name = listing["rows"][0]["boundary_school_name"]
        filtered = self.get_json("/rdd/results", school_name=school_name, limit=5000)
        detail = self.get_json(f"/rdd/results/{school_name}")

        self.assertEqual(filtered["count"], detail["count"])
        self.assertTrue(all(row["boundary_school_name"] == school_name for row in detail["rows"]))

    def test_rdd_group_comparison_summary_and_coefficients_share_filters(self) -> None:
        comparison = self.get_json("/rdd/group-comparison")
        self.assertGreater(comparison["count"], 0)

        first_row = comparison["rows"][0]
        specification = first_row.get("specification")
        bandwidth = first_row.get("bandwidth_m")

        filtered_comparison = self.get_json(
            "/rdd/group-comparison",
            specification=specification,
            bandwidth_m=bandwidth,
        )
        filtered_coefficients = self.get_json(
            "/rdd/group-comparison/coefficients",
            specification=specification,
            bandwidth_m=bandwidth,
            limit=5000,
        )

        self.assertGreater(filtered_comparison["count"], 0)
        self.assertGreater(filtered_coefficients["count"], 0)

    def test_town_premium_detail_matches_listing(self) -> None:
        listing = self.get_json("/town-premiums", limit=20)
        self.assertGreater(listing["count"], 0)

        town_name = listing["rows"][0]["town"]
        detail = self.get_json(f"/town-premiums/{town_name}")

        self.assertEqual(detail["row"]["town"], town_name)

    def test_benchmark_best_is_consistent_with_results(self) -> None:
        results = self.get_json("/benchmarks/results", limit=1000)
        best = self.get_json("/benchmarks/best")

        rows = results["rows"]
        best_r2_variant = max(rows, key=lambda row: float(row["test_r2_log"]))["variant"]
        best_rmse_variant = min(rows, key=lambda row: float(row["test_rmse_sgd"]))["variant"]
        best_mae_variant = min(rows, key=lambda row: float(row["test_mae_sgd"]))["variant"]

        self.assertEqual(best["best_by_test_r2_log"]["variant"], best_r2_variant)
        self.assertEqual(best["best_by_test_rmse_sgd"]["variant"], best_rmse_variant)
        self.assertEqual(best["best_by_test_mae_sgd"]["variant"], best_mae_variant)


if __name__ == "__main__":
    unittest.main()
