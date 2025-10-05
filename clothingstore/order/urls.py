from django.urls import path
from . import views

from django.urls import path
from . import views

urlpatterns = [
    # Cart operations
    path('add/', views.add_to_cart_view, name='add_to_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/remove/<str:key>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/remove/db/<int:item_id>/', views.remove_from_cart, name='remove_from_cart_db'),
    path('cart/update/', views.update_cart_quantity, name='update_cart_quantity'),

    # Checkout process
    path('checkout/', views.checkout_view, name='checkout'),
    path('ajax/calculate-shipping/', views.ajax_calculate_shipping, name='ajax_calculate_shipping'),

    # Order status pages
    path('order/success/<int:order_id>/', views.order_success_view, name='order_success'),
    path('order/failure/', views.order_failure_view, name='order_failure'),

    # Razorpay webhook (optional, for server-side payment verification)
    path('razorpay/webhook/', views.razorpay_webhook, name='razorpay_webhook'),
     path('my-orders/', views.my_orders_view, name='my_orders'),
     path('order/<int:order_id>/', views.order_detail_view, name='order_detail'),
     path("account/update/", views.update_profile, name="update_profile"),

     path('admin/shipments/', views.admin_shipment_dashboard, name='admin_shipment_dashboard_default'), # Default view
     path('admin/shipments/<str:status_filter>/', views.admin_shipment_dashboard, name='admin_shipment_dashboard'), # Filtered view
    
     path('admin/create-shipment/<int:order_id>/', views.create_shipment_for_order, name='create_shipment_for_order'),

]

