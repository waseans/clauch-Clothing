from django.db import models
from user.models import CustomUser, Product, ProductColor

# --------------------------------------------------------------------------
# CartItem Model (Unchanged)
# --------------------------------------------------------------------------
class CartItem(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    color = models.ForeignKey(ProductColor, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1) # Quantity of PACKS/SETS
    product_name = models.CharField(max_length=255)
    product_image = models.ImageField(upload_to='cart_snapshots/')
    actual_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product', 'color')

    def __str__(self):
        color_info = f" ({self.color.name})" if self.color else ""
        return f"{self.product.name}{color_info} x{self.quantity} packs"


# --------------------------------------------------------------------------
# Order Model (Updated with Shipping Fields and Defaults)
# --------------------------------------------------------------------------
# order/models.py

class Order(models.Model):
    PAYMENT_CHOICES = (
        ('COD', 'Cash on Delivery'),
        ('RZP', 'Razorpay'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('SHIPMENT_FAILED', 'Shipment Failed'), # <-- NEW STATUS ADDED
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    )

    # --- Customer and Address Info ---
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)

    # --- Payment & Pricing Info ---
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES)
    payment_id = models.CharField(max_length=100, blank=True, null=True, help_text="The Razorpay Payment ID (pay_...)")
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True, help_text="The Razorpay Order ID (order_...)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total price of products before discount and shipping.")
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    coupon_code = models.CharField(max_length=50, blank=True, null=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="The final amount paid by the customer.")

    # 🚚 Shipping & Tracking Information
    shipping_service_name = models.CharField(max_length=100, blank=True, null=True, default=None, help_text="e.g., Delhivery, XpressBees")
    tracking_id = models.CharField(max_length=100, blank=True, null=True, default=None, help_text="AWB Number from the courier")
    shipping_label_url = models.URLField(blank=True, null=True, default=None, help_text="URL to the shipping label PDF")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} by {self.user.phone_number}"
# --------------------------------------------------------------------------
# OrderItem Model (Unchanged)
# --------------------------------------------------------------------------
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    color = models.ForeignKey(ProductColor, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    product_name = models.CharField(max_length=255)
    product_image = models.ImageField(upload_to='order_snapshots/')
    actual_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_piece_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
    total_pieces_in_set_at_purchase = models.PositiveIntegerField()

    def __str__(self):
        color_info = f" ({self.color.name})" if self.color else ""
        return f"{self.product_name}{color_info} x{self.quantity} packs"


# --------------------------------------------------------------------------
# Coupon Model (Unchanged)
# --------------------------------------------------------------------------
class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=10, choices=[('PERCENT', 'Percent'), ('FLAT', 'Flat')])
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.code