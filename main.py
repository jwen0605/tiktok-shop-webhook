import hmac
import hashlib
import json
import time
from fastapi import FastAPI, Request, HTTPException, Header
from typing import Optional
import uvicorn

app = FastAPI(title="TikTok Shop Merchant Integration")

# Shared secret between TikTok Shop and your server — used to verify webhooks
WEBHOOK_SECRET = "my_secret_key_123"

# In-memory store (replace with a real DB in production)
orders = {}
products = {
    "SKU001": {"name": "Wireless Earbuds", "price": 29.99, "stock": 100},
    "SKU002": {"name": "Phone Case",        "price":  9.99, "stock":  50},
    "SKU003": {"name": "USB-C Cable",       "price": 12.99, "stock": 200},
}


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """HMAC-SHA256 signature check — ensures the webhook came from TikTok Shop."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Webhook endpoint — TikTok Shop POSTs events here
# ---------------------------------------------------------------------------

@app.post("/webhook")
async def receive_webhook(
    request: Request,
    x_tiktok_signature: Optional[str] = Header(None),
):
    payload = await request.body()

    if not x_tiktok_signature or not verify_signature(payload, x_tiktok_signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = json.loads(payload)
    event_type = event.get("type")
    data = event.get("data", {})

    print(f"\n[WEBHOOK] {event_type}")

    if event_type == "order.created":
        order_id = data["order_id"]

        # Idempotency check — ignore duplicate webhook deliveries
        if order_id in orders:
            print(f"  DUPLICATE ignored: {order_id} already exists")
            return {"status": "ok"}

        # Oversell check — verify stock before accepting the order
        for item in data["items"]:
            sku, qty = item["sku"], item["quantity"]
            if sku in products and products[sku]["stock"] < qty:
                print(f"  OVERSELL BLOCKED: {sku} has {products[sku]['stock']} units, requested {qty}")
                return {"status": "rejected", "reason": f"insufficient stock for {sku}"}

        orders[order_id] = {
            "order_id":   order_id,
            "status":     "pending",
            "items":      data["items"],
            "total":      data["total"],
            "customer":   data["customer"],
            "created_at": data["created_at"],
        }
        print(f"  New order {order_id} from {data['customer']['name']} — ${data['total']}")

    elif event_type == "order.paid":
        order_id = data["order_id"]
        if order_id in orders:
            # Idempotency check — don't deduct stock twice if payment event fires twice
            if orders[order_id]["status"] == "paid":
                print(f"  DUPLICATE ignored: {order_id} already paid")
                return {"status": "ok"}

            orders[order_id]["status"] = "paid"
            print(f"  Payment confirmed for {order_id}")
            for item in orders[order_id]["items"]:
                sku, qty = item["sku"], item["quantity"]
                if sku in products:
                    products[sku]["stock"] -= qty
                    print(f"  Inventory: {sku} stock → {products[sku]['stock']}")

    elif event_type == "order.cancelled":
        order_id = data["order_id"]
        if order_id in orders:
            orders[order_id]["status"] = "cancelled"
            print(f"  Order {order_id} cancelled")

    elif event_type == "inventory.low":
        sku = data["sku"]
        print(f"  LOW STOCK ALERT: {sku} has only {data['stock']} units left!")

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# REST API — merchants / internal tools query order and product state
# ---------------------------------------------------------------------------

@app.get("/orders")
def list_orders(status: Optional[str] = None):
    result = list(orders.values())
    if status:
        result = [o for o in result if o["status"] == status]
    return {"orders": result, "count": len(result)}


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    if order_id not in orders:
        raise HTTPException(status_code=404, detail="Order not found")
    return orders[order_id]


@app.post("/orders/{order_id}/fulfill")
def fulfill_order(order_id: str):
    if order_id not in orders:
        raise HTTPException(status_code=404, detail="Order not found")
    if orders[order_id]["status"] != "paid":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot fulfill order with status: {orders[order_id]['status']}",
        )
    orders[order_id]["status"] = "fulfilled"
    orders[order_id]["fulfilled_at"] = int(time.time())
    return {"message": f"Order {order_id} marked as fulfilled", "order": orders[order_id]}


@app.get("/products")
def list_products():
    return {"products": products}


@app.get("/products/{sku}")
def get_product(sku: str):
    if sku not in products:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"sku": sku, **products[sku]}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
