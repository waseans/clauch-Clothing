from django.contrib import admin
from .models import CartItem, Order, OrderItem, Coupon # Ensure all models are imported

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['user', 'product_name', 'color', 'quantity', 'added_at', 'get_product_pack_composition']
    list_filter = ['color', 'added_at']
    search_fields = ['product_name', 'user__phone_number']

    def get_product_pack_composition(self, obj):
        return obj.product.sizes if obj.product else 'N/A'
    get_product_pack_composition.short_description = 'Pack Composition'


# This class allows you to see and edit order items directly within an order
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0 # Prevents showing extra, empty forms
    readonly_fields = [
        'product', 'color', 'product_name', 'quantity', 
        'actual_price', 'discount_price', 
        'price_per_piece_at_purchase', 'total_pieces_in_set_at_purchase'
    ]

    def has_add_permission(self, request, obj=None):
        return False # Disables adding new order items from the admin

    def has_delete_permission(self, request, obj=None):
        return False # Disables deleting order items from the admin


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Updated list_display to use new fields and remove 'total_amount'
    list_display = ['id', 'full_name', 'status', 'grand_total', 'shipping_charge', 'tracking_id', 'created_at']
    
    list_filter = ['status', 'payment_method', 'created_at']
    
    # Added 'tracking_id' to search fields for easy lookup
    search_fields = ['user__phone_number', 'full_name', 'tracking_id']
    
    readonly_fields = [
        'user', 'payment_id', 'created_at', 'subtotal', 
        'shipping_charge', 'discount_amount', 'grand_total',
        'shipping_service_name', 'tracking_id', 'shipping_label_url'
    ]
    
    inlines = [OrderItemInline] # Adds the OrderItem view to the Order page


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