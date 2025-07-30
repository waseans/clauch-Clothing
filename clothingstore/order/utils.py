from user.models import Product, ProductColor
from .models import CartItem

def add_to_cart(request, product_id, size, color_id, quantity=1):
    product = Product.objects.get(id=product_id)
    color = ProductColor.objects.get(id=color_id)
    quantity = int(quantity)

    if request.user.is_authenticated:
        cart_item, created = CartItem.objects.get_or_create(
            user=request.user,
            product=product,
            size=size,
            color=color,
            defaults={
                'quantity': quantity,
                'product_name': product.name,
                'product_image': product.primary_image,
                'actual_price': product.price,
                'discount_price': product.discount_price,
            }
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
    else:
        cart = request.session.get('cart', {})
        key = f"{product_id}-{size}-{color_id}"
        item = cart.get(key, {})

        if item:
            item['quantity'] += quantity
        else:
            cart[key] = {
                'product_id': product.id,
                'size': size,
                'color_id': color.id,
                'quantity': quantity,
                'product_name': product.name,
                'product_image_url': product.primary_image.url,
                'actual_price': str(product.price),
                'discount_price': str(product.discount_price) if product.discount_price else None,
            }

        request.session['cart'] = cart
        request.session.modified = True
