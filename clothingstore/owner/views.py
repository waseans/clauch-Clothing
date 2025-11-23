from django.shortcuts import render

# Create your views here.
from django.shortcuts import render

def dashboard(request):
    return render(request, 'dashboard.html')




from django.shortcuts import render, get_object_or_404
from .models import Blog

def blog_list(request):
    blogs = Blog.objects.filter(is_published=True)
    return render(request, "blogs/blog_list.html", {"blogs": blogs})

def blog_detail(request, slug):
    blog = get_object_or_404(Blog, slug=slug, is_published=True)
    template_file = f"blogs/{blog.template}.html"
    return render(request, template_file, {"blog": blog})
