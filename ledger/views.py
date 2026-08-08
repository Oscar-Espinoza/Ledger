from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from .forms import GroupForm
from .models import Group
from .services import compute_balances


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
        context["expenses"] = self.object.expenses.select_related("payer").order_by(
            "-created_at"
        )
        return context
