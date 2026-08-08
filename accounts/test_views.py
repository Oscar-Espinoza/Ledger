from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AuthFlowTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Log in")

    def test_login_redirects_home(self):
        User.objects.create_user(username="alice", password="s3cret-pw!")
        response = self.client.post(
            reverse("login"), {"username": "alice", "password": "s3cret-pw!"}
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_logout_is_post_and_redirects_to_login(self):
        user = User.objects.create_user(username="alice", password="s3cret-pw!")
        self.client.force_login(user)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))


class SignUpTests(TestCase):
    def test_signup_page_renders(self):
        response = self.client.get(reverse("signup"))
        self.assertContains(response, "Sign up")

    def test_signup_creates_user_and_redirects_to_login(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "carol",
                "password1": "s3cret-pw!x",
                "password2": "s3cret-pw!x",
            },
        )
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(User.objects.filter(username="carol").exists())

    def test_password_mismatch_creates_no_user(self):
        response = self.client.post(
            reverse("signup"),
            {"username": "carol", "password1": "s3cret-pw!x", "password2": "different"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="carol").exists())
