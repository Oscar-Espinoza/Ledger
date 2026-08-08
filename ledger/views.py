from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView

from .forms import ExpenseForm, GroupForm, InviteMemberForm
from .models import Group
from .services import compute_balances, create_expense_shares, settle_up


class GroupQuerysetMixin(LoginRequiredMixin):
    """Group-scoped views resolve only groups the current user belongs to (else 404)."""

    def get_queryset(self):
        return Group.objects.filter(members=self.request.user)


class GroupListView(GroupQuerysetMixin, ListView):
    model = Group
    context_object_name = "groups"


class GroupCreateView(LoginRequiredMixin, CreateView):
    model = Group
    form_class = GroupForm

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.members.add(self.request.user)
        return response

    def get_success_url(self):
        return reverse("group-detail", args=[self.object.pk])


class GroupDetailView(GroupQuerysetMixin, DetailView):
    model = Group
    context_object_name = "group"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        balances = compute_balances(self.object)
        context["balances"] = sorted(balances.items(), key=lambda item: item[0].username)
        context["expenses"] = self.object.expenses.select_related("payer").order_by("-created_at")
        context["invite_form"] = InviteMemberForm(group=self.object)
        return context


class InviteMemberView(LoginRequiredMixin, View):
    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk, members=request.user)
        form = InviteMemberForm(request.POST, group=group)
        if form.is_valid():
            new_member = form.cleaned_data["username"]
            group.members.add(new_member)
            messages.success(request, f"Added {new_member.username} to the group.")
        else:
            for error in form.errors["username"]:
                messages.error(request, error)
        return redirect("group-detail", pk=group.pk)


class ExpenseCreateView(LoginRequiredMixin, FormView):
    template_name = "ledger/expense_form.html"
    form_class = ExpenseForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.group = get_object_or_404(Group, pk=kwargs["pk"], members=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["group"] = self.group
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["group"] = self.group
        return context

    def form_valid(self, form):
        expense = form.save(commit=False)
        expense.group = self.group
        try:
            with transaction.atomic():
                expense.save()
                create_expense_shares(expense, form.split_data())
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
            return self.form_invalid(form)
        messages.success(self.request, "Expense added.")
        return redirect("group-detail", pk=self.group.pk)


class SettleUpView(LoginRequiredMixin, TemplateView):
    template_name = "ledger/settle_up.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = get_object_or_404(Group, pk=self.kwargs["pk"], members=self.request.user)
        context["group"] = group
        context["transactions"] = settle_up(group)
        return context
