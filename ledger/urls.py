from django.urls import path

from .views import (
    ExpenseCreateView,
    GroupCreateView,
    GroupDetailView,
    GroupListView,
    InviteMemberView,
    SettleUpView,
)

urlpatterns = [
    path("", GroupListView.as_view(), name="group-list"),
    path("groups/new/", GroupCreateView.as_view(), name="group-create"),
    path("groups/<int:pk>/", GroupDetailView.as_view(), name="group-detail"),
    path("groups/<int:pk>/invite/", InviteMemberView.as_view(), name="group-invite"),
    path("groups/<int:pk>/expenses/new/", ExpenseCreateView.as_view(), name="expense-create"),
    path("groups/<int:pk>/settle/", SettleUpView.as_view(), name="group-settle"),
]
