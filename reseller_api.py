"""
Reseller API Client for Telegram Store Bot
Auto-delivers products via xyzcheats.com API after payment approval.
"""

import requests
import time
import json
import os

# ========== CONFIG (loaded from env) ==========
from dotenv import load_dotenv
load_dotenv()

RESELLER_API_URL = os.getenv("RESELLER_API_URL", "https://xyzcheats.com/api/reseller_v1.php")
RESELLER_API_KEY = os.getenv("RESELLER_API_KEY", "5767866fbf5b04d2e9d881c9f5e935d0")
RESELLER_MASTER_KEY = os.getenv("RESELLER_MASTER_KEY", "a7f3e8b2c9d1f4a6b8c2d5e9f1a3b6c8")
RESELLER_MAX_RETRIES = int(os.getenv("RESELLER_MAX_RETRIES", "2"))
RESELLER_RETRY_DELAY = int(os.getenv("RESELLER_RETRY_DELAY", "3"))

# ========== HELPER: parse duration ==========

def parse_duration_text(duration_str):
    """
    Parse duration string like '30 Days', '1 Month', '1 Season' into a
    duration string for the API. xyzcheats expects singular 'Day' format.
    Returns string like '1 Day', '7 Day', '30 Day'.
    """
    if not duration_str:
        return "30 Day"  # default

    import re
    num_match = re.search(r'(\d+)', duration_str)
    num = int(num_match.group(1)) if num_match else 1

    dur_lower = duration_str.strip().lower()

    if 'day' in dur_lower:
        return f"{num} Day"
    elif 'week' in dur_lower:
        return f"{num * 7} Day"
    elif 'month' in dur_lower or 'mois' in dur_lower:
        return f"{num * 30} Day"
    elif 'year' in dur_lower:
        return f"{num * 365} Day"
    elif 'season' in dur_lower:
        return "30 Day"
    elif 'lifetime' in dur_lower or 'permanent' in dur_lower:
        return "9999 Day"
    else:
        return f"{num} Day"


def get_product_pid(product_id):
    """Get the reseller product_pid from the products table."""
    from database import get_db
    try:
        with get_db() as conn:
            r = conn.execute(
                "SELECT product_pid FROM products WHERE id=? AND is_active=1",
                (product_id,)
            ).fetchone()
            if r and r["product_pid"]:
                return int(r["product_pid"])
    except Exception:
        pass
    return None


def is_reseller_api_configured():
    """Check if reseller API is configured."""
    return bool(RESELLER_API_URL and RESELLER_API_KEY and RESELLER_MASTER_KEY)


def call_reseller_api(product_id, duration_text, order_id=None, max_retries=None):
    """
    Call the reseller API to purchase a license/key.

    Args:
        product_id: Internal product ID from the database
        duration_text: Duration string from the plan (e.g., '30 Days')
        order_id: For logging purposes
        max_retries: Override max retry count

    Returns:
        dict with keys:
            success (bool)
            key (str) — the delivered license/key/account
            raw_response (str) — the full API response text
            error (str) — error message if failed
    """
    from database import add_log

    if max_retries is None:
        max_retries = RESELLER_MAX_RETRIES

    pid = get_product_pid(product_id)
    if pid is None:
        return {
            "success": False,
            "key": "",
            "raw_response": "",
            "error": f"Reseller PID not configured for product ID {product_id}"
        }

    duration = parse_duration_text(duration_text)

    payload = {
        "api_key": RESELLER_API_KEY,
        "action": "buy",
        "product_id": str(pid),
        "duration": str(duration)
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "x-master-key": RESELLER_MASTER_KEY,
    }

    last_error = ""
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                time.sleep(RESELLER_RETRY_DELAY)

            response = requests.post(
                RESELLER_API_URL,
                data=payload,
                headers=headers,
                timeout=30
            )

            raw_text = response.text.strip()

            # Log attempt
            log_prefix = f"[Attempt {attempt+1}/{max_retries+1}]" if attempt > 0 else ""
            add_log(
                "reseller_api",
                None,
                f"Order {order_id}: {log_prefix} PID={pid}, duration={duration} -> {raw_text[:200]}"
            )

            # Try JSON response
            try:
                resp_json = response.json()
                # Check for success indicators
                if isinstance(resp_json, dict):
                    if resp_json.get("status") == "success" or resp_json.get("success"):
                        key = str(resp_json.get("key") or resp_json.get("license") or resp_json.get("account") or resp_json.get("message") or raw_text)
                        return {
                            "success": True,
                            "key": key,
                            "raw_response": raw_text,
                            "error": ""
                        }
                    elif resp_json.get("status") == "error" or resp_json.get("error"):
                        last_error = str(resp_json.get("message") or resp_json.get("error") or raw_text)
                        # Don't retry on certain errors
                        if "insufficient" in last_error.lower() or "balance" in last_error.lower():
                            return {"success": False, "key": "", "raw_response": raw_text, "error": last_error}
                        continue
                    else:
                        # Unknown JSON structure — treat as success if no error
                        key = str(resp_json.get("key") or resp_json.get("license") or resp_json.get("account") or resp_json.get("data") or raw_text)
                        return {
                            "success": True,
                            "key": key,
                            "raw_response": raw_text,
                            "error": ""
                        }
                # Array response
                elif isinstance(resp_json, list) and len(resp_json) > 0:
                    item = resp_json[0]
                    if isinstance(item, dict):
                        key = str(item.get("key") or item.get("license") or item.get("account") or str(item))
                        return {"success": True, "key": key, "raw_response": raw_text, "error": ""}
            except (json.JSONDecodeError, ValueError):
                pass

            # Plain text response — treat as key if it looks like one
            # Common patterns: key=xxx, account:xxx, or just a raw key string
            raw_lower = raw_text.lower()

            # Check for error keywords
            error_keywords = ["error", "failed", "invalid", "insufficient", "disabled", "not found", "maintenance"]
            if any(kw in raw_lower for kw in error_keywords):
                last_error = raw_text
                continue

            # Check for success keywords
            success_keywords = ["success", "purchased", "delivered", "key:", "license:", "account:", "login:"]
            if any(kw in raw_lower for kw in success_keywords) or len(raw_text) > 3:
                # Extract key from known formats
                for sep in ["key:", "license:", "account:", "login:", "="]:
                    if sep in raw_lower:
                        idx = raw_lower.index(sep)
                        extracted = raw_text[idx + len(sep):].split("\n")[0].strip()
                        if extracted:
                            return {"success": True, "key": extracted, "raw_response": raw_text, "error": ""}

                # If it's short and doesn't look like an error — treat as key
                if len(raw_text) < 500:
                    return {"success": True, "key": raw_text, "raw_response": raw_text, "error": ""}

            last_error = raw_text

        except requests.exceptions.Timeout:
            last_error = "API request timed out"
            continue
        except requests.exceptions.ConnectionError:
            last_error = "API connection failed"
            continue
        except Exception as e:
            last_error = f"API error: {str(e)}"
            continue

    return {"success": False, "key": "", "raw_response": last_error, "error": last_error}
