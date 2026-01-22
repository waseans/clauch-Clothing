import os
import re
import random
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings
from ckeditor.fields import RichTextField
from django.db.models import CheckConstraint, Q
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

# -----------------------------------------------------------
# 1. SEO HELPERS: Dynamic Path & Filenaming
# -----------------------------------------------------------
def get_category_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    name = slugify(instance.name)
    return f'categories/{name}.{ext}'

def get_product_primary_path(instance, filename):
    ext = filename.split('.')[-1]
    name = slugify(instance.name)
    return f'products/primary/{name}.{ext}'

def get_product_hover_path(instance, filename):
    ext = filename.split('.')[-1]
    name = slugify(instance.name)
    return f'products/hover/{name}-hover.{ext}'

def get_variant_image_path(instance, filename):
    ext = filename.split('.')[-1]
    # Creates: products/colors/product-slug-color-slug.jpg
    name = f"{instance.color.product.slug}-{instance.color.slug}"
    return f'products/colors/{name}.{ext}'

# -----------------------------------------------------------
# 2. CATEGORY MODEL
# -----------------------------------------------------------
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    image = models.ImageField(upload_to=get_category_upload_path)
    
    # SEO Field
    image_alt = models.CharField(
        max_length=160, 
        blank=True, 
        help_text="SEO text for category image (e.g., 'Summer Collection T-Shirts')"
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

# -----------------------------------------------------------
# 3. PRODUCT MODEL
# -----------------------------------------------------------
class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    categories = models.ManyToManyField('Category', related_name='products')

    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price for one full set.")
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         help_text="Discounted price for one full set.")

    sizes = models.CharField(max_length=255, help_text="Composition: e.g., '1S, 2M, 1L'.")
    
    # SEO Image Fields
    primary_image = models.ImageField(upload_to=get_product_primary_path)
    primary_image_alt = models.CharField(max_length=160, blank=True, help_text="SEO alt text for main image")
    
    hover_image = models.ImageField(upload_to=get_product_hover_path, null=True, blank=True)
    hover_image_alt = models.CharField(max_length=160, blank=True, help_text="SEO alt text for hover image")
    
    size_chart = models.ImageField(upload_to='products/size_charts/', null=True, blank=True)
    
    # Shipping Details
    weight = models.FloatField(default=0.5)
    length = models.FloatField(default=30.0)
    width = models.FloatField(default=20.0)
    height = models.FloatField(default=10.0)

    # General Info
    rating = models.FloatField(default=0.0)
    reviews_count = models.PositiveIntegerField(default=0)
    description = models.TextField()
    html_description = RichTextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_total_pieces_in_set(self):
        total_pieces = 0
        pieces_matches = re.findall(r'(\d+)?([A-Z]{1,3}|\d{2})', self.sizes.replace(' ', ''))
        for count_str, _ in pieces_matches:
            try:
                total_pieces += int(count_str) if count_str else 1
            except ValueError: continue
        return total_pieces

    def get_current_price_per_piece(self):
        total = self.get_total_pieces_in_set()
        if total == 0: return 0.00
        price = self.discount_price if self.discount_price else self.price
        return price / total

# -----------------------------------------------------------
# 4. PRODUCT COLOR VARIANT
# -----------------------------------------------------------
class ProductColor(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='colors')
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=60, blank=True)
    hex_code = models.CharField(max_length=7)
    is_primary = models.BooleanField(default=False)
    stock = models.PositiveIntegerField(default=0)

    # ✅ ADDED BACK: Fixed "Out of Stock" frontend issue
    @property
    def is_in_stock(self):
        return self.stock > 0

    def save(self, *args, **kwargs):
        if not self.slug:
            # Reverted to your old robust slug logic
            base_slug = slugify(self.name)
            existing_slugs = ProductColor.objects.filter(product=self.product, slug__startswith=base_slug).values_list('slug', flat=True)
            if base_slug not in existing_slugs:
                self.slug = base_slug
            else:
                counter = 1
                new_slug = f"{base_slug}-{counter}"
                while new_slug in existing_slugs:
                    counter += 1
                    new_slug = f"{base_slug}-{counter}"
                self.slug = new_slug
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('product', 'slug')
        constraints = [CheckConstraint(check=Q(stock__gte=0), name='stock_must_be_positive')]

    def __str__(self):
        return f"{self.product.name} - {self.name} ({self.stock} sets left)"

# -----------------------------------------------------------
# 5. PRODUCT IMAGES (Per Color)
# -----------------------------------------------------------
class ProductImage(models.Model):
    color = models.ForeignKey(ProductColor, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=get_variant_image_path)
    alt_text = models.CharField(max_length=160, blank=True, help_text="SEO alt text for variant image")

    def __str__(self):
        return f"Image for {self.color}"

# -----------------------------------------------------------
# 6. OTP MODEL
# -----------------------------------------------------------
class OTP(models.Model):
    phone_number = models.CharField(max_length=15)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)

# -----------------------------------------------------------
# 7. USER MODELS
# -----------------------------------------------------------
class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("Phone number is required")
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(phone_number, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(max_length=15, unique=True)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    gst_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.phone_number

# -----------------------------------------------------------
# 8. COURSE MODELS
# -----------------------------------------------------------
class Course(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    short_description = models.TextField()
    long_description = models.TextField()
    html_content = RichTextField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to="courses/thumbnails/")
    banner = models.ImageField(upload_to="courses/banners/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_display_price(self):
        return self.discount_price if self.discount_price else self.price

    def has_discount(self):
        return self.discount_price is not None

class CourseVideo(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="videos")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    thumbnail = models.ImageField(upload_to="courses/videos/thumbnails/", blank=True, null=True)
    video_file = models.FileField(upload_to="courses/videos/")

    def __str__(self):
        return f"{self.course.title} - {self.title}"

class CoursePDF(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="pdfs")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to="courses/pdfs/")

    def __str__(self):
        return f"{self.course.title} - {self.title}"

class CourseEnrollment(models.Model):
    STATUS_CHOICES = (("active", "Active"), ("pending", "Pending"), ("cancelled", "Cancelled"))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    price_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "course")

    def __str__(self):
        return f"{self.user} - {self.course} ({self.status})"