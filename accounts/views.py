from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.forms import RegisterForm, CustomAuthenticationForm
from accounts.models import AdminPromotion, Profile
from accounts.services.admin_permissions import get_property_admin_group
from properties.models import Property


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user, defaults={"role": Profile.USER})
    if request.user.is_staff or profile.role == Profile.ADMIN:
        return redirect("realestate_admin:index")
    properties = Property.objects.filter(owner=request.user)

    if request.method == "POST":
        profile.phone = request.POST.get("phone")
        profile.city = request.POST.get("city")
        profile.save()
        return redirect("profile")

    return render(request, "accounts/profile.html", {
        "profile": profile,
        "properties": properties
    })


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = CustomAuthenticationForm

    def get_success_url(self):
        next_url = self.request.GET.get("next")

        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url

        user = self.request.user

        if user.is_staff:
            return reverse_lazy("realestate_admin:index")

        return reverse_lazy("home")


def confirm_admin(request, token):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={request.path}")

    with transaction.atomic():

        promotion = get_object_or_404(
            AdminPromotion.objects.select_for_update(),
            token=token,
            is_used=False
        )

        if promotion.is_expired:
            promotion.delete()
            messages.error(request, "This promotion link has expired.")
            return redirect("home")

        user = promotion.user

        if request.user != user:
            logout(request)
            return redirect(f"{reverse('login')}?next={request.path}")

        if user.is_staff:
            messages.info(request, "You are already an administrator.")
            return redirect("profile")

        user.is_staff = True
        user.save()

        user.profile.role = "ADMIN"
        user.profile.save()

        group = get_property_admin_group()
        user.groups.add(group)

        login(request, user)

        AdminPromotion.objects.filter(
            user=user,
            is_used=False
        ).update(is_used=True)

    messages.success(request, "You are now an administrator.")
    return redirect("realestate_admin:index")
