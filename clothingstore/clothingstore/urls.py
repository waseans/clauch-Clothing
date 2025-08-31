"""
URL configuration for clothingstore project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
import nested_admin
from django.urls import path

# Import sitemap-related classes
from django.contrib.sitemaps.views import sitemap
from user.sitemaps import ProductSitemap
from django.views.generic import TemplateView

sitemaps = {
    'products': ProductSitemap,
}

urlpatterns = [
    # Main project URLs
    path('admin/', admin.site.urls),
    path('', include('user.urls')),      # Main customer views
    path('owner/', include('owner.urls')),  # Owner dashboard
    path('order/', include('order.urls')),
    
    # Add the URL patterns for robots.txt and sitemap.xml
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)