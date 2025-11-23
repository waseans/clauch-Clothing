from django.urls import path
from . import views

urlpatterns = [
    path("blogs/", views.blog_list, name="blog_list"),
    path("blogs/<slug:slug>/", views.blog_detail, name="blog_detail"),
]
