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


def demo_normal_flow():
    """Standard order lifecycle: created → paid → fulfilled, plus a cancellation."""
    print("\n" + "=" * 50)
    print("  DEMO 1: Normal Order Flow")
    print("=" * 50)

    # Customer places an order
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

    # Payment confirmed — inventory deducted automatically
    send_event("order.paid", {"order_id": "ORD-001"})
    time.sleep(1)

    # Second order placed then cancelled
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

    # Platform fires a low-stock alert
    send_event("inventory.low", {"sku": "SKU001", "stock": 5})
    time.sleep(1)

    print("\n" + "=" * 50)
    print("  Querying REST API")
    print("=" * 50)

    query("GET",  "/orders",                 "all orders")
    query("GET",  "/orders/ORD-001",         "single order")
    query("POST", "/orders/ORD-001/fulfill", "fulfill paid order")
    query("GET",  "/products/SKU001",        "check SKU001 stock after sales")


def demo_duplicate_order():
    """Idempotency test — same order sent twice, only processed once."""
    print("\n" + "=" * 50)
    print("  DEMO 2: Duplicate Order (Idempotency)")
    print("=" * 50)

    order = {
        "order_id": "ORD-003",
        "customer": {"name": "Carol Wu", "email": "carol@example.com"},
        "items": [{"sku": "SKU002", "name": "Phone Case", "quantity": 1, "price": 9.99}],
        "total": 9.99,
        "created_at": int(time.time()),
    }

    print("Sending ORD-003 first time:")
    send_event("order.created", order)
    time.sleep(1)

    print("Sending ORD-003 again (simulates TikTok Shop retry):")
    send_event("order.created", order)


def demo_oversell():
    """Oversell protection — order requesting more stock than available is blocked."""
    print("\n" + "=" * 50)
    print("  DEMO 3: Oversell Protection")
    print("=" * 50)

    print("Requesting 999 units of SKU001 (only 100 in stock):")
    send_event("order.created", {
        "order_id": "ORD-004",
        "customer": {"name": "Dan Lee", "email": "dan@example.com"},
        "items": [{"sku": "SKU001", "name": "Wireless Earbuds", "quantity": 999, "price": 29.99}],
        "total": 29990.01,
        "created_at": int(time.time()),
    })


if __name__ == "__main__":
    demo_normal_flow()
    demo_duplicate_order()
    demo_oversell()
