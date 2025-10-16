import requests
import hmac
import hashlib
import json
from typing import Dict, Optional
from config import NOWPAYMENTS_API_KEY, NOWPAYMENTS_IPN_SECRET, NOWPAYMENTS_API_URL, PACKAGE_PRICES

class NOWPayments:
    def __init__(self):
        self.api_key = NOWPAYMENTS_API_KEY
        self.ipn_secret = NOWPAYMENTS_IPN_SECRET
        self.api_url = NOWPAYMENTS_API_URL
        self.headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json'
        }

    def get_available_currencies(self) -> list:
        """Get list of available cryptocurrencies"""
        try:
            response = requests.get(
                f"{self.api_url}/currencies",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json().get('currencies', [])
            return []
        except Exception as e:
            print(f"Error getting currencies: {e}")
            return []

    def get_estimate(self, amount: float, currency_from: str = 'usd', currency_to: str = 'btc') -> Optional[Dict]:
        """Get estimated price in crypto"""
        try:
            response = requests.get(
                f"{self.api_url}/estimate",
                params={
                    'amount': amount,
                    'currency_from': currency_from,
                    'currency_to': currency_to
                },
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting estimate: {e}")
            return None

    def create_payment(self,
                      price_amount: float,
                      price_currency: str = 'usd',
                      pay_currency: str = 'btc',
                      order_id: str = None,
                      order_description: str = None,
                      ipn_callback_url: str = None) -> Optional[Dict]:
        """Create a payment"""
        try:
            payload = {
                'price_amount': price_amount,
                'price_currency': price_currency,
                'pay_currency': pay_currency,
                'order_id': order_id,
                'order_description': order_description
            }

            if ipn_callback_url:
                payload['ipn_callback_url'] = ipn_callback_url

            response = requests.post(
                f"{self.api_url}/payment",
                json=payload,
                headers=self.headers
            )

            if response.status_code == 200 or response.status_code == 201:
                return response.json()
            else:
                print(f"Payment creation failed: {response.text}")
                return None
        except Exception as e:
            print(f"Error creating payment: {e}")
            return None

    def create_invoice(self,
                      price_amount: float,
                      price_currency: str = 'usd',
                      order_id: str = None,
                      order_description: str = None,
                      ipn_callback_url: str = None,
                      success_url: str = None,
                      cancel_url: str = None) -> Optional[Dict]:
        """Create an invoice (allows user to choose payment method)"""
        try:
            payload = {
                'price_amount': price_amount,
                'price_currency': price_currency,
                'order_id': order_id,
                'order_description': order_description
            }

            if ipn_callback_url:
                payload['ipn_callback_url'] = ipn_callback_url
            if success_url:
                payload['success_url'] = success_url
            if cancel_url:
                payload['cancel_url'] = cancel_url

            response = requests.post(
                f"{self.api_url}/invoice",
                json=payload,
                headers=self.headers
            )

            if response.status_code == 200 or response.status_code == 201:
                return response.json()
            else:
                print(f"Invoice creation failed: {response.text}")
                return None
        except Exception as e:
            print(f"Error creating invoice: {e}")
            return None

    def get_payment_status(self, payment_id: str) -> Optional[Dict]:
        """Get payment status"""
        try:
            response = requests.get(
                f"{self.api_url}/payment/{payment_id}",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting payment status: {e}")
            return None

    def verify_ipn(self, request_data: dict, signature: str) -> bool:
        """Verify IPN callback signature"""
        try:
            sorted_data = json.dumps(request_data, sort_keys=True, separators=(',', ':'))
            expected_signature = hmac.new(
                self.ipn_secret.encode('utf-8'),
                sorted_data.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()

            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            print(f"Error verifying IPN: {e}")
            return False

    def get_minimum_payment_amount(self, currency: str) -> Optional[float]:
        """Get minimum payment amount for a currency"""
        try:
            response = requests.get(
                f"{self.api_url}/min-amount",
                params={'currency_from': 'usd', 'currency_to': currency},
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json().get('min_amount')
            return None
        except Exception as e:
            print(f"Error getting minimum amount: {e}")
            return None


def create_payment_for_package(user_id: int, package_id: str, pay_currency: str = 'btc') -> Optional[Dict]:
    """Create payment for a credits package"""
    if package_id not in PACKAGE_PRICES:
        return None

    package = PACKAGE_PRICES[package_id]
    np = NOWPayments()

    order_id = f"user{user_id}_pkg{package_id}_{int(datetime.now().timestamp())}"
    description = f"{package['credits'] + package['bonus']} créditos ({package['credits']} + {package['bonus']} bônus)"

    # Create invoice (allows user to choose payment method)
    result = np.create_invoice(
        price_amount=package['price'],
        price_currency='usd',
        order_id=order_id,
        order_description=description
    )

    return result


def get_payment_link(invoice_id: str) -> str:
    """Get payment link for invoice"""
    return f"https://nowpayments.io/payment/?iid={invoice_id}"


# Mock function for testing without API key
def create_mock_payment(user_id: int, package_id: str) -> Dict:
    """Create mock payment for testing"""
    if package_id not in PACKAGE_PRICES:
        return None

    package = PACKAGE_PRICES[package_id]

    return {
        'id': f'MOCK_{user_id}_{package_id}',
        'invoice_id': f'MOCK_INV_{user_id}_{package_id}',
        'order_id': f'user{user_id}_pkg{package_id}',
        'price_amount': package['price'],
        'price_currency': 'usd',
        'pay_amount': package['price'],
        'pay_currency': 'btc',
        'order_description': f"{package['credits'] + package['bonus']} créditos",
        'payment_status': 'waiting',
        'pay_address': '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
        'invoice_url': f'https://nowpayments.io/payment/?iid=MOCK_INV_{user_id}_{package_id}'
    }
