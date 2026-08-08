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
