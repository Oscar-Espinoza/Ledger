from django.contrib.auth.views import LoginView
from django.urls import path

from .forms import LoginForm
from .views import SignUpView

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(authentication_form=LoginForm, template_name="registration/login.html"),
        name="login",
    ),
    path("signup/", SignUpView.as_view(), name="signup"),
]
