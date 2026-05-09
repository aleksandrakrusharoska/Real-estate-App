from django.urls import path

from properties import views

urlpatterns = [
    path("", views.property_list, name="property_list"),
    path("create/", views.create_property, name="create_property"),
    path("<int:id>/", views.property_details, name="property_details"),
    path("edit/<int:pk>/", views.edit_property, name="edit_property"),
    path("delete/<int:pk>/", views.delete_property, name="delete_property"),
    path("generate-description/", views.generate_description, name="generate_description"),
    path("ai-chat/", views.ai_chat, name="ai_chat"),
    path("ai-chat/history/", views.ai_chat_history, name="ai_chat_history"),
    path("ai-chat/clear/", views.ai_chat_clear, name="ai_chat_clear"),
]
