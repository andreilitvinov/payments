import pytest


def test_create_order_and_cash_payment(client):
    r = client.post("/api/orders", json={"total_amount": "100.00"})
    assert r.status_code == 201
    data = r.json()
    order_id = data["id"]
    assert float(data["total_amount"]) == 100.0
    assert data["payment_status"] == "unpaid"

    r2 = client.post(
        f"/api/orders/{order_id}/payments",
        json={"payment_type": "cash", "amount": "50.00"},
    )
    assert r2.status_code == 201
    assert float(r2.json()["deposited_amount"]) == 50.0
    assert r2.json()["status"] == "completed"

    r3 = client.get(f"/api/orders/{order_id}")
    assert r3.status_code == 200
    assert r3.json()["payment_status"] == "partially_paid"

    r4 = client.post(
        f"/api/orders/{order_id}/payments",
        json={"payment_type": "cash", "amount": "50.00"},
    )
    assert r4.status_code == 201
    r5 = client.get(f"/api/orders/{order_id}")
    assert r5.json()["payment_status"] == "paid"


def test_create_order_validation(client):
    r = client.post("/api/orders", json={"total_amount": "-1"})
    assert r.status_code == 422


def test_refund(client):
    order = client.post("/api/orders", json={"total_amount": "80.00"}).json()
    r = client.post(f"/api/orders/{order['id']}/payments", json={"payment_type": "cash", "amount": "80.00"})
    assert r.status_code == 201
    payment_id = r.json()["id"]

    r = client.post(f"/api/payments/{payment_id}/refund", json={"amount": "20.00"})
    assert r.status_code == 204

    r = client.get(f"/api/payments/{payment_id}")
    assert float(r.json()["refunded_amount"]) == 20.0

    r = client.get(f"/api/orders/{order['id']}")
    assert r.json()["payment_status"] == "partially_paid"


def test_overpay_rejected(client):
    order = client.post("/api/orders", json={"total_amount": "10.00"}).json()
    client.post(f"/api/orders/{order['id']}/payments", json={"payment_type": "cash", "amount": "10.00"})
    r = client.post(f"/api/orders/{order['id']}/payments", json={"payment_type": "cash", "amount": "0.01"})
    assert r.status_code == 400


def test_404_order(client):
    r = client.get("/api/orders/999999")
    assert r.status_code == 404


def test_404_payment(client):
    r = client.get("/api/payments/99999")
    assert r.status_code == 404
