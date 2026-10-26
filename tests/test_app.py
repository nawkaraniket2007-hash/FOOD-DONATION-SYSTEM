import os
import tempfile
import unittest
from datetime import datetime, timedelta

# Set a temporary database before importing app.
_tmp = tempfile.TemporaryDirectory()
os.environ["FOOD_DONATION_DB"] = os.path.join(_tmp.name, "test.db")

import app as donation_app


class FoodDonationTests(unittest.TestCase):
    def setUp(self):
        donation_app.app.config["TESTING"] = True
        self.client = donation_app.app.test_client()
        donation_app.init_db()

    def valid_donation(self, **overrides):
        data = {
            "food_name": "Vegetable Rice",
            "category": "Cooked Meals",
            "quantity": 10,
            "unit": "servings",
            "expiry_datetime": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "pickup_location": "Nagpur",
            "donor_name": "Test Donor",
            "donor_contact": "1234567890",
            "notes": "Sample"
        }
        data.update(overrides)
        return data

    def create_donation(self):
        response = self.client.post("/api/donations", json=self.valid_donation())
        self.assertEqual(response.status_code, 201)
        return response.get_json()["donation"]["id"]

    def test_create_and_list_donation(self):
        self.create_donation()
        response = self.client.get("/api/donations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), 1)

    def test_reject_zero_quantity(self):
        response = self.client.post("/api/donations", json=self.valid_donation(quantity=0))
        self.assertEqual(response.status_code, 400)

    def test_reject_expired_donation(self):
        past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post("/api/donations", json=self.valid_donation(expiry_datetime=past))
        self.assertEqual(response.status_code, 400)

    def test_edit_available_donation(self):
        donation_id = self.create_donation()
        data = self.valid_donation(food_name="Updated Rice")
        response = self.client.put(f"/api/donations/{donation_id}", json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["donation"]["food_name"], "Updated Rice")

    def test_request_reserves_donation_and_reject_restores_availability(self):
        donation_id = self.create_donation()
        response = self.client.post(
            f"/api/donations/{donation_id}/requests",
            json={"recipient_name": "Test Recipient", "recipient_contact": "1234567890"}
        )
        self.assertEqual(response.status_code, 201)
        request_id = response.get_json()["request"]["id"]

        duplicate = self.client.post(
            f"/api/donations/{donation_id}/requests",
            json={"recipient_name": "Another Recipient", "recipient_contact": "1234567890"}
        )
        self.assertEqual(duplicate.status_code, 409)

        decision = self.client.patch(f"/api/requests/{request_id}/decision", json={"action": "reject"})
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.get_json()["request"]["donation_status"], "Available")

    def test_only_approved_request_can_complete(self):
        donation_id = self.create_donation()
        created = self.client.post(
            f"/api/donations/{donation_id}/requests",
            json={"recipient_name": "Test Recipient", "recipient_contact": "1234567890"}
        )
        request_id = created.get_json()["request"]["id"]
        pending_complete = self.client.patch(
            f"/api/requests/{request_id}/decision", json={"action": "complete"}
        )
        self.assertEqual(pending_complete.status_code, 409)

        approved = self.client.patch(
            f"/api/requests/{request_id}/decision", json={"action": "approve"}
        )
        self.assertEqual(approved.status_code, 200)
        completed = self.client.patch(
            f"/api/requests/{request_id}/decision", json={"action": "complete"}
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.get_json()["request"]["status"], "Completed")
        self.assertEqual(completed.get_json()["request"]["donation_status"], "Completed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
