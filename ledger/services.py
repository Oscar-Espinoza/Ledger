"""Business logic for expense splitting and debt settlement.

Lives outside models/views so it can be unit tested in isolation.
All money values are Decimal at cent precision. Rounding remainders are
handed out one cent at a time to members in ascending user-id order, so
results are deterministic and shares always sum exactly to the total.
"""

from decimal import ROUND_FLOOR, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Expense, ExpenseShare

CENT = Decimal("0.01")
ONE_HUNDRED = Decimal("100")


@transaction.atomic
def create_expense_shares(expense: Expense, split_data: dict | None = None) -> list[ExpenseShare]:
    """Calculate and persist the ExpenseShare rows for an expense.

    For 'equal' splits the amount is divided across all group members and
    split_data must be None. For 'exact' and 'percentage' splits, split_data
    maps each participating user to their exact amount or percentage.
    Existing shares for the expense are replaced.

    Returns the created shares in ascending user-id order.
    Raises ValidationError for invalid amounts or split data.
    """
    _validate_amount(expense.amount)
    members = list(expense.group.members.order_by("pk"))
    if not members:
        raise ValidationError("Group has no members.")
    if expense.payer not in members:
        raise ValidationError("Payer must be a member of the group.")

    if expense.split_type == Expense.SplitType.EQUAL:
        if split_data is not None:
            raise ValidationError("split_data is not accepted for equal splits.")
        shares = _equal_shares(expense.amount, members)
    elif expense.split_type == Expense.SplitType.EXACT:
        shares = _exact_shares(expense.amount, _validated_split_data(split_data, members))
    elif expense.split_type == Expense.SplitType.PERCENTAGE:
        shares = _percentage_shares(expense.amount, _validated_split_data(split_data, members))
    else:
        raise ValidationError(f"Unknown split type: {expense.split_type!r}")

    expense.shares.all().delete()
    return ExpenseShare.objects.bulk_create(
        ExpenseShare(expense=expense, user=user, amount_owed=amount)
        for user, amount in sorted(shares.items(), key=lambda item: item[0].pk)
    )


def _validate_amount(amount) -> None:
    if not isinstance(amount, Decimal):
        raise ValidationError("Amount must be a Decimal.")
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    if amount != amount.quantize(CENT):
        raise ValidationError("Amount cannot be more precise than one cent.")


def _validated_split_data(split_data: dict | None, members: list) -> dict:
    if not split_data:
        raise ValidationError("This split type requires split_data.")
    if not set(split_data) <= set(members):
        raise ValidationError("All split participants must be group members.")
    for value in split_data.values():
        if not isinstance(value, Decimal):
            raise ValidationError("Split values must be Decimals.")
        if value < 0:
            raise ValidationError("Split values cannot be negative.")
    return split_data


def _equal_shares(amount: Decimal, members: list) -> dict:
    base = (amount / len(members)).quantize(CENT, rounding=ROUND_FLOOR)
    shares = {member: base for member in members}
    _distribute_remainder(shares, amount)
    return shares


def _exact_shares(amount: Decimal, split_data: dict) -> dict:
    for value in split_data.values():
        if value != value.quantize(CENT):
            raise ValidationError("Exact shares cannot be more precise than one cent.")
    if sum(split_data.values()) != amount:
        raise ValidationError("Exact shares must sum to the expense amount.")
    return dict(split_data)

def _percentage_shares(amount: Decimal, split_data: dict) -> dict:
    raise NotImplementedError  # Task 6

def _distribute_remainder(shares: dict, total: Decimal) -> None:
    """Top up shares in ascending user-id order until they sum to total.

    Callers floor each share to the cent first, so the shortfall is a
    non-negative whole number of cents smaller than len(shares).
    """
    remainder_cents = int((total - sum(shares.values())) / CENT)
    for user in sorted(shares, key=lambda u: u.pk)[:remainder_cents]:
        shares[user] += CENT
