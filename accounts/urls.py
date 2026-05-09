from django.urls import path
from django.contrib.auth.views import LogoutView

from accounts import views
from accounts.views import CustomLoginView

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),

    path("confirm-admin/<uuid:token>/", views.confirm_admin, name="confirm_admin"),

]
