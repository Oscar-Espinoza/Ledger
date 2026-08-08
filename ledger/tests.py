from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from .models import Expense, ExpenseShare, Group
from .services import create_expense_shares, compute_balances

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


class EqualSplitTests(TestCase):
    def _expense(self, group, payer, amount):
        return Expense.objects.create(
            group=group,
            payer=payer,
            amount=amount,
            description="Pizza",
            split_type=Expense.SplitType.EQUAL,
        )

    def test_non_divisible_total_gives_extra_cents_to_first_members(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        expense = self._expense(group, alice, Decimal("10.00"))
        shares = create_expense_shares(expense)
        owed = {share.user: share.amount_owed for share in shares}
        self.assertEqual(
            owed, {alice: Decimal("3.34"), bob: Decimal("3.33"), carol: Decimal("3.33")}
        )
        self.assertEqual(sum(owed.values()), Decimal("10.00"))

    def test_two_cent_remainder_spreads_over_first_two_members(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        expense = self._expense(group, alice, Decimal("11.00"))
        shares = create_expense_shares(expense)
        owed = {share.user: share.amount_owed for share in shares}
        self.assertEqual(
            owed, {alice: Decimal("3.67"), bob: Decimal("3.67"), carol: Decimal("3.66")}
        )
        self.assertEqual(sum(owed.values()), Decimal("11.00"))

    def test_divisible_total_splits_evenly(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        expense = self._expense(group, alice, Decimal("9.00"))
        owed = {s.user: s.amount_owed for s in create_expense_shares(expense)}
        self.assertEqual(
            owed, {alice: Decimal("3.00"), bob: Decimal("3.00"), carol: Decimal("3.00")}
        )

    def test_two_member_group(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = self._expense(group, alice, Decimal("7.01"))
        owed = {s.user: s.amount_owed for s in create_expense_shares(expense)}
        self.assertEqual(owed, {alice: Decimal("3.51"), bob: Decimal("3.50")})

    def test_payer_is_also_a_shareholder(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = self._expense(group, alice, Decimal("10.00"))
        owed = {s.user: s.amount_owed for s in create_expense_shares(expense)}
        self.assertEqual(owed[alice], Decimal("5.00"))

    def test_split_data_rejected_for_equal_split(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = self._expense(group, alice, Decimal("10.00"))
        with self.assertRaises(ValidationError):
            create_expense_shares(expense, {alice: Decimal("10.00")})

    def test_recalculating_replaces_existing_shares(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = self._expense(group, alice, Decimal("10.00"))
        create_expense_shares(expense)
        create_expense_shares(expense)
        self.assertEqual(expense.shares.count(), 2)


class ExpenseValidationTests(TestCase):
    def _expense(self, group, payer, amount):
        return Expense.objects.create(
            group=group, payer=payer, amount=amount, description="Bad", split_type="equal"
        )

    def test_zero_amount_raises(self):
        group, (alice,) = make_group("alice")
        with self.assertRaisesMessage(ValidationError, "greater than zero"):
            create_expense_shares(self._expense(group, alice, Decimal("0.00")))

    def test_negative_amount_raises(self):
        group, (alice,) = make_group("alice")
        with self.assertRaisesMessage(ValidationError, "greater than zero"):
            create_expense_shares(self._expense(group, alice, Decimal("-5.00")))

    def test_subcent_precision_raises(self):
        group, (alice,) = make_group("alice")
        expense = Expense(
            group=group, payer=alice, amount=Decimal("10.005"), description="Bad"
        )
        with self.assertRaisesMessage(ValidationError, "one cent"):
            create_expense_shares(expense)

    def test_float_amount_raises(self):
        group, (alice,) = make_group("alice")
        expense = Expense(group=group, payer=alice, amount=10.0, description="Bad")
        with self.assertRaisesMessage(ValidationError, "Decimal"):
            create_expense_shares(expense)

    def test_payer_not_a_member_raises(self):
        group, (alice,) = make_group("alice")
        outsider = User.objects.create_user(username="outsider")
        expense = Expense.objects.create(
            group=group, payer=outsider, amount=Decimal("10.00"), description="Bad"
        )
        with self.assertRaisesMessage(ValidationError, "member of the group"):
            create_expense_shares(expense)

    def test_group_with_no_members_raises(self):
        alice = User.objects.create_user(username="alice")
        group = Group.objects.create(name="Empty")
        expense = Expense.objects.create(
            group=group, payer=alice, amount=Decimal("10.00"), description="Bad"
        )
        with self.assertRaisesMessage(ValidationError, "no members"):
            create_expense_shares(expense)


class ExactSplitTests(TestCase):
    def _expense(self, group, payer, amount):
        return Expense.objects.create(
            group=group,
            payer=payer,
            amount=amount,
            description="Dinner",
            split_type=Expense.SplitType.EXACT,
        )

    def test_valid_exact_split(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        expense = self._expense(group, alice, Decimal("10.00"))
        shares = create_expense_shares(
            expense, {alice: Decimal("5.00"), bob: Decimal("3.00"), carol: Decimal("2.00")}
        )
        owed = {s.user: s.amount_owed for s in shares}
        self.assertEqual(
            owed, {alice: Decimal("5.00"), bob: Decimal("3.00"), carol: Decimal("2.00")}
        )

    def test_zero_share_means_member_owes_nothing(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = self._expense(group, alice, Decimal("10.00"))
        shares = create_expense_shares(expense, {alice: Decimal("10.00"), bob: Decimal("0.00")})
        owed = {s.user: s.amount_owed for s in shares}
        self.assertEqual(owed[bob], Decimal("0.00"))

    def test_participant_subset_is_allowed(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        expense = self._expense(group, alice, Decimal("10.00"))
        shares = create_expense_shares(expense, {alice: Decimal("4.00"), bob: Decimal("6.00")})
        self.assertEqual({s.user for s in shares}, {alice, bob})

    def test_shares_summing_under_total_raise(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = self._expense(group, alice, Decimal("10.00"))
        with self.assertRaisesMessage(ValidationError, "must sum to the expense amount"):
            create_expense_shares(expense, {alice: Decimal("5.00"), bob: Decimal("4.00")})

    def test_shares_summing_over_total_raise(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = self._expense(group, alice, Decimal("10.00"))
        with self.assertRaisesMessage(ValidationError, "must sum to the expense amount"):
            create_expense_shares(expense, {alice: Decimal("5.00"), bob: Decimal("6.00")})

    def test_negative_share_raises(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = self._expense(group, alice, Decimal("10.00"))
        with self.assertRaisesMessage(ValidationError, "cannot be negative"):
            create_expense_shares(expense, {alice: Decimal("15.00"), bob: Decimal("-5.00")})

    def test_missing_split_data_raises(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = self._expense(group, alice, Decimal("10.00"))
        with self.assertRaisesMessage(ValidationError, "requires split_data"):
            create_expense_shares(expense)

    def test_non_member_participant_raises(self):
        group, (alice,) = make_group("alice")
        outsider = User.objects.create_user(username="outsider")
        expense = self._expense(group, alice, Decimal("10.00"))
        with self.assertRaisesMessage(ValidationError, "group members"):
            create_expense_shares(expense, {outsider: Decimal("10.00")})

    def test_subcent_share_raises(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = self._expense(group, alice, Decimal("10.00"))
        with self.assertRaisesMessage(ValidationError, "one cent"):
            create_expense_shares(expense, {alice: Decimal("5.005"), bob: Decimal("4.995")})


class PercentageSplitTests(TestCase):
    def _expense(self, group, payer, amount):
        return Expense.objects.create(
            group=group,
            payer=payer,
            amount=amount,
            description="Hotel",
            split_type=Expense.SplitType.PERCENTAGE,
        )

    def test_valid_percentages(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        expense = self._expense(group, alice, Decimal("10.00"))
        shares = create_expense_shares(
            expense, {alice: Decimal("50"), bob: Decimal("30"), carol: Decimal("20")}
        )
        owed = {s.user: s.amount_owed for s in shares}
        self.assertEqual(
            owed, {alice: Decimal("5.00"), bob: Decimal("3.00"), carol: Decimal("2.00")}
        )

    def test_rounding_remainder_goes_to_first_member(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        expense = self._expense(group, alice, Decimal("10.00"))
        shares = create_expense_shares(
            expense, {alice: Decimal("33.33"), bob: Decimal("33.33"), carol: Decimal("33.34")}
        )
        owed = {s.user: s.amount_owed for s in shares}
        self.assertEqual(
            owed, {alice: Decimal("3.34"), bob: Decimal("3.33"), carol: Decimal("3.33")}
        )
        self.assertEqual(sum(owed.values()), Decimal("10.00"))

    def test_percentages_under_100_raise(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        expense = self._expense(group, alice, Decimal("10.00"))
        with self.assertRaisesMessage(ValidationError, "sum to exactly 100"):
            create_expense_shares(
                expense, {alice: Decimal("30"), bob: Decimal("30"), carol: Decimal("30")}
            )

    def test_percentages_over_100_raise(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        expense = self._expense(group, alice, Decimal("10.00"))
        with self.assertRaisesMessage(ValidationError, "sum to exactly 100"):
            create_expense_shares(
                expense, {alice: Decimal("50"), bob: Decimal("40"), carol: Decimal("20")}
            )

    def test_negative_percentage_raises(self):
        group, (alice, bob) = make_group("alice", "bob")
        expense = self._expense(group, alice, Decimal("10.00"))
        with self.assertRaisesMessage(ValidationError, "cannot be negative"):
            create_expense_shares(expense, {alice: Decimal("150"), bob: Decimal("-50")})


class ComputeBalancesTests(TestCase):
    def test_payer_who_also_owes_a_share_nets_out(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        expense = Expense.objects.create(
            group=group, payer=alice, amount=Decimal("30.00"), description="Groceries"
        )
        create_expense_shares(expense)
        self.assertEqual(
            compute_balances(group),
            {alice: Decimal("20.00"), bob: Decimal("-10.00"), carol: Decimal("-10.00")},
        )

    def test_uninvolved_member_has_zero_balance(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        expense = Expense.objects.create(
            group=group,
            payer=alice,
            amount=Decimal("10.00"),
            description="Coffee",
            split_type=Expense.SplitType.EXACT,
        )
        create_expense_shares(expense, {alice: Decimal("4.00"), bob: Decimal("6.00")})
        self.assertEqual(compute_balances(group)[carol], Decimal("0.00"))

    def test_group_with_no_expenses_is_all_zeros(self):
        group, users = make_group("alice", "bob")
        self.assertEqual(compute_balances(group), {u: Decimal("0.00") for u in users})

    def test_balances_sum_to_zero_across_mixed_expenses(self):
        group, (alice, bob, carol) = make_group("alice", "bob", "carol")
        e1 = Expense.objects.create(
            group=group, payer=alice, amount=Decimal("10.00"), description="A"
        )
        create_expense_shares(e1)
        e2 = Expense.objects.create(
            group=group,
            payer=bob,
            amount=Decimal("7.77"),
            description="B",
            split_type=Expense.SplitType.PERCENTAGE,
        )
        create_expense_shares(
            e2, {alice: Decimal("33.33"), bob: Decimal("33.33"), carol: Decimal("33.34")}
        )
        self.assertEqual(sum(compute_balances(group).values()), Decimal("0.00"))
