from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse

from core.models import ContactMessage, BlogPost
from properties.models import Property


def about(request):
    return render(request, "core/about.html")

def contact(request):
    if request.method == "POST":
        ContactMessage.objects.create(
            first_name=request.POST.get("first_name", "").strip(),
            last_name=request.POST.get("last_name", "").strip(),
            email=request.POST.get("email", "").strip(),
            phone=request.POST.get("phone", "").strip(),
            subject=request.POST.get("subject", "").strip(),
            message=request.POST.get("message", "").strip(),
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return HttpResponse("OK")
        messages.success(request, "Your message has been sent! We'll get back to you shortly.")
        return redirect("contact")

    return render(request, "core/contact.html")


def home(request):
    all_approved = Property.objects.filter(status="approved").prefetch_related("images").order_by('-created_at')
    blog_posts = BlogPost.objects.filter(is_published=True)[:3]

    context = {
        'featured_prop': all_approved.first(),
        'side_properties': all_approved[1:4],
        'bottom_properties': all_approved[4:7],
        'blog_posts': blog_posts,
    }
    return render(request, "core/home.html", context)


def blog_list(request):
    posts = BlogPost.objects.filter(is_published=True)
    return render(request, "blog/list.html", {"posts": posts})


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    return render(request, "blog/detail.html", {"post": post})