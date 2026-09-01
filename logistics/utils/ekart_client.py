"""
logistics/utils/ekart_client.py
===============================
Base HTTP Client for Ekart API.
Handles token caching, automatic Bearer injection, and audit logging.
Includes WAF bypass headers and connection retries.
"""

import time
import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import APIException

from logistics.models import EkartAuthToken, LogisticsAPILog

logger = logging.getLogger("logistics")

class EkartAPIException(APIException):
    status_code = 502
    default_detail = "Ekart API communication failed."
    default_code = "bad_gateway"


class EkartClient:
    def __init__(self):
        self.base_url = getattr(settings, "EKART_BASE_URL", "https://api.ekartlogistics.in").rstrip("/")
        self.client_id = getattr(settings, "EKART_CLIENT_ID", "")
        self.username = getattr(settings, "EKART_USERNAME", "")
        self.password = getattr(settings, "EKART_PASSWORD", "")
        
        # 1. Setup session with Retries to handle random SSL drops
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[ 502, 503, 504 ])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

        # 2. Add Standard Browser Headers to bypass WAF (Fixes SSLEOFError)
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def _log_request(self, method: str, endpoint: str, req_payload: dict, res_payload: dict, status_code: int, duration_ms: int):
        """Privately log the request to the DB."""
        safe_req = req_payload.copy() if req_payload else {}
        if "password" in safe_req:
            safe_req["password"] = "********"

        LogisticsAPILog.objects.create(
            endpoint=endpoint,
            method=method.upper(),
            request_payload=safe_req,
            response_payload=res_payload,
            status_code=status_code,
            response_time_ms=duration_ms
        )

    def get_valid_token(self, force_refresh=False) -> str:
        """
        Retrieves a valid Bearer token.
        Queries the DB first. If expired or force_refresh=True, fetches a new one.
        """
        if not force_refresh:
            active_token = EkartAuthToken.objects.filter(is_deleted=False).order_by("-expires_at").first()
            if active_token and active_token.is_valid():
                return active_token.access_token

        # Fetch new token
        endpoint = f"/integrations/v2/auth/token/{self.client_id}"
        url = f"{self.base_url}{endpoint}"
        payload = {
            "username": self.username,
            "password": self.password
        }

        start_time = time.time()
        try:
            # Use self.session and pass default_headers
            response = self.session.post(url, json=payload, headers=self.default_headers, timeout=15)
            duration_ms = int((time.time() - start_time) * 1000)
            res_data = response.json() if response.text else {}
            
            self._log_request("POST", endpoint, payload, res_data, response.status_code, duration_ms)
            
            if response.status_code != 200:
                logger.error(f"Ekart Auth Failed: {res_data}")
                raise EkartAPIException("Failed to authenticate with Ekart. Check credentials or IP whitelist.")

            expires_in_seconds = res_data.get("expires_in", 86400)
            expires_at = timezone.now() + timezone.timedelta(seconds=expires_in_seconds)

            new_token = EkartAuthToken.objects.create(
                access_token=res_data.get("access_token"),
                token_type=res_data.get("token_type", "Bearer"),
                scope=res_data.get("scope", "core:all"),
                expires_at=expires_at
            )
            return new_token.access_token

        except requests.RequestException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_request("POST", endpoint, payload, {"error": str(e)}, 500, duration_ms)
            logger.error(f"Ekart SSL/Network Error: {str(e)}")
            raise EkartAPIException(f"Network error while connecting to Ekart: {str(e)}")

    def request(self, method: str, endpoint: str, payload: dict = None, params: dict = None) -> dict:
        """
        Generic request executor. Automatically injects the Bearer token.
        """
        token = self.get_valid_token()
        
        # Merge Bearer token with our WAF bypass headers
        headers = self.default_headers.copy()
        headers["Authorization"] = f"Bearer {token}"
        
        url = f"{self.base_url}{endpoint}"

        start_time = time.time()
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=headers, params=params, timeout=15)
            elif method.upper() == "POST":
                response = self.session.post(url, headers=headers, json=payload, params=params, timeout=15)
            elif method.upper() == "PUT":
                response = self.session.put(url, headers=headers, json=payload, params=params, timeout=15)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, headers=headers, params=params, timeout=15)
            else:
                raise ValueError("Unsupported HTTP Method")

            duration_ms = int((time.time() - start_time) * 1000)
            
            try:
                res_data = response.json()
            except ValueError:
                res_data = {"raw_text": response.text}

            self._log_request(method, endpoint, payload or params, res_data, response.status_code, duration_ms)

            return {
                "status_code": response.status_code,
                "data": res_data
            }

        except requests.RequestException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_request(method, endpoint, payload or params, {"error": str(e)}, 500, duration_ms)
            raise EkartAPIException(f"Network error: {str(e)}")