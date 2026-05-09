from django.contrib.admin import AdminSite
from django.contrib.auth.admin import UserAdmin
from django.shortcuts import redirect
from django.urls import reverse_lazy

from accounts.admin import ProfileAdmin, AdminPromotionAdmin
from accounts.models import Profile, AdminPromotion
from core.admin import ContactMessageAdmin, BlogPostAdmin
from core.models import ContactMessage, BlogPost
from properties.admin import PropertyAdmin, FeatureAdmin, TourRequestAdmin
from properties.models import Property, Feature, TourRequest, PropertyImage
from django.contrib.auth.models import User


class RealEstateAdminSite(AdminSite):
    index_title = "Dashboard"
    login_form = None

    def login(self, request, extra_context=None):
        return redirect(str(reverse_lazy('login')))

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}

        extra_context["users_count"] = User.objects.count()
        extra_context["properties_count"] = Property.objects.count()
        extra_context["pending_count"] = Property.objects.filter(status="pending").count()
        extra_context["features_count"] = Feature.objects.count()

        extra_context["sale_count"] = Property.objects.filter(listing_type="sale").count()
        extra_context["rent_count"] = Property.objects.filter(listing_type="rent").count()

        extra_context["latest_properties"] = Property.objects.order_by("-created_at")[:5]
        extra_context["latest_tour_requests"] = TourRequest.objects.order_by("-created_at")[:5]

        return super().index(request, extra_context=extra_context)


class CustomUserAdmin(UserAdmin):
    def has_module_permission(self, request):
        return request.user.is_superuser


admin_site = RealEstateAdminSite(name="realestate_admin")
admin_site.register(User, CustomUserAdmin)
admin_site.register(Property, PropertyAdmin)
admin_site.register(Feature, FeatureAdmin)
admin_site.register(TourRequest, TourRequestAdmin)
admin_site.register(Profile, ProfileAdmin)
admin_site.register(AdminPromotion, AdminPromotionAdmin)
admin_site.register(ContactMessage, ContactMessageAdmin)
admin_site.register(BlogPost, BlogPostAdmin)
