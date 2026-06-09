import json
import os
import subprocess
import time
import unittest

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY", "")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "customer-risk-api")
COMPOSE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INJECTION_PAYLOADS = [
    "'; DROP TABLE customer_risk_profiles; --",
    "' OR '1'='1",
    "' UNION SELECT null, null, null --",
    "1; SELECT * FROM customer_risk_profiles",
    ("SELECT DROP TABLE INSERT UPDATE DELETE " * 20)[:500],
]


def _psql(query):
    result = subprocess.run(
        ["docker", "compose", "exec", "db", "psql",
         "-U", POSTGRES_USER, "-d", POSTGRES_DB, "-t", "-A", "-c", query],
        capture_output=True, text=True, cwd=COMPOSE_DIR,
    )
    return result.stdout.strip()


def _get_row_count():
    return int(_psql("SELECT COUNT(*) FROM customer_risk_profiles"))


def _get_db_row(customer_id):
    raw = _psql(
        "SELECT row_to_json(t) FROM "
        f"(SELECT customer_id, risk_tier, risk_factors "
        f"FROM customer_risk_profiles WHERE customer_id = '{customer_id}') t"
    )
    return json.loads(raw)


class TestInv01DataCorrectness(unittest.TestCase):
    """INV-01: API response values match database rows exactly for all three fields."""

    def _check_customer(self, customer_id):
        db_row = _get_db_row(customer_id)
        r = requests.get(f"{BASE_URL}/customers/{customer_id}", headers={"X-API-Key": API_KEY})
        self.assertEqual(r.status_code, 200)
        api = r.json()
        self.assertEqual(api["customer_id"], db_row["customer_id"])
        self.assertEqual(api["risk_tier"], db_row["risk_tier"])
        self.assertEqual(api["risk_factors"], db_row["risk_factors"])

    def test_cust_001_matches_db(self):
        self._check_customer("CUST-001")

    def test_cust_004_matches_db(self):
        self._check_customer("CUST-004")

    def test_cust_007_matches_db(self):
        self._check_customer("CUST-007")


class TestInv02StatusCodes(unittest.TestCase):
    """INV-02: Existing ID → 200; non-existent ID → 404; no other codes for these cases."""

    def test_existing_customer_returns_200(self):
        r = requests.get(f"{BASE_URL}/customers/CUST-001", headers={"X-API-Key": API_KEY})
        self.assertEqual(r.status_code, 200)

    def test_nonexistent_customer_returns_404(self):
        r = requests.get(f"{BASE_URL}/customers/CUST-999", headers={"X-API-Key": API_KEY})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"], "Customer not found")


class TestInv03NoWrites(unittest.TestCase):
    """INV-03: Row count is unchanged after a full set of API requests."""

    @classmethod
    def setUpClass(cls):
        cls.pre_count = _get_row_count()

    def test_row_count_unchanged_after_requests(self):
        for cid in ["CUST-001", "CUST-004", "CUST-007", "CUST-999"]:
            requests.get(f"{BASE_URL}/customers/{cid}", headers={"X-API-Key": API_KEY})
        post_count = _get_row_count()
        self.assertEqual(post_count, self.__class__.pre_count)


class TestInv04InjectionBlocked(unittest.TestCase):
    """INV-04: Injection payloads return 404 or 401, never 500."""

    def _assert_not_500_or_200(self, payload):
        r = requests.get(
            f"{BASE_URL}/customers/{payload}",
            headers={"X-API-Key": API_KEY},
        )
        self.assertNotEqual(r.status_code, 500, f"Got 500 for payload: {payload!r}")
        self.assertNotEqual(r.status_code, 200, f"Got 200 for payload: {payload!r}")

    def test_drop_table_payload(self):
        self._assert_not_500_or_200(INJECTION_PAYLOADS[0])

    def test_or_true_payload(self):
        self._assert_not_500_or_200(INJECTION_PAYLOADS[1])

    def test_union_select_payload(self):
        self._assert_not_500_or_200(INJECTION_PAYLOADS[2])

    def test_stacked_query_payload(self):
        self._assert_not_500_or_200(INJECTION_PAYLOADS[3])

    def test_long_keyword_string_payload(self):
        self._assert_not_500_or_200(INJECTION_PAYLOADS[4])


class TestInv05ResponseShape(unittest.TestCase):
    """INV-05: Every 200 response has exactly three keys with correct types."""

    def _check_shape(self, customer_id):
        r = requests.get(f"{BASE_URL}/customers/{customer_id}", headers={"X-API-Key": API_KEY})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(set(body.keys()), {"customer_id", "risk_tier", "risk_factors"})
        self.assertIsInstance(body["customer_id"], str)
        self.assertIsInstance(body["risk_tier"], str)
        self.assertIsInstance(body["risk_factors"], list)

    def test_cust_001_shape(self):
        self._check_shape("CUST-001")

    def test_cust_004_shape(self):
        self._check_shape("CUST-004")

    def test_cust_007_shape(self):
        self._check_shape("CUST-007")


class TestInv06RiskTierValues(unittest.TestCase):
    """INV-06: risk_tier is always LOW, MEDIUM, or HIGH — uppercase, unchanged from DB."""

    VALID_TIERS = {"LOW", "MEDIUM", "HIGH"}

    def _check_tier(self, customer_id):
        r = requests.get(f"{BASE_URL}/customers/{customer_id}", headers={"X-API-Key": API_KEY})
        self.assertEqual(r.status_code, 200)
        self.assertIn(r.json()["risk_tier"], self.VALID_TIERS)

    def test_cust_001_tier_valid(self):
        self._check_tier("CUST-001")

    def test_cust_004_tier_valid(self):
        self._check_tier("CUST-004")

    def test_cust_007_tier_valid(self):
        self._check_tier("CUST-007")


class TestInv07AuthBeforeDB(unittest.TestCase):
    """INV-07: Unauthenticated request returns 401; row count unchanged (proxy check).
    Definitive check: code review confirming verify_api_key is Depends before DB access."""

    def test_no_key_returns_401_row_count_unchanged(self):
        pre = _get_row_count()
        r = requests.get(f"{BASE_URL}/customers/CUST-001")
        self.assertEqual(r.status_code, 401)
        post = _get_row_count()
        self.assertEqual(post, pre)


class TestInv08KeyNotInResponse(unittest.TestCase):
    """INV-08: 401 detail string does not contain the submitted key value."""

    def test_submitted_key_absent_from_401_body(self):
        submitted = "probe-key-that-must-not-appear"
        r = requests.get(f"{BASE_URL}/customers/CUST-001", headers={"X-API-Key": submitted})
        self.assertEqual(r.status_code, 401)
        self.assertNotIn(submitted, r.text)


class TestInv09InternalErrorIsolation(unittest.TestCase):
    """INV-09: DB down returns exactly {"detail": "Internal server error"} with no internal detail."""

    @classmethod
    def setUpClass(cls):
        subprocess.run(
            ["docker", "compose", "stop", "db"],
            cwd=COMPOSE_DIR, capture_output=True,
        )
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        subprocess.run(
            ["docker", "compose", "start", "db"],
            cwd=COMPOSE_DIR, capture_output=True,
        )
        time.sleep(10)

    def test_db_down_returns_500_static_literal(self):
        r = requests.get(f"{BASE_URL}/customers/CUST-001", headers={"X-API-Key": API_KEY})
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.json(), {"detail": "Internal server error"})

    def test_db_down_no_internal_detail_in_body(self):
        r = requests.get(f"{BASE_URL}/customers/CUST-001", headers={"X-API-Key": API_KEY})
        body = r.text
        self.assertNotIn("psycopg2", body)
        self.assertNotIn("customer_risk_profiles", body)
        self.assertNotIn("Traceback", body)


class TestInv12IdenticalUnauthorizedBodies(unittest.TestCase):
    """INV-12: Wrong key and missing key return identical response bodies."""

    def test_wrong_key_and_no_key_bodies_identical(self):
        r_no_key = requests.get(f"{BASE_URL}/customers/CUST-001")
        r_wrong_key = requests.get(
            f"{BASE_URL}/customers/CUST-001", headers={"X-API-Key": "wrong-key"}
        )
        self.assertEqual(r_no_key.json(), r_wrong_key.json())


class TestInv13HealthShape(unittest.TestCase):
    """INV-13: GET /health returns exactly {"status": "ok"} — one key, no extras."""

    def test_health_has_exactly_one_key(self):
        r = requests.get(f"{BASE_URL}/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(list(body.keys()), ["status"])
        self.assertEqual(body["status"], "ok")


if __name__ == "__main__":
    unittest.main()
