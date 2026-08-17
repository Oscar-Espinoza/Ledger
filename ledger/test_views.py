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
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('group-list')}")

    def test_group_list_shows_only_my_groups(self):
        alice = login_user(self.client)
        mine = Group.objects.create(name="Trip")
        mine.members.add(alice)
        Group.objects.create(name="Secret")
        response = self.client.get(reverse("group-list"))
        self.assertContains(response, "Trip")
        self.assertNotContains(response, "Secret")

    def test_group_list_uses_annotated_member_and_expense_counts(self):
        alice = login_user(self.client)
        bob = User.objects.create_user(username="bob")
        group = Group.objects.create(name="Trip")
        group.members.set([alice, bob])
        Expense.objects.create(
            group=group, payer=alice, amount=Decimal("10.00"), description="Lunch"
        )

        response = self.client.get(reverse("group-list"))

        listed_group = response.context["groups"][0]
        self.assertEqual(listed_group.member_count, 2)
        self.assertEqual(listed_group.expense_count, 1)
        self.assertContains(response, "2 members")
        self.assertContains(response, "1 expense")

    def test_empty_dashboard_has_actionable_checklist(self):
        login_user(self.client)
        response = self.client.get(reverse("group-list"))
        self.assertContains(response, "Create your first group")
        self.assertContains(response, "Invite friends by their existing Ledger username")

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
        self.assertContains(response, "You are owed")
        self.assertContains(response, "is owed")
        self.assertContains(response, "owes")
        self.assertContains(response, "5.00")
        self.assertContains(response, "Help reading positive and negative balances")

    def test_create_group_success_uses_toast_markup(self):
        login_user(self.client)
        response = self.client.post(
            reverse("group-create"), {"name": "Ski house"}, follow=True
        )
        self.assertContains(response, "Ski house is ready.")
        self.assertContains(response, "data-app-toast")


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
        self.assertContains(response, "invalid-feedback d-block")
        self.assertNotContains(response, "data-app-toast")
        self.assertEqual(self.group.members.count(), 1)

    def test_detail_explains_existing_username_requirement(self):
        response = self.client.get(reverse("group-detail", args=[self.group.pk]))
        self.assertContains(response, "They must already have a Ledger account.")
        self.assertContains(response, "Help inviting a member")

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


class AddExpenseTests(TestCase):
    def setUp(self):
        self.alice = login_user(self.client)
        self.bob = User.objects.create_user(username="bob")
        self.group = Group.objects.create(name="Trip")
        self.group.members.set([self.alice, self.bob])
        self.url = reverse("expense-create", args=[self.group.pk])

    def _post(self, **extra):
        data = {
            "description": "Dinner",
            "amount": "10.00",
            "payer": str(self.alice.pk),
            "split_type": "equal",
        }
        data.update(extra)
        return self.client.post(self.url, data)

    def test_equal_split_creates_expense_and_shares(self):
        response = self._post()
        self.assertRedirects(response, reverse("group-detail", args=[self.group.pk]))
        expense = Expense.objects.get()
        owed = {s.user: s.amount_owed for s in expense.shares.all()}
        self.assertEqual(owed, {self.alice: Decimal("5.00"), self.bob: Decimal("5.00")})

    def test_exact_split_uses_share_fields(self):
        self._post(
            split_type="exact",
            **{
                f"share_{self.alice.pk}": "7.50",
                f"share_{self.bob.pk}": "2.50",
            },
        )
        expense = Expense.objects.get()
        owed = {s.user: s.amount_owed for s in expense.shares.all()}
        self.assertEqual(owed, {self.alice: Decimal("7.50"), self.bob: Decimal("2.50")})

    def test_percentage_split_uses_share_fields(self):
        self._post(
            split_type="percentage",
            **{
                f"share_{self.alice.pk}": "25",
                f"share_{self.bob.pk}": "75",
            },
        )
        expense = Expense.objects.get()
        owed = {s.user: s.amount_owed for s in expense.shares.all()}
        self.assertEqual(owed, {self.alice: Decimal("2.50"), self.bob: Decimal("7.50")})

    def test_exact_split_sum_mismatch_rolls_back(self):
        response = self._post(
            split_type="exact",
            **{
                f"share_{self.alice.pk}": "9.00",
                f"share_{self.bob.pk}": "2.00",
            },
        )
        self.assertContains(response, "must sum to the expense amount")
        self.assertEqual(Expense.objects.count(), 0)

    def test_percentage_not_100_rolls_back(self):
        response = self._post(
            split_type="percentage",
            **{
                f"share_{self.alice.pk}": "50",
                f"share_{self.bob.pk}": "40",
            },
        )
        self.assertContains(response, "sum to exactly 100")
        self.assertEqual(Expense.objects.count(), 0)

    def test_shares_with_equal_split_rejected(self):
        response = self._post(**{f"share_{self.alice.pk}": "10.00"})
        self.assertContains(response, "not accepted for equal splits")
        self.assertEqual(Expense.objects.count(), 0)

    def test_payer_choices_limited_to_members(self):
        outsider = User.objects.create_user(username="mallory")
        response = self.client.get(self.url)
        payer_qs = response.context["form"].fields["payer"].queryset
        self.assertNotIn(outsider, payer_qs)

    def test_expense_form_explains_split_methods_and_live_total(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Help choosing a split method")
        self.assertContains(response, 'id="share-total"')
        self.assertContains(response, "Use your group's agreed currency.")

    def test_non_member_gets_404(self):
        other = Group.objects.create(name="Other")
        response = self.client.get(reverse("expense-create", args=[other.pk]))
        self.assertEqual(response.status_code, 404)


class SettleUpViewTests(TestCase):
    def setUp(self):
        self.alice = login_user(self.client)
        self.bob = User.objects.create_user(username="bob")
        self.group = Group.objects.create(name="Trip")
        self.group.members.set([self.alice, self.bob])

    def test_shows_suggested_transactions(self):
        expense = Expense.objects.create(
            group=self.group, payer=self.alice, amount=Decimal("10.00"), description="Cab"
        )
        create_expense_shares(expense)
        response = self.client.get(reverse("group-settle", args=[self.group.pk]))
        self.assertContains(response, "bob")
        self.assertContains(response, "alice")
        self.assertContains(response, "5.00")
        self.assertContains(response, "Ledger does not transfer money")
        self.assertContains(response, "Help understanding settlement suggestions")

    def test_settled_group_shows_empty_state(self):
        response = self.client.get(reverse("group-settle", args=[self.group.pk]))
        self.assertContains(response, "No payments are needed")

    def test_non_member_gets_404(self):
        other = Group.objects.create(name="Other")
        response = self.client.get(reverse("group-settle", args=[other.pk]))
        self.assertEqual(response.status_code, 404)


class HomeViewTests(TestCase):
    def test_anonymous_home_is_public_landing_page(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Split expenses without the spreadsheet")
        self.assertContains(response, "Weekend trip")
        self.assertContains(response, "Create a group")
        self.assertContains(response, "Groups are private to their members")
        self.assertContains(response, "ledger/css/app.css")

    def test_authenticated_home_redirects_to_groups(self):
        login_user(self.client)
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("group-list"), fetch_redirect_response=False)
