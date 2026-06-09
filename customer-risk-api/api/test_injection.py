import os
import subprocess
import unittest

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY", "")

PAYLOADS = [
    "'; DROP TABLE customer_risk_profiles; --",
    "' OR '1'='1",
    "' UNION SELECT null, null, null --",
    "1; SELECT * FROM customer_risk_profiles",
    ("SELECT DROP TABLE INSERT UPDATE DELETE " * 20)[:500],
]


def _get_row_count():
    result = subprocess.run(
        ["docker", "compose", "exec", "db", "psql",
         "-U", os.environ.get("POSTGRES_USER", "postgres"),
         "-d", os.environ.get("POSTGRES_DB", "customer-risk-api"),
         "-t", "-c", "SELECT COUNT(*) FROM customer_risk_profiles"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__))
    )
    return int(result.stdout.strip())


class TestSQLInjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pre_count = _get_row_count()

    def _assert_404(self, payload):
        r = requests.get(
            f"{BASE_URL}/customers/{payload}",
            headers={"X-API-Key": API_KEY},
        )
        self.assertNotEqual(r.status_code, 500, f"Got 500 for payload: {payload!r}")
        self.assertNotEqual(r.status_code, 200, f"Got 200 for payload: {payload!r}")
        self.assertEqual(r.status_code, 404, f"Expected 404, got {r.status_code}")

    def test_payload_1_drop_table(self):
        self._assert_404(PAYLOADS[0])

    def test_payload_2_or_true(self):
        self._assert_404(PAYLOADS[1])

    def test_payload_3_union_select(self):
        self._assert_404(PAYLOADS[2])

    def test_payload_4_stacked_query(self):
        self._assert_404(PAYLOADS[3])

    def test_payload_5_long_keyword_string(self):
        self._assert_404(PAYLOADS[4])

    def test_row_count_unchanged(self):
        post_count = _get_row_count()
        self.assertEqual(
            post_count,
            self.__class__.pre_count,
            f"Row count changed: was {self.__class__.pre_count}, now {post_count}",
        )


if __name__ == "__main__":
    unittest.main()
