from django.urls import path

from core.views import home, about, contact, blog_list, blog_detail

urlpatterns = [
    path("", home, name="home"),
    path("about/", about, name="about"),
    path("contact/", contact, name="contact"),
    path("blog/", blog_list, name="blog_list"),
    path("blog/<slug:slug>/", blog_detail, name="blog_detail"),
]
