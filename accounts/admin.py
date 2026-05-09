from django.contrib import admin, messages

from accounts.models import Profile, AdminPromotion
from accounts.services.admin_permissions import get_property_admin_group
from accounts.services.admin_promotions import send_admin_confirmation_email, send_downgrade_notification


class AdminPromotionAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "is_used", "is_expired", "created_at")
    list_filter = ("is_used",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "token", "created_at")

    def has_add_permission(self, request):
        return False


class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "is_superuser")

    def is_superuser(self, obj):
        return obj.user.is_superuser

    is_superuser.boolean = True
    is_superuser.short_description = "Superadmin"

    list_filter = ("role",)
    search_fields = ("user__username", "user__email")

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            return

        old_role = None

        if change:
            old_obj = Profile.objects.get(pk=obj.pk)
            old_role = old_obj.role

        if change and old_role == "USER" and obj.role == "ADMIN":
            obj.role = "USER"
            super().save_model(request, obj, form, change)

            send_admin_confirmation_email(request, obj)

            messages.info(request, "Admin confirmation email sent.")
            return

        if change and old_role == "ADMIN" and obj.role == "USER":
            super().save_model(request, obj, form, change)

            group = get_property_admin_group()
            obj.user.groups.remove(group)

            obj.user.is_staff = False
            obj.user.save()

            AdminPromotion.objects.filter(
                user=obj.user,
                is_used=False
            ).update(is_used=True)

            send_downgrade_notification(obj.user)

            messages.warning(request, f"Admin privileges for {obj.user.username} have been revoked.")
            return

        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True

        if request.user.profile.role == "ADMIN":

            if obj is None:
                return True

            if obj.user == request.user:
                return False

            if obj.role == "ADMIN":
                return False

            return obj.role == "USER"

        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True

        if request.user.profile.role == "ADMIN":
            if obj and obj.role == "ADMIN":
                return False
            return True

        return False
