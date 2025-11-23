from django.contrib import admin
from django.utils.html import format_html
from .models import Blog, BlogCategory, BlogTag


# ------------------------------
# CATEGORY ADMIN
# ------------------------------
@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


# ------------------------------
# TAG ADMIN
# ------------------------------
@admin.register(BlogTag)
class BlogTagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


# ------------------------------
# BLOG ADMIN
# ------------------------------
@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "admin_thumbnail",
        "category",
        "template",
        "status",
        "reading_time",
        "created_at",
        "is_published",
    )

    list_filter = (
        "template",
        "status",
        "is_published",
        "category",
        "tags",
        "created_at",
    )

    search_fields = (
        "title",
        "subtitle_1",
        "subtitle_2",
        "meta_description",
    )

    prepopulated_fields = {"slug": ("title",)}

    filter_horizontal = ("tags",)

    readonly_fields = (
        "admin_main_image",
        "admin_thumbnail",
        "reading_time",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Basic Info", {
            "fields": ("title", "slug", "template", "author", "status", "publish_at")
        }),

        ("Category & Tags", {
            "fields": ("category", "tags")
        }),

        ("SEO", {
            "fields": ("meta_description", "seo_keywords")
        }),

        ("Images", {
            "fields": (
                "thumbnail",
                "admin_thumbnail",
                "main_image",
                "admin_main_image",
                "image_1",
                "image_2",
                "image_3",
                "image_4",
                "image_5",
            )
        }),

        ("Content", {
            "fields": ("subtitle_1", "subtitle_2", "paragraph_1", "paragraph_2")
        }),

        ("Meta Data", {
            "fields": ("reading_time", "created_at", "updated_at", "is_published")
        }),
    )

    # ------------------------------
    # IMAGE PREVIEWS
    # ------------------------------
    def admin_thumbnail(self, obj):
        if obj.thumbnail:
            return format_html(
                '<img src="{}" width="60" height="60" style="border-radius:8px; object-fit:cover;" />',
                obj.thumbnail.url
            )
        return "No Thumbnail"

    admin_thumbnail.short_description = "Thumbnail"

    def admin_main_image(self, obj):
        if obj.main_image:
            return format_html(
                '<img src="{}" width="180" style="border-radius:10px; object-fit:cover;" />',
                obj.main_image.url
            )
        return "No Image"

    admin_main_image.short_description = "Main Image Preview"
