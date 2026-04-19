"""
Simulates TikTok Shop sending webhook events to your merchant server.
Run this in a second terminal after starting main.py.
"""

import hmac
import hashlib
import json
import time
import httpx

WEBHOOK_SECRET = "my_secret_key_123"
SERVER_URL = "http://localhost:8000"


def send_event(event_type: str, data: dict):
    payload = json.dumps({"type": event_type, "data": data}).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()

    response = httpx.post(
        f"{SERVER_URL}/webhook",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "X-TikTok-Signature": signature,
        },
    )
    status = "OK" if response.status_code == 200 else f"ERROR {response.status_code}"
    print(f"[SIMULATOR] {event_type:<25} → {status}")
    return response


def query(method: str, path: str, label: str):
    fn = httpx.get if method == "GET" else httpx.post
    r = fn(f"{SERVER_URL}{path}")
    print(f"\n[API] {method} {path}  ({label})")
    print(json.dumps(r.json(), indent=2))


def run_demo():
    print("=" * 50)
    print("  TikTok Shop Integration Demo")
    print("=" * 50)

    # 1. Customer places an order
    send_event("order.created", {
        "order_id": "ORD-001",
        "customer": {"name": "Alice Chen", "email": "alice@example.com"},
        "items": [
            {"sku": "SKU001", "name": "Wireless Earbuds", "quantity": 1, "price": 29.99},
            {"sku": "SKU002", "name": "Phone Case",        "quantity": 2, "price":  9.99},
        ],
        "total": 49.97,
        "created_at": int(time.time()),
    })
    time.sleep(1)

    # 2. Payment goes through
    send_event("order.paid", {"order_id": "ORD-001"})
    time.sleep(1)

    # 3. Second order placed but then cancelled
    send_event("order.created", {
        "order_id": "ORD-002",
        "customer": {"name": "Bob Kim", "email": "bob@example.com"},
        "items": [{"sku": "SKU003", "name": "USB-C Cable", "quantity": 1, "price": 12.99}],
        "total": 12.99,
        "created_at": int(time.time()),
    })
    time.sleep(1)

    send_event("order.cancelled", {"order_id": "ORD-002"})
    time.sleep(1)

    # 4. Platform fires a low-stock alert
    send_event("inventory.low", {"sku": "SKU001", "stock": 5})
    time.sleep(1)

    # 5. Now call the REST API to inspect state and fulfill the paid order
    print("\n" + "=" * 50)
    print("  Querying REST API")
    print("=" * 50)

    query("GET",  "/orders",              "all orders")
    query("GET",  "/orders/ORD-001",      "single order")
    query("POST", "/orders/ORD-001/fulfill", "fulfill paid order")
    query("GET",  "/products/SKU001",     "check SKU001 stock after sales")


if __name__ == "__main__":
    run_demo()
