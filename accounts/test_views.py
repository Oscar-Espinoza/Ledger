from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AuthFlowTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Log in")
        self.assertContains(response, "Equal, exact, and percentage splits")

    def test_login_redirects_to_group_list(self):
        User.objects.create_user(username="alice", password="s3cret-pw!")
        response = self.client.post(
            reverse("login"), {"username": "alice", "password": "s3cret-pw!"}
        )
        self.assertRedirects(response, reverse("group-list"), fetch_redirect_response=False)

    def test_logout_is_post_and_redirects_to_public_home(self):
        user = User.objects.create_user(username="alice", password="s3cret-pw!")
        self.client.force_login(user)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("home"))


class SignUpTests(TestCase):
    def test_signup_page_renders(self):
        response = self.client.get(reverse("signup"))
        self.assertContains(response, "Sign up")
        self.assertContains(response, "keeps groups visible only to their members")
        self.assertContains(response, "exact username")

    def test_signup_authenticates_and_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "carol",
                "password1": "s3cret-pw!x",
                "password2": "s3cret-pw!x",
            },
        )
        user = User.objects.get(username="carol")
        self.assertRedirects(response, reverse("group-list"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_signup_onboarding_appears_once_and_help_remains(self):
        self.client.post(
            reverse("signup"),
            {
                "username": "carol",
                "password1": "s3cret-pw!x",
                "password2": "s3cret-pw!x",
            },
        )

        first_dashboard = self.client.get(reverse("group-list"))
        self.assertContains(first_dashboard, 'data-auto-show="true"')
        self.assertContains(first_dashboard, 'data-bs-target="#welcomeModal"')

        second_dashboard = self.client.get(reverse("group-list"))
        self.assertContains(second_dashboard, 'data-auto-show="false"')
        self.assertContains(second_dashboard, 'data-bs-target="#welcomeModal"')

    def test_password_mismatch_creates_no_user(self):
        response = self.client.post(
            reverse("signup"),
            {"username": "carol", "password1": "s3cret-pw!x", "password2": "different"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="carol").exists())
