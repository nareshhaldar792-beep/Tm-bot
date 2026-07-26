"""
Binance Pay API Integration
- Creates orders via Binance Pay API
- Generates QR payment codes
- Verifies payments
"""

import time
import hashlib
import hmac
import json
import uuid
import requests
from urllib.parse import urlencode

from config import (
    BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_MERCHANT_ID, BINANCE_API_BASE
)


class BinancePayAPI:
    def __init__(self):
        self.api_key = BINANCE_API_KEY
        self.secret_key = BINANCE_SECRET_KEY
        self.merchant_id = BINANCE_MERCHANT_ID
        self.base_url = BINANCE_API_BASE.rstrip("/")

    def is_configured(self):
        return bool(self.api_key and self.secret_key and self.merchant_id)

    def _generate_nonce(self):
        return str(uuid.uuid4()).replace("-", "")[:32]

    def _generate_signature(self, payload: dict) -> str:
        """Generate HMAC SHA-512 signature for Binance Pay API"""
        timestamp = str(int(time.time() * 1000))
        nonce = self._generate_nonce()
        body = json.dumps(payload) if payload else ""

        payload_to_sign = f"{timestamp}\n{nonce}\n{body}\n"
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            payload_to_sign.encode("utf-8"),
            hashlib.sha512
        ).hexdigest().upper()

        return timestamp, nonce, signature

    def _headers(self, payload: dict) -> dict:
        timestamp, nonce, signature = self._generate_signature(payload)
        return {
            "Content-Type": "application/json",
            "BinancePay-Timestamp": timestamp,
            "BinancePay-Nonce": nonce,
            "BinancePay-Certificate-SN": self.api_key,
            "BinancePay-Signature": signature,
        }

    def create_order(self, order_id: str, amount: float, currency: str = "USDT",
                     product_name: str = "Digital Product", product_desc: str = "",
                     buyer_id: str = "") -> dict:
        """
        Create a payment order via Binance Pay API.
        Returns: {success, qr_code_url, prepay_id, qr_content, error}
        """
        if not self.is_configured():
            return {"success": False, "error": "Binance Pay not configured"}

        endpoint = f"{self.base_url}/binancepay/openapi/v2/order"

        payload = {
            "merchantTradeNo": order_id,
            "tradeType": "WEB",
            "totalFee": amount,
            "currency": currency,
            "fiatCurrency": "USD",
            "productType": "Digital Product",
            "productName": product_name[:50] if product_name else "Digital Product",
            "productDetail": product_desc[:200] if product_desc else "",
            "buyerId": buyer_id,
            "returnUrl": "",
            "cancelUrl": "",
        }

        # Remove empty optional fields
        payload = {k: v for k, v in payload.items() if v != ""}

        try:
            headers = self._headers(payload)
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=15)
            data = resp.json()

            if data.get("status") == "SUCCESS" or data.get("code") == "000000":
                result = data.get("data", data)
                return {
                    "success": True,
                    "prepay_id": result.get("prepayId", ""),
                    "qr_code_url": result.get("qrCode", ""),
                    "qr_content": result.get("qrcodeLink", result.get("qrCode", "")),
                    "trade_no": result.get("tradeNo", ""),
                    "total_fee": result.get("totalFee", amount),
                    "currency": result.get("currency", currency),
                }
            else:
                return {
                    "success": False,
                    "error": data.get("errorMessage", data.get("msg", "Unknown error")),
                    "code": data.get("code", ""),
                }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Binance API timeout"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Could not connect to Binance API"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def query_order(self, prepay_id: str = "", merchant_trade_no: str = "") -> dict:
        """
        Query order status from Binance Pay API.
        """
        if not self.is_configured():
            return {"success": False, "error": "Binance Pay not configured"}

        endpoint = f"{self.base_url}/binancepay/openapi/v2/order/query"

        payload = {}
        if prepay_id:
            payload["prepayId"] = prepay_id
        if merchant_trade_no:
            payload["merchantTradeNo"] = merchant_trade_no

        if not payload:
            return {"success": False, "error": "No order identifier provided"}

        try:
            headers = self._headers(payload)
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=15)
            data = resp.json()

            if data.get("status") == "SUCCESS" or data.get("code") == "000000":
                result = data.get("data", data)
                status = result.get("status", result.get("tradeStatus", ""))
                return {
                    "success": True,
                    "status": status,
                    "prepay_id": result.get("prepayId", prepay_id),
                    "trade_no": result.get("tradeNo", ""),
                    "total_fee": result.get("totalFee", 0),
                    "currency": result.get("currency", ""),
                    "transaction_id": result.get("transactionId", ""),
                    "paid_at": result.get("payTime", ""),
                }
            else:
                return {
                    "success": False,
                    "error": data.get("errorMessage", data.get("msg", "Unknown error")),
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_order(self, merchant_trade_no: str) -> dict:
        """Close/cancel a Binance Pay order."""
        if not self.is_configured():
            return {"success": False, "error": "Binance Pay not configured"}

        endpoint = f"{self.base_url}/binancepay/openapi/v2/order/close"
        payload = {"merchantTradeNo": merchant_trade_no}

        try:
            headers = self._headers(payload)
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=15)
            data = resp.json()
            if data.get("status") == "SUCCESS" or data.get("code") == "000000":
                return {"success": True}
            return {"success": False, "error": data.get("errorMessage", str(data))}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton
binance_api = BinancePayAPI()
