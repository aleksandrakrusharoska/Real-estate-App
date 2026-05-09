from django.contrib import admin
from core.models import ContactMessage, BlogPost


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "is_published")
    list_filter = ("is_published",)
    search_fields = ("title",)
    prepopulated_fields = {"slug": ("title",)}

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "subject", "created_at", "is_read")
    list_filter = ("is_read",)
    search_fields = ("first_name", "last_name", "email", "message")
    readonly_fields = ("first_name", "last_name", "email", "phone", "subject", "message", "created_at")
    actions = ["mark_as_read"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Mark selected messages as read")
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)