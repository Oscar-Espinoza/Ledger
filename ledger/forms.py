from django import forms
from django.contrib.auth import get_user_model

from .models import Expense, Group

User = get_user_model()


class BootstrapFormMixin:
    """Attach Bootstrap classes to every widget so templates stay plain."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs.setdefault("class", css)


class GroupForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Group
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "e.g. Weekend trip", "autocomplete": "off"}
            )
        }


class InviteMemberForm(BootstrapFormMixin, forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "username"}),
    )

    def __init__(self, *args, group, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group

    def clean_username(self):
        username = self.cleaned_data["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError("No user with that username.") from None
        if self.group.members.filter(pk=user.pk).exists():
            raise forms.ValidationError(f"{username} is already a member.")
        return user


class ExpenseForm(BootstrapFormMixin, forms.ModelForm):
    """Expense fields plus one optional share input per group member.

    Share inputs are amounts for 'exact' splits and percentages for
    'percentage' splits; they stay blank for 'equal'. All money rules are
    enforced by ledger.services — this form only collects the values.
    """

    class Meta:
        model = Expense
        fields = ("description", "amount", "payer", "split_type")
        widgets = {
            "description": forms.TextInput(
                attrs={"placeholder": "e.g. Dinner", "autocomplete": "off"}
            ),
            "amount": forms.NumberInput(
                attrs={"step": "0.01", "min": "0.01", "inputmode": "decimal"}
            ),
        }

    def __init__(self, *args, group, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        members = group.members.order_by("username")
        self.fields["payer"].queryset = members
        self._share_fields = []
        for member in members:
            name = f"share_{member.pk}"
            self.fields[name] = forms.DecimalField(
                required=False,
                max_digits=12,
                decimal_places=2,
                label=member.username,
                widget=forms.NumberInput(
                    attrs={
                        "class": "form-control share-input",
                        "step": "0.01",
                        "min": "0",
                        "inputmode": "decimal",
                    }
                ),
            )
            self._share_fields.append((member, name))

    def split_data(self):
        """Collected share values as {user: Decimal}, or None if all blank."""
        data = {
            member: self.cleaned_data[name]
            for member, name in self._share_fields
            if self.cleaned_data.get(name) is not None
        }
        return data or None

    def share_fields(self):
        for _, name in self._share_fields:
            yield self[name]
