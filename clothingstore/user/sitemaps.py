from django.contrib.sitemaps import Sitemap
from .models import Product # Assuming you have a Product model

class ProductSitemap(Sitemap):
    # This determines how frequently a page is likely to change.
    changefreq = "weekly"
    # This is a priority score for a page, from 0.0 to 1.0.
    priority = 0.9

    def items(self):
        # Return all objects that you want to include in the sitemap.
        return Product.objects.all()