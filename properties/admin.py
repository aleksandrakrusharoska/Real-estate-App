from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html

from properties.models import Property, PropertyImage, TourRequest


class PropertyImageInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        covers = 0
        for form in self.forms:
            if not getattr(form, "cleaned_data", None):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            if form.cleaned_data.get("is_cover"):
                covers += 1

        if covers > 1:
            raise ValidationError("You can select only one cover image.")


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 3
    formset = PropertyImageInlineFormSet

    class Media:
        js = ("admin/js/cover_radio.js",)


class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "listing_type_badge",
        "city",
        "property_type",
        "owner",
        "status_badge",
        "created_at",
    )
    list_filter = ("listing_type","status", "city", "property_type")
    search_fields = ("name", "description", "city", "location")
    filter_horizontal = ("features",)
    actions = ["approve_property"]
    exclude = ('owner',)
    inlines = [PropertyImageInline]

    def listing_type_badge(self, obj):
        styles = {
            "sale": "background-color: rgba(220, 38, 38, 0.1); color: #dc2626; border: 1.5px solid #dc2626;",
            "rent": "background-color: rgba(37, 99, 235, 0.1); color: #2563eb; border: 1.5px solid #2563eb;",
        }
        style = styles.get(obj.listing_type, "background-color: rgba(107, 114, 128, 0.1); color: #6b7280; border: 1.5px solid #6b7280;")
        label = "For Sale" if obj.listing_type == "sale" else "For Rent"
        return format_html(
            '<span style="display: inline-block; padding: 6px 12px; {}; '
            'border-radius: 6px; font-weight: 400; font-size: 12px;">{}</span>',
            style,
            label
        )
    listing_type_badge.short_description = "Listing Type"

    def status_badge(self, obj):
        styles = {
            "pending": "background-color: rgba(245, 158, 11, 0.08); color: #f59e0b;",
            "approved": "background-color: rgba(16, 185, 129, 0.08); color: #10b981;",
            "rejected": "background-color: rgba(239, 68, 68, 0.08); color: #ef4444;",
        }
        style = styles.get(obj.status, "background-color: rgba(107, 114, 128, 0.08); color: #6b7280;")
        status_label = obj.get_status_display()
        return format_html(
            '<span style="display: inline-block; padding: 8px 14px; {}; '
            'border-radius: 20px; font-weight: 400; font-size: 12px;">{}</span>',
            style,
            status_label
        )
    status_badge.short_description = "Status"

    def get_exclude(self, request, obj=None):
        excluded = list(self.exclude)

        if obj is None:
            excluded.append("status")

        return excluded

    def get_readonly_fields(self, request, obj=None):
        readonly = []

        if obj:
            if obj.owner.profile.is_admin:
                readonly.append("status")
            else:
                if not (request.user.profile.is_admin or request.user.is_superuser):
                    readonly.append("status")

        return readonly

    def save_model(self, request, obj, form, change):
        if not change:
            obj.owner = request.user

            if request.user.profile.is_admin or request.user.is_superuser:
                obj.status = "approved"
            else:
                obj.status = "pending"
        else:
            old = Property.objects.get(pk=obj.pk)
            critical_fields = ["price", "description"]

            if obj.owner.profile.is_user:
                for field in critical_fields:
                    if getattr(old, field) != getattr(obj, field):
                        obj.status = "pending"
                        break

            if old.status == "rejected" and obj.status == "rejected":
                obj.status = "pending"

        super().save_model(request, obj, form, change)

    @admin.action(description="Approve selected properties")
    def approve_property(self, request, queryset):
        queryset.update(status="approved")


class TourRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "property", "email", "phone", "created_at")
    list_filter = ("created_at", "property")
    search_fields = ("name", "email", "phone", "property__name")
    readonly_fields = ("name", "property", "email", "phone", "message", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


class FeatureAdmin(admin.ModelAdmin):
    search_fields = ("name",)
