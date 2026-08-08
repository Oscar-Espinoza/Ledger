from django.contrib.auth import get_user_model
from django.test import TestCase


class UserModelTests(TestCase):
    def test_custom_user_model_is_active(self):
        user = get_user_model().objects.create_user(username="alice")
        self.assertEqual(user._meta.label, "accounts.User")
