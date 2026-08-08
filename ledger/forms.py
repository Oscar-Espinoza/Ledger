from django import forms
from django.contrib.auth import get_user_model

from .models import Group

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
            raise forms.ValidationError("No user with that username.")
        if self.group.members.filter(pk=user.pk).exists():
            raise forms.ValidationError(f"{username} is already a member.")
        return user
