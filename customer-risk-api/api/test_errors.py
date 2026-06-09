import os
import unittest

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY", "")


class TestErrorStates(unittest.TestCase):
    def test_no_api_key_returns_401(self):
        r = requests.get(f"{BASE_URL}/customers/CUST-001")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["detail"], "Unauthorized")

    def test_wrong_api_key_returns_401(self):
        r = requests.get(f"{BASE_URL}/customers/CUST-001", headers={"X-API-Key": "wrong-key"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["detail"], "Unauthorized")

    def test_empty_api_key_returns_401(self):
        r = requests.get(f"{BASE_URL}/customers/CUST-001", headers={"X-API-Key": ""})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["detail"], "Unauthorized")

    def test_nonexistent_customer_returns_404(self):
        r = requests.get(f"{BASE_URL}/customers/CUST-999", headers={"X-API-Key": API_KEY})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"], "Customer not found")

    def test_401_bodies_are_identical(self):
        r_no_key = requests.get(f"{BASE_URL}/customers/CUST-001")
        r_wrong_key = requests.get(f"{BASE_URL}/customers/CUST-001", headers={"X-API-Key": "wrong-key"})
        self.assertEqual(r_no_key.json(), r_wrong_key.json())


if __name__ == "__main__":
    unittest.main()
