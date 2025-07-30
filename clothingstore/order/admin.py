from django.contrib import admin
from .models import CartItem, Order, OrderItem, Coupon # Ensure all models are imported

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    # Removed 'size' from list_display
    list_display = ['user', 'product_name', 'color', 'quantity', 'added_at', 'get_product_pack_composition']
    # Removed 'size' from list_filter
    list_filter = ['color', 'added_at']
    search_fields = ['product_name', 'user__phone_number']

    # Custom method to display the pack composition from the Product model
    def get_product_pack_composition(self, obj):
        # Access the 'sizes' field of the related Product object
        # This assumes that your Product model has a 'sizes' field
        # describing the pack (e.g., "1M, 1L, 1XL")
        return obj.product.sizes if obj.product else 'N/A'
    get_product_pack_composition.short_description = 'Pack Composition' # Column header in admin


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'full_name', 'phone', 'status', 'total_amount', 'created_at']
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['user__phone_number', 'full_name', 'email', 'address']
    readonly_fields = ['payment_id', 'created_at']
    # If you want to see OrderItems directly in the Order detail, you'd add an inline here
    # from your_app_name.admin import OrderItemInline # Assuming you define this inline
    # inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    # Removed 'size' from list_display
    list_display = ['order', 'product_name', 'color', 'quantity', 'get_product_pack_composition']
    # Removed 'size' from list_filter
    list_filter = ['color'] # No 'size' filter anymore
    search_fields = ['product_name']

    # Custom method to display the pack composition from the Product model
    def get_product_pack_composition(self, obj):
        # Access the 'sizes' field of the related Product object
        return obj.product.sizes if obj.product else 'N/A'
    get_product_pack_composition.short_description = 'Pack Composition'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'min_order_amount', 'active', 'expires_at']
    list_filter = ['discount_type', 'active', 'expires_at']
    search_fields = ['code']