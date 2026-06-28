import requests
import base64
from datetime import datetime
from django.conf import settings
from .models import MpesaTransaction

class MpesaService:
    def __init__(self):
        self.config = settings.MPESA_CONFIG
        self.base_url = 'https://sandbox.safaricom.co.ke' if self.config['SANDBOX'] else 'https://api.safaricom.co.ke'
    
    def get_access_token(self):
        """Get M-Pesa access token"""
        api_url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        
        try:
            response = requests.get(
                api_url,
                auth=(self.config['CONSUMER_KEY'], self.config['CONSUMER_SECRET'])
            )
            return response.json().get('access_token')
        except Exception as e:
            print(f"Error getting access token: {e}")
            return None
    
    def generate_password(self):
        """Generate M-Pesa password for STK Push"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password_string = f"{self.config['SHORTCODE']}{self.config['PASSKEY']}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode('utf-8')
        return password, timestamp
    
    def stk_push(self, phone_number, amount, checkout_request_id):
        """Initiate STK Push"""
        access_token = self.get_access_token()
        if not access_token:
            return None, "Failed to get access token"
        
        password, timestamp = self.generate_password()
        
        # Format phone number (remove leading 0, add 254)
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        
        # Convert amount to integer (remove decimals)
        try:
            amount_int = int(float(amount))
        except (ValueError, TypeError):
            return None, f"Invalid amount: {amount}"
        
        api_url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "BusinessShortCode": self.config['SHORTCODE'],
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount_int,  # Use the converted integer
            "PartyA": phone_number,
            "PartyB": self.config['SHORTCODE'],
            "PhoneNumber": phone_number,
            "CallBackURL": self.config['CALLBACK_URL'],
            "AccountReference": self.config['ACCOUNT_REFERENCE'],
            "TransactionDesc": self.config['TRANSACTION_DESC']
        }
        
        try:
            response = requests.post(api_url, json=payload, headers=headers)
            response_data = response.json()
            
            if response.status_code == 200:
                return response_data, None
            else:
                return None, response_data.get('errorMessage', 'STK Push failed')
        except Exception as e:
            return None, str(e)
    
    def create_transaction(self, user, phone_number, amount, checkout_request_id):
        """Create M-Pesa transaction record"""
        return MpesaTransaction.objects.create(
            user=user,
            phone_number=phone_number,
            amount=amount,
            checkout_request_id=checkout_request_id
        )
    
    def update_transaction(self, checkout_request_id, **kwargs):
        """Update M-Pesa transaction"""
        try:
            transaction = MpesaTransaction.objects.get(checkout_request_id=checkout_request_id)
            for key, value in kwargs.items():
                setattr(transaction, key, value)
            transaction.save()
            return transaction
        except MpesaTransaction.DoesNotExist:
            return None