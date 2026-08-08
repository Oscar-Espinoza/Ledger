from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Project user model, custom from day one so it can evolve without a painful migration."""
