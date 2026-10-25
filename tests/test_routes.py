"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase
from tests.factories import AccountFactory
from service.common import status  # HTTP Status Codes
from service.models import db, Account, init_db
from service.routes import app

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)

BASE_URL = "/accounts"


######################################################################
#  T E S T   C A S E S
######################################################################
class TestAccountService(TestCase):
    """Account Service Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Runs once before test suite"""

    def setUp(self):
        """Runs before each test"""
        db.session.query(Account).delete()  # clean up the last tests
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Runs once after each test case"""
        db.session.remove()

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_accounts(self, count):
        """Factory method to create accounts in bulk"""
        accounts = []
        for _ in range(count):
            account = AccountFactory()
            response = self.client.post(BASE_URL, json=account.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test Account",
            )
            new_account = response.get_json()
            account.id = new_account["id"]
            accounts.append(account)
        return accounts

    ######################################################################
    #  A C C O U N T   T E S T   C A S E S
    ######################################################################

    def test_index(self):
        """It should get 200_OK from the Home Page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health(self):
        """It should be healthy"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "OK")

    def test_create_account(self):
        """It should Create a new Account"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL, json=account.serialize(), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_account = response.get_json()
        self.assertEqual(new_account["name"], account.name)
        self.assertEqual(new_account["email"], account.email)
        self.assertEqual(new_account["address"], account.address)
        self.assertEqual(new_account["phone_number"], account.phone_number)
        self.assertEqual(new_account["date_joined"], str(account.date_joined))

    def test_bad_request(self):
        """It should not Create an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_media_type(self):
        """It should not Create an Account when sending the wrong media type"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL, json=account.serialize(), content_type="test/html"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # ADD YOUR TEST CASES HERE ...

    def test_read_account(self):
        """It should read a created account through its Location URL"""
        response = self.client.post(BASE_URL, json=AccountFactory().serialize())
        found = self.client.get(response.headers["Location"])
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.get_json(), response.get_json())

    def test_read_missing(self):
        """It should return 404 for an unknown account"""
        self.assertEqual(self.client.get("/accounts/99999").status_code, 404)

    def test_list_accounts(self):
        """It should list every account"""
        accounts = self._create_accounts(3)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {a["id"] for a in response.get_json()}, {a.id for a in accounts}
        )

    def test_list_empty(self):
        """It should return an empty list when there are no accounts"""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_update_account(self):
        """It should persist updates without changing the account ID"""
        account = self._create_accounts(1)[0]
        data = account.serialize()
        data["name"] = "Updated Customer"
        data["id"] = 99999
        url = f"{BASE_URL}/{account.id}"
        response = self.client.put(url, json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["id"], account.id)
        self.assertEqual(self.client.get(url).get_json()["name"], data["name"])

    def test_update_missing(self):
        """It should not create an account when updating a missing ID"""
        response = self.client.put("/accounts/99999", json=AccountFactory().serialize())
        self.assertEqual(response.status_code, 404)

    def test_update_bad_request(self):
        """It should reject incomplete update data"""
        account = self._create_accounts(1)[0]
        response = self.client.put(f"{BASE_URL}/{account.id}", json={})
        self.assertEqual(response.status_code, 400)

    def test_delete_account(self):
        """It should delete an account and allow repeated deletes"""
        account = self._create_accounts(1)[0]
        url = f"{BASE_URL}/{account.id}"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_default_date(self):
        """It should accept missing optional phone and date fields"""
        data = {
            "name": "Example",
            "email": "example@example.com",
            "address": "123 Example Street",
        }
        response = self.client.post(BASE_URL, json=data)
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.get_json()["phone_number"])
        self.assertIsNotNone(response.get_json()["date_joined"])

    def test_invalid_date(self):
        """It should return 400 for an invalid ISO date"""
        data = AccountFactory().serialize()
        data["date_joined"] = "invalid"
        self.assertEqual(self.client.post(BASE_URL, json=data).status_code, 400)

    def test_security_headers(self):
        """It should apply protective headers"""
        response = self.client.get("/health")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])

    def test_cors(self):
        """It should support CORS preflight for the account API"""
        response = self.client.options(
            BASE_URL,
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"], "https://example.com"
        )
        self.assertIn("POST", response.headers["Access-Control-Allow-Methods"])

    def test_method_not_allowed(self):
        """It should return a JSON error for unsupported methods"""
        response = self.client.patch(BASE_URL)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json()["status"], 405)

    def test_server_error(self):
        """It should return JSON when the database fails"""
        from unittest.mock import patch

        with patch(
            "service.routes.Account.all", side_effect=RuntimeError("db unavailable")
        ):
            app.config["PROPAGATE_EXCEPTIONS"] = False
            try:
                response = self.client.get(BASE_URL)
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.get_json()["status"], 500)
            finally:
                app.config["PROPAGATE_EXCEPTIONS"] = None
