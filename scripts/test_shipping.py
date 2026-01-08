from types import SimpleNamespace
import requests

# Monkeypatch requests.post to inspect payload without calling external service
_original_post = requests.post

def fake_post(url, json=None, headers=None, timeout=None):
    print('\n==== outgoing iThink request ====')
    print('URL:', url)
    print('Payload:', json)
    class Resp:
        def raise_for_status(self):
            return None
        def json(self):
            # Minimal fake success response
            return {"status": "success", "data": [{"rate": "50", "logistic_name": "MockCourier"}]}
    return Resp()

requests.post = fake_post

from order.ithink_services import get_rate_for_checkout
from django.conf import settings
from decimal import Decimal
# For testing, raise our fallback per-kg so we can observe fallback being chosen in test
settings.SHIPPING_PER_KG_RATE = 60
settings.SHIPPING_MIN_CHARGE = 40

class FakeQS(list):
    def exists(self):
        return len(self) > 0

# Test product (weights in kg)
product = SimpleNamespace(weight=0.5, length=20, width=15, height=5)
item = SimpleNamespace(product=product, quantity=1)

print('\n--- Test: 1 set ---')
res1 = get_rate_for_checkout('440016', 100, FakeQS([item]), payment_method='Prepaid')
print('Carrier result:', res1)
# compute fallback and final similar to ajax flow
carrier_rate = Decimal(str(res1.get('total_charges')))
fallback = Decimal(str(settings.SHIPPING_PER_KG_RATE)) * Decimal(str( (item.product.weight * item.quantity) ))
if fallback < Decimal(str(settings.SHIPPING_MIN_CHARGE)):
    fallback = Decimal(str(settings.SHIPPING_MIN_CHARGE))
final1 = max(carrier_rate, fallback)
print('fallback:', fallback, 'final:', final1)

# Increase quantity and test again
item.quantity=4
print('\n--- Test: 4 sets ---')
res4 = get_rate_for_checkout('440016', 400, FakeQS([item]), payment_method='Prepaid')
print('Carrier result:', res4)
carrier_rate = Decimal(str(res4.get('total_charges')))
# compute total weight for items
total_w = item.product.weight * item.quantity
fallback = Decimal(str(settings.SHIPPING_PER_KG_RATE)) * Decimal(str(total_w))
if fallback < Decimal(str(settings.SHIPPING_MIN_CHARGE)):
    fallback = Decimal(str(settings.SHIPPING_MIN_CHARGE))
final4 = max(carrier_rate, fallback)
print('fallback:', fallback, 'final:', final4)

# Restore
requests.post = _original_post
