# In order/admin.py

from django.contrib import admin
from .models import CartItem, Order, OrderItem, Coupon

# ... (CartItemAdmin class is fine) ...
@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['user', 'product_name', 'color', 'quantity', 'added_at', 'get_product_pack_composition']
    list_filter = ['color', 'added_at']
    search_fields = ['product_name', 'user__phone_number']

    def get_product_pack_composition(self, obj):
        return obj.product.sizes if obj.product else 'N/A'
    get_product_pack_composition.short_description = 'Pack Composition'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = [
        'product', 'color', 'product_name', 'quantity', 
        'actual_price', 'discount_price', 
        'price_per_piece_at_purchase', 'total_pieces_in_set_at_purchase'
    ]
    def has_add_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


# ✅ UPDATED OrderAdmin CLASS
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Replaced 'status' with the two new status fields
    list_display = ['id', 'full_name', 'payment_status', 'shipping_status', 'grand_total', 'tracking_id', 'created_at']
    
    # Replaced 'status' with the two new status fields for filtering
    list_filter = ['payment_status', 'shipping_status', 'payment_method', 'created_at']
    
    search_fields = ['user__phone_number', 'full_name', 'tracking_id']
    
    # Removed shipping_service_name, tracking_id, payment_status, and shipping_status from here
    readonly_fields = [
        'user', 'payment_id', 'razorpay_order_id', 'created_at', 'subtotal', 
        'shipping_charge', 'discount_amount', 'grand_total', 'shipping_label_url'
    ]
    
    inlines = [OrderItemInline]


# ... (OrderItemAdmin and CouponAdmin classes are fine) ...
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product_name', 'color', 'quantity', 'get_product_pack_composition']
    list_filter = ['color']
    search_fields = ['product_name']

    def get_product_pack_composition(self, obj):
        return obj.product.sizes if obj.product else 'N/A'
    get_product_pack_composition.short_description = 'Pack Composition'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'min_order_amount', 'active', 'expires_at']
    list_filter = ['discount_type', 'active', 'expires_at']
    search_fields = ['code']