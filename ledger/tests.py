from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from .models import Expense, ExpenseShare, Group

User = get_user_model()


def make_group(*usernames):
    """Create a Group whose members are freshly created users.

    Returns (group, users) with users in creation (ascending pk) order —
    the same order the services use to hand out remainder cents.
    """
    users = [User.objects.create_user(username=name) for name in usernames]
    group = Group.objects.create(name="Trip")
    group.members.set(users)
    return group, users


class ModelTests(TestCase):
    def test_group_membership(self):
        group, users = make_group("alice", "bob")
        self.assertCountEqual(group.members.all(), users)

    def test_expense_and_share_creation(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = Expense.objects.create(
            group=group,
            payer=alice,
            amount=Decimal("12.50"),
            description="Taxi",
            split_type=Expense.SplitType.EQUAL,
        )
        share = ExpenseShare.objects.create(expense=expense, user=bob, amount_owed=Decimal("6.25"))
        self.assertEqual(expense.shares.get(), share)
        self.assertEqual(expense.split_type, "equal")
        self.assertIn(expense, group.expenses.all())

    def test_duplicate_share_for_same_user_rejected(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = Expense.objects.create(
            group=group, payer=alice, amount=Decimal("10.00"), description="Lunch"
        )
        ExpenseShare.objects.create(expense=expense, user=bob, amount_owed=Decimal("5.00"))
        with self.assertRaises(IntegrityError):
            ExpenseShare.objects.create(expense=expense, user=bob, amount_owed=Decimal("5.00"))
