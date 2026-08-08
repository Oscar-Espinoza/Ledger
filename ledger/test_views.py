from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Expense, Group
from .services import create_expense_shares

User = get_user_model()


def login_user(client, username="alice"):
    user = User.objects.create_user(username=username, password="s3cret-pw!")
    client.force_login(user)
    return user


class GroupViewTests(TestCase):
    def test_group_list_requires_login(self):
        response = self.client.get(reverse("group-list"))
        self.assertRedirects(response, f"{reverse('login')}?next=/")

    def test_group_list_shows_only_my_groups(self):
        alice = login_user(self.client)
        mine = Group.objects.create(name="Trip")
        mine.members.add(alice)
        Group.objects.create(name="Secret")
        response = self.client.get(reverse("group-list"))
        self.assertContains(response, "Trip")
        self.assertNotContains(response, "Secret")

    def test_create_group_adds_creator_as_member(self):
        alice = login_user(self.client)
        response = self.client.post(reverse("group-create"), {"name": "Ski house"})
        group = Group.objects.get(name="Ski house")
        self.assertRedirects(response, reverse("group-detail", args=[group.pk]))
        self.assertIn(alice, group.members.all())

    def test_detail_404_for_non_members(self):
        login_user(self.client)
        group = Group.objects.create(name="Private")
        response = self.client.get(reverse("group-detail", args=[group.pk]))
        self.assertEqual(response.status_code, 404)

    def test_detail_shows_balances_and_expenses(self):
        alice = login_user(self.client)
        bob = User.objects.create_user(username="bob")
        group = Group.objects.create(name="Trip")
        group.members.set([alice, bob])
        expense = Expense.objects.create(
            group=group, payer=alice, amount=Decimal("10.00"), description="Lunch"
        )
        create_expense_shares(expense)
        response = self.client.get(reverse("group-detail", args=[group.pk]))
        self.assertContains(response, "Lunch")
        self.assertContains(response, "5.00")
        self.assertContains(response, "-5.00")


class InviteMemberTests(TestCase):
    def setUp(self):
        self.alice = login_user(self.client)
        self.group = Group.objects.create(name="Trip")
        self.group.members.add(self.alice)

    def test_invite_adds_existing_user(self):
        User.objects.create_user(username="bob")
        response = self.client.post(
            reverse("group-invite", args=[self.group.pk]), {"username": "bob"}
        )
        self.assertRedirects(response, reverse("group-detail", args=[self.group.pk]))
        self.assertTrue(self.group.members.filter(username="bob").exists())

    def test_unknown_username_shows_error(self):
        response = self.client.post(
            reverse("group-invite", args=[self.group.pk]),
            {"username": "nobody"},
            follow=True,
        )
        self.assertContains(response, "No user with that username.")
        self.assertEqual(self.group.members.count(), 1)

    def test_existing_member_shows_error(self):
        response = self.client.post(
            reverse("group-invite", args=[self.group.pk]),
            {"username": "alice"},
            follow=True,
        )
        self.assertContains(response, "already a member")

    def test_non_member_cannot_invite(self):
        outsider_group = Group.objects.create(name="Other")
        response = self.client.post(
            reverse("group-invite", args=[outsider_group.pk]), {"username": "alice"}
        )
        self.assertEqual(response.status_code, 404)
