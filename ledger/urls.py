from django.urls import path

from .views import GroupCreateView, GroupDetailView, GroupListView

urlpatterns = [
    path("", GroupListView.as_view(), name="group-list"),
    path("groups/new/", GroupCreateView.as_view(), name="group-create"),
    path("groups/<int:pk>/", GroupDetailView.as_view(), name="group-detail"),
]
