import requests
import base64
import logging
import re
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from .models import MpesaTransaction

logger = logging.getLogger(__name__)


class MpesaService:
    def __init__(self):
        self.config = settings.MPESA_CONFIG
        self.base_url = (
            'https://sandbox.safaricom.co.ke'
            if self.config['SANDBOX']
            else 'https://api.safaricom.co.ke'
        )

    # ------------------------------------------------------------------ #
    # OAuth                                                                #
    # ------------------------------------------------------------------ #

    def get_access_token(self):
        """Get M-Pesa OAuth access token via client credentials."""
        api_url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        try:
            response = requests.get(
                api_url,
                auth=(self.config['CONSUMER_KEY'], self.config['CONSUMER_SECRET']),
                timeout=30,
            )
            response.raise_for_status()
            token = response.json().get('access_token')
            if not token:
                logger.error("OAuth response did not contain access_token: %s", response.text)
            return token
        except requests.exceptions.ConnectionError as e:
            logger.error("OAuth connection error: %s", e)
            return None
        except requests.exceptions.Timeout:
            logger.error("OAuth request timed out")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error("OAuth HTTP error %s: %s", e.response.status_code, e.response.text)
            return None
        except Exception as e:
            logger.error("OAuth unexpected error: %s", e)
            return None

    # ------------------------------------------------------------------ #
    # Password / timestamp                                                 #
    # ------------------------------------------------------------------ #

    def generate_password(self):
        """Generate base64 STK Push password and timestamp."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        raw = f"{self.config['SHORTCODE']}{self.config['PASSKEY']}{timestamp}"
        password = base64.b64encode(raw.encode()).decode('utf-8')
        return password, timestamp

    # ------------------------------------------------------------------ #
    # Phone number formatting                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def format_phone_number(phone_number):
        """
        Normalise a Kenyan phone number to 2547XXXXXXXX format.
        Accepts: 07XXXXXXXX, +2547XXXXXXXX, 2547XXXXXXXX
        Returns (formatted, error_message) tuple.
        """
        phone = re.sub(r'[\s\-\(\)]', '', str(phone_number))

        if phone.startswith('+254'):
            phone = phone[1:]          # strip leading +
        elif phone.startswith('07') or phone.startswith('01'):
            phone = '254' + phone[1:]
        elif phone.startswith('7') or phone.startswith('1'):
            phone = '254' + phone

        # Validate final format
        if not re.match(r'^2547\d{8}$|^2541\d{8}$', phone):
            return None, (
                f"Invalid phone number '{phone_number}'. "
                "Use format 07XXXXXXXX or 2547XXXXXXXX."
            )
        return phone, None

    # ------------------------------------------------------------------ #
    # STK Push                                                             #
    # ------------------------------------------------------------------ #

    def stk_push(self, phone_number, amount, account_reference=None):
        """
        Initiate M-Pesa STK Push (Lipa na M-Pesa Online).
        Returns (response_data, error_message).
        On success error_message is None and response_data contains CheckoutRequestID.
        """
        access_token = self.get_access_token()
        if not access_token:
            return None, "Failed to obtain OAuth access token. Check CONSUMER_KEY/SECRET."

        # Phone formatting
        formatted_phone, phone_error = self.format_phone_number(phone_number)
        if phone_error:
            return None, phone_error

        # Amount validation
        try:
            amount_int = int(float(amount))
            if amount_int <= 0:
                return None, "Amount must be greater than 0"
        except (ValueError, TypeError):
            return None, f"Invalid amount: {amount}"

        password, timestamp = self.generate_password()
        callback_url = self.config['CALLBACK_URL']
        ref = account_reference or self.config['ACCOUNT_REFERENCE']

        payload = {
            "BusinessShortCode": self.config['SHORTCODE'],
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount_int,
            "PartyA": formatted_phone,
            "PartyB": self.config['SHORTCODE'],
            "PhoneNumber": formatted_phone,
            "CallBackURL": callback_url,
            "AccountReference": ref,
            "TransactionDesc": self.config['TRANSACTION_DESC'],
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        api_url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            response_data = response.json()

            if response.status_code == 200 and response_data.get('ResponseCode') == '0':
                logger.info(
                    "STK Push initiated: CheckoutRequestID=%s",
                    response_data.get('CheckoutRequestID'),
                )
                return response_data, None
            else:
                error_msg = (
                    response_data.get('errorMessage')
                    or response_data.get('ResponseDescription')
                    or 'STK Push request failed'
                )
                logger.warning("STK Push failed (%s): %s", response.status_code, error_msg)
                return None, error_msg

        except requests.exceptions.ConnectionError as e:
            logger.error("STK Push connection error: %s", e)
            return None, "Network error — could not reach Safaricom API"
        except requests.exceptions.Timeout:
            logger.error("STK Push timed out")
            return None, "Request timed out — Safaricom API did not respond"
        except Exception as e:
            logger.error("STK Push unexpected error: %s", e)
            return None, str(e)

    # ------------------------------------------------------------------ #
    # Transaction query                                                    #
    # ------------------------------------------------------------------ #

    def query_stk_push_status(self, checkout_request_id):
        """
        Query the status of a pending STK Push from Safaricom.
        Returns (response_data, error_message).
        """
        access_token = self.get_access_token()
        if not access_token:
            return None, "Failed to obtain OAuth access token"

        password, timestamp = self.generate_password()

        payload = {
            "BusinessShortCode": self.config['SHORTCODE'],
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        api_url = f"{self.base_url}/mpesa/stkpushquery/v1/query"

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            return response.json(), None
        except Exception as e:
            logger.error("STK status query error: %s", e)
            return None, str(e)

    # ------------------------------------------------------------------ #
    # Transaction DB helpers                                               #
    # ------------------------------------------------------------------ #

    def create_transaction(self, user, phone_number, amount, checkout_request_id):
        """Create a PENDING MpesaTransaction record."""
        # Avoid duplicate checkout IDs
        existing = MpesaTransaction.objects.filter(
            checkout_request_id=checkout_request_id
        ).first()
        if existing:
            logger.warning(
                "Duplicate checkout_request_id=%s — returning existing record",
                checkout_request_id,
            )
            return existing

        return MpesaTransaction.objects.create(
            user=user,
            phone_number=phone_number,
            amount=amount,
            checkout_request_id=checkout_request_id,
        )

    def update_transaction(self, checkout_request_id, **kwargs):
        """Update an existing MpesaTransaction by checkout_request_id."""
        try:
            transaction = MpesaTransaction.objects.get(
                checkout_request_id=checkout_request_id
            )
            for key, value in kwargs.items():
                setattr(transaction, key, value)
            transaction.save()
            return transaction
        except MpesaTransaction.DoesNotExist:
            logger.warning(
                "update_transaction: no record found for checkout_request_id=%s",
                checkout_request_id,
            )
            return None

    def get_transaction(self, checkout_request_id):
        """Retrieve a transaction by checkout_request_id."""
        try:
            return MpesaTransaction.objects.get(checkout_request_id=checkout_request_id)
        except MpesaTransaction.DoesNotExist:
            return None

    def get_user_transactions(self, user, limit=50):
        """Return the most recent transactions for a user."""
        return MpesaTransaction.objects.filter(user=user).order_by('-date_requested')[:limit]
