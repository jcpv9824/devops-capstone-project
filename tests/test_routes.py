"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
import sys
from io import StringIO
from unittest import TestCase
from tests.factories import AccountFactory
from service.common import status  # HTTP Status Codes
from service.models import db, Account, init_db
from service.routes import app
import random
from service import talisman

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)

BASE_URL = "/accounts"

HTTPS_ENVIRON = {'wsgi.url_scheme': 'https'}


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
        talisman.force_https = False
        db.session.query(Account).delete()  # clean up the last tests
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Runs once after each test case"""
        db.session.remove()

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_accounts(self, count):#Return a list of instances accounts
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
            account.id = new_account["id"] #The id provided is the same than the id in the database
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
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
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

    def test_read_an_account(self):
        """
        It should read an account from the service using ID.
        """
        # Create a single account
        account_created = self._create_accounts(1)[0]
        account_id = account_created.id

        # Verify the account is correctly created in the setup
        self.assertIsNotNone(Account.find(account_id))

        # Making a GET request to fetch the account
        response = self.client.get(f"{BASE_URL}/{account_id}")
        payload = response.get_json()

        # Asserting the HTTP status and response content
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payload["id"], account_id)
        self.assertEqual(payload["name"], account_created.name)
        self.assertEqual(payload["email"], account_created.email)
        self.assertEqual(payload["address"], account_created.address)
        self.assertEqual(payload["phone_number"], account_created.phone_number)

    def test_read_an_account_that_doesnt_exist(self):
        """
        It should try to read an account that doesn't exist
        """
        # Making a GET request to fetch the account
        response = self.client.get(f"{BASE_URL}/123456789")
        payload = response.get_json()

        # Asserting the HTTP status and response content
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(payload["message"], "Account wasnt found")

    def test_update_an_account(self):
        """
        it should update an account from the service
        using ID, and requires all data to be updated
        """
        #Update  | PUT    | 200 OK         | An account as json {...}    | PUT /accounts/{id}

        # Create a single account
        account= self._create_accounts(1)[0]
        account_id = account.id 

        #New attributes
        original_name = account.name
        account.name = "New_name"
        original_email = account.email
        account.email = "New_email"
         

        #Update
        response = self.client.put(
            f"{BASE_URL}/{account_id}",
            json=account.serialize(),
            content_type="application/json"
            )
        payload = response.get_json()
        
        #tests
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payload["name"], "New_name")
        self.assertEqual(payload["email"], "New_email")

    def test_update_an_account_that_doesnt_exist(self):
        """
        It should try to update an account that doesn't exist
        """
        account = AccountFactory()
        # Making a GET request to fetch the account
        response = self.client.put(f"{BASE_URL}/123456789")
        payload = response.get_json()

        # Asserting the HTTP status and response content
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(payload["message"], "Account wasnt found")


    def test_delete_an_account(self):
        """
        it should delete an account from the service
        using ID
        """
        #Delete  | DELETE | 204 NO CONTENT | ""                          | DELETE /accounts/{id}
        # Create a single account
        count = random.randint(5, 100)
        accounts_created = self._create_accounts(count)
        response = self.client.get(BASE_URL)
        self.assertEqual(len(response.get_json()), count)
        account = accounts_created[4]
        account_id = account.id 

        #Delete account
        response = self.client.delete(
            f"{BASE_URL}/{account_id}"
            )

        #testing response
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        #testing deletion
        response = self.client.get(BASE_URL)
        self.assertEqual(len(response.get_json()), count - 1)


    
    def test_list_all_accounts(self):
        """
        it should list all the accounts in the service
        """
        #Testing with no accounts
        response = self.client.get(BASE_URL)
        self.assertEqual(len(response.get_json()), 0)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        #create a random number of accounts
        count = random.randint(1, 100)
        accounts_created = self._create_accounts(count)
        response = self.client.get(BASE_URL)
        self.assertEqual(len(response.get_json()), count)
        self.assertEqual(type(response.get_json()), list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_bad_request(self):
        """It should not Create an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_media_type(self):
        """It should not Create an Account when sending the wrong media type"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="test/html"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    ######################################################################
    #  S E C U R I T Y   T E S T   C A S E S
    ######################################################################

    def test_secure_headers(self):
        """It should confirm the presence of security headers"""
        response = self.client.get(BASE_URL, environ_overrides=HTTPS_ENVIRON)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        headers = {
            'X-Frame-Options': 'SAMEORIGIN',
            'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': 'default-src \'self\'; object-src \'none\'',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
            }
        for key, value in headers.items():
            self.assertEqual(response.headers.get(key), value)

    def test_cors_policies(self):
        """It should determine if there are cors policies stablished"""
        response = self.client.get(BASE_URL, environ_overrides=HTTPS_ENVIRON)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")


        
