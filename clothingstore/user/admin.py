from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Product, ProductColor, ProductImage

# -------------------------------------------
# Inline: Product Images under ProductColor
# -------------------------------------------
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'preview')
    readonly_fields = ('preview',)

    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:80px;" />', obj.image.url)
        return "No Image"
    preview.short_description = "Preview"

# -------------------------------------------
# Inline: ProductColor under Product
# -------------------------------------------
class ProductColorInline(admin.TabularInline):
    model = ProductColor
    extra = 1
    fields = ('name', 'hex_code', 'is_primary', 'color_box')
    readonly_fields = ('color_box',)
    show_change_link = True

    def color_box(self, obj):
        if obj.hex_code:
            return format_html('<div style="width: 30px; height: 30px; background-color:{}; border: 1px solid #ccc;"></div>', obj.hex_code)
        return "-"
    color_box.short_description = "Color"

# -------------------------------------------
# Admin: Product
# -------------------------------------------
# -------------------------------------------
# Admin: Product
# -------------------------------------------
class ProductAdmin(admin.ModelAdmin):
    # Added 'weight' to the list display for a quick overview
    list_display = ('thumbnail', 'name', 'price', 'discount_price', 'weight', 'get_categories', 'get_primary_color')
    list_filter = ('categories',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ('categories',)
    inlines = [ProductColorInline]

    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'categories', 'price', 'discount_price', 'sizes', 'size_chart')
        }),
        # New fieldset to group all shipping-related fields together
        ("Shipping Details (kg & cm)", {
            'fields': ('weight', 'length', 'width', 'height')
        }),
        ("Details", {
            'fields': ('description', 'html_description')
        }),
        ("Primary Settings", {
            'fields': ('primary_image', 'hover_image', 'rating', 'reviews_count')
        }),
    )

    def get_categories(self, obj):
        return ", ".join([cat.name for cat in obj.categories.all()])
    get_categories.short_description = 'Categories'

    def get_primary_color(self, obj):
        primary = obj.colors.filter(is_primary=True).first()
        return primary.name if primary else "-"
    get_primary_color.short_description = 'Primary Color'

    def thumbnail(self, obj):
        if obj.primary_image:
            return format_html('<img src="{}" style="height:50px;" />', obj.primary_image.url)
        return "-"
    thumbnail.short_description = 'Image'

# -------------------------------------------
# Admin: ProductColor
# -------------------------------------------
class ProductColorAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'hex_code', 'is_primary', 'color_box')
    list_filter = ('product', 'is_primary')
    search_fields = ('product__name', 'name')
    inlines = [ProductImageInline]

    def color_box(self, obj):
        if obj.hex_code:
            return format_html('<div style="width: 30px; height: 30px; background-color:{}; border: 1px solid #ccc;"></div>', obj.hex_code)
        return "-"
    color_box.short_description = "Color"

# -------------------------------------------
# Admin: Category
# -------------------------------------------
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'image_tag')
    search_fields = ('name',)

    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:40px;" />', obj.image.url)
        return "No Image"
    image_tag.short_description = 'Image'

# -------------------------------------------
# Register Admin Models
# -------------------------------------------
admin.site.register(Category, CategoryAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(ProductColor, ProductColorAdmin)


from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser

class CustomUserAdmin(BaseUserAdmin):
    model = CustomUser
    list_display = ('phone_number', 'full_name', 'email', 'is_staff', 'is_superuser')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('phone_number', 'full_name', 'email')
    ordering = ('phone_number',)

    fieldsets = (
        (None, {'fields': ('phone_number', 'full_name', 'email', 'password')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'full_name', 'email', 'password1', 'password2'),
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)



from django.contrib import admin
from .models import Course, CourseVideo, CoursePDF, CourseEnrollment


class CourseVideoInline(admin.TabularInline):
    model = CourseVideo
    extra = 1
    fields = ("title", "description", "thumbnail", "video_file")
    show_change_link = True


class CoursePDFInline(admin.TabularInline):
    model = CoursePDF
    extra = 1
    fields = ("title", "description", "file")
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "price", "discount_price", "created_at", "has_discount")
    list_filter = ("created_at",)
    search_fields = ("title", "short_description", "long_description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CourseVideoInline, CoursePDFInline]
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(CourseVideo)
class CourseVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "course")
    search_fields = ("title", "description")
    list_filter = ("course",)


@admin.register(CoursePDF)
class CoursePDFAdmin(admin.ModelAdmin):
    list_display = ("title", "course")
    search_fields = ("title", "description")
    list_filter = ("course",)


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "status", "price_paid", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "course__title")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
