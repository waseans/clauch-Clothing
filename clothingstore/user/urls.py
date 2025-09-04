from django.urls import path
from django.views.generic import TemplateView # Import TemplateView
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('search/', views.search_view, name='search'),
    path('search/results/', views.search_results_view, name='search_results'),
    path("search/suggestions/", views.search_suggestions, name="search_suggestions"),
    path('new/', views.new_view, name='new'),
    path('product/<slug:product_slug>/<slug:color_slug>/', views.product_detail_by_color, name='product_color_detail'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('ajax/get-color-images/<int:color_id>/', views.get_color_images, name='get_color_images'),
    path('cart/', views.cart_view, name='cart'),
    path('showroom/', views.showroom_view, name='showroom'),
    path('faq/', views.faq_view, name='faq'),
    path('shipping-return/', views.shipping_return_view, name='shipping_return'),
    path('contact/', views.contact_view, name='contact'),
    path('privacy-policy/', views.privacy_policy_view, name='privacy_policy'),
    path('terms-and-condition/', views.terms_and_condition_view, name='terms_and_condition'),
    path('account/', views.account_view, name='account'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    path("ajax/filter-popular-products/", views.filter_popular_products, name="filter_popular_products"),

    path('login/', views.login_view, name='login'),
    path('send-otp/', views.send_otp, name='send_otp'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.send_otp, name='resend_otp'),
    path('change-number/', views.change_number, name='change_number'),
    path('logout/', views.logout_view, name='logout'),
    
    # Add this line to handle the robots.txt file
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),

    path("course/", views.course_list, name="course_list"),   # /course/
    path("course/<slug:slug>/", views.course_detail, name="course_detail"),  # /course/<slug>/
    path("course/<slug:slug>/create-order/", views.create_order, name="create_order"),  # /course/<slug>/create-order/
    path("course/<slug:slug>/success/", views.payment_success, name="payment_success"), # /course/<slug>/success/
]