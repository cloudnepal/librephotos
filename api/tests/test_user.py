from constance.test import override_config
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import User
from api.tests.utils import create_test_user, create_user_details


class UserTest(TestCase):
    public_user_properties = [
        "id",
        "avatar_url",
        "username",
        "first_name",
        "last_name",
        "public_photo_count",
        "public_photo_samples",
    ]

    private_user_properties = [
        "id",
        "username",
        "email",
        "scan_directory",
        "confidence",
        "confidence_person",
        "transcode_videos",
        "semantic_search_topk",
        "first_name",
        "public_photo_samples",
        "last_name",
        "public_photo_count",
        "date_joined",
        "avatar",
        "is_superuser",
        "photo_count",
        "nextcloud_server_address",
        "nextcloud_username",
        "nextcloud_scan_directory",
        "avatar_url",
        "favorite_min_rating",
        "image_scale",
        "save_metadata_to_disk",
        "datetime_rules",
        "default_timezone",
        "public_sharing",
    ]

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=None)
        self.admin = create_test_user(is_admin=True)
        self.user1 = create_test_user(public_sharing=True)
        self.user2 = create_test_user()

    def test_public_user_list_count(self):
        response = self.client.get("/api/user/")
        data = response.json()
        self.assertEquals(
            len(User.objects.filter(public_sharing=True)), len(data["results"])
        )

    def test_public_user_list_properties(self):
        response = self.client.get("/api/user/")
        data = response.json()
        for user in data["results"]:
            self.assertEqual(len(self.public_user_properties), len(user.keys()))
            for key in self.public_user_properties:
                self.assertTrue(key in user, f"user does not have key: {key}")

    def test_authenticated_user_list_count(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/user/")
        data = response.json()
        self.assertEquals(len(User.objects.all()), len(data["results"]))

    def test_authenticated_user_list_properties(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/api/user/")
        data = response.json()
        for user in data["results"]:
            self.assertEqual(len(self.private_user_properties), len(user.keys()))
            for key in self.private_user_properties:
                self.assertTrue(key in user, f"user does not have key: {key}")

    def test_user_update_self(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.patch(
            f"/api/user/{self.user1.id}/", data={"first_name": "Updated"}
        )
        self.assertEqual(200, response.status_code)

    def test_public_update_user(self):
        response = self.client.patch(
            f"/api/user/{self.user1.id}/", data={"first_name": "Updated"}
        )
        self.assertEqual(401, response.status_code)

    def test_public_delete_user(self):
        response = self.client.delete(f"/api/user/{self.user1.id}/")
        self.assertEqual(401, response.status_code)

    @override_config(ALLOW_REGISTRATION=False)
    def test_public_user_create_successful_on_first_setup(self):
        User.objects.all().delete()
        self.client.force_authenticate(user=None)
        # You do not have to provide the is_superuser flag, because it is set to true by default, when there are no superusers in the database
        data = create_user_details()
        response = self.client.post("/api/user/", data=data)
        self.assertEqual(201, response.status_code)
        # Changed to 2, because we also have a deleted user -> endpoint things it already has a user and does not create a new admin
        self.assertEqual(2, len(User.objects.all()))
        user = User.objects.get(username=data["username"])
        self.assertTrue(user.is_superuser)

    @override_config(ALLOW_REGISTRATION=True)
    def test_public_user_create_successful_when_registration_enabled(self):
        data = create_user_details()
        response = self.client.post("/api/user/", data=data)
        self.assertEqual(201, response.status_code)
        user = User.objects.get(username=data["username"])
        self.assertEqual(data["username"], user.username)
        self.assertEqual(data["email"], user.email)
        self.assertEqual(data["first_name"], user.first_name)
        self.assertEqual(data["last_name"], user.last_name)

    @override_config(ALLOW_REGISTRATION=True)
    def test_after_registration_user_can_authenticate(self):
        user = create_user_details()
        signup_response = self.client.post("/api/user/", data=user)
        self.assertEqual(201, signup_response.status_code)
        login_payload = {
            "username": user["username"],
            "password": user["password"],
        }
        response = self.client.post("/api/auth/token/obtain/", data=login_payload)
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertTrue("access" in data.keys())
        self.assertTrue("refresh" in data.keys())

    @override_config(ALLOW_REGISTRATION=False)
    def test_public_user_create_fails_when_registration_disabled(self):
        response = self.client.post("/api/user/", data=create_user_details())
        # because IsAdminOrFirstTimeSetupOrRegistrationAllowed is **global** permission
        # on UserViewSet, we are returning 401 and not 403
        self.assertEqual(401, response.status_code)

    @override_config(ALLOW_REGISTRATION=True)
    def test_not_first_setup_create_admin_should_create_regular_user(self):
        data = create_user_details(is_admin=True)
        response = self.client.post("/api/user/", data=data)
        self.assertEqual(201, response.status_code)
        user = User.objects.get(username=data["username"])
        self.assertEqual(False, user.is_superuser)

    def test_user_update_another_user(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.patch(
            f"/api/user/{self.user2.id}/", data={"first_name": "Updated"}
        )
        self.assertEqual(403, response.status_code)

    def test_user_delete_another_user(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.delete(f"/api/user/{self.user2.id}/")
        self.assertEqual(403, response.status_code)

    def test_admin_create_user(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/user/", data=create_user_details())
        self.assertEqual(201, response.status_code)

    def test_admin_partial_update_user(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(
            f"/api/user/{self.user1.id}/", data={"first_name": "Updated"}
        )
        self.assertEqual(200, response.status_code)

    def test_admin_delete_user(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(f"/api/user/{self.user1.id}/")
        self.assertEqual(204, response.status_code)

    @override_config(ALLOW_REGISTRATION=False)
    def test_first_time_setup_creates_user_when_registration_is_disabled(self):
        User.objects.all().delete()
        response = self.client.post("/api/user/", data=create_user_details())
        self.assertEqual(201, response.status_code)

    def test_first_time_setup(self):
        User.objects.all().delete()
        response = self.client.get("/api/firsttimesetup/")
        data = response.json()
        self.assertEqual(True, data["isFirstTimeSetup"])

    @override_config(ALLOW_REGISTRATION=True)
    def test_not_first_time_setup(self):
        data = create_user_details()
        signup_response = self.client.post("/api/user/", data=data)
        self.assertEqual(201, signup_response.status_code)
        user = User.objects.get(username=data["username"])
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/firsttimesetup/")
        data = response.json()
        self.assertEqual(False, data["isFirstTimeSetup"])

    def test_regular_user_not_allowed_to_set_scan_directory(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.patch(
            f"/api/user/{self.user1.id}/", {"scan_directory": "/data"}
        )
        data = response.json()
        self.assertNotEqual("/data", data["scan_directory"])
