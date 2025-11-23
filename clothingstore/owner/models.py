from django.db import models
from django.utils.text import slugify
from django.conf import settings
import math
import re

BLOG_TEMPLATES = (
    ("template1", "Template 1"),
    ("template2", "Template 2"),
    ("template3", "Template 3"),
    ("template4", "Template 4"),
)

BLOG_STATUS = (
    ("draft", "Draft"),
    ("published", "Published"),
    ("scheduled", "Scheduled"),
)


class BlogCategory(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class BlogTag(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Blog(models.Model):
    # BASIC INFO
    title = models.CharField(max_length=300)
    slug = models.SlugField(unique=True, blank=True)

    template = models.CharField(max_length=20, choices=BLOG_TEMPLATES)

    # SEO
    meta_description = models.CharField(max_length=300, blank=True, null=True)
    seo_keywords = models.CharField(max_length=400, blank=True, null=True)  # comma-separated

    # CATEGORY + TAGS
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, blank=True)
    tags = models.ManyToManyField(BlogTag, blank=True)

    # AUTHOR (FIXED)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # IMAGES
    thumbnail = models.ImageField(upload_to="blogs/thumbnails/", blank=True, null=True)
    main_image = models.ImageField(upload_to="blogs/", blank=True, null=True)

    image_1 = models.ImageField(upload_to="blogs/", blank=True, null=True)
    image_2 = models.ImageField(upload_to="blogs/", blank=True, null=True)
    image_3 = models.ImageField(upload_to="blogs/", blank=True, null=True)
    image_4 = models.ImageField(upload_to="blogs/", blank=True, null=True)
    image_5 = models.ImageField(upload_to="blogs/", blank=True, null=True)

    # TEXT CONTENT
    subtitle_1 = models.CharField(max_length=300, blank=True, null=True)
    subtitle_2 = models.CharField(max_length=300, blank=True, null=True)
    paragraph_1 = models.TextField(blank=True, null=True)
    paragraph_2 = models.TextField(blank=True, null=True)

    # META DATA
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(max_length=20, choices=BLOG_STATUS, default="draft")
    publish_at = models.DateTimeField(blank=True, null=True)

    is_published = models.BooleanField(default=True)

    # READING TIME
    reading_time = models.IntegerField(default=1)  # minutes

    def calculate_reading_time(self):
        """Counts text and returns estimated reading time."""
        text = f"{self.paragraph_1 or ''} {self.paragraph_2 or ''}"
        words = len(re.findall(r'\w+', text))
        return max(1, math.ceil(words / 200))  # 200 wpm reading speed

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        self.reading_time = self.calculate_reading_time()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
