"""
Tests for the SmartLoad Optimization API.
Run with: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

BASE_URL = "/api/v1/load-optimizer/optimize"

TRUCK = {
    "id": "truck-123",
    "max_weight_lbs": 44000,
    "max_volume_cuft": 3000,
}

ORDERS_SAMPLE = [
    {
        "id": "ord-001",
        "payout_cents": 250000,
        "weight_lbs": 18000,
        "volume_cuft": 1200,
        "origin": "Los Angeles, CA",
        "destination": "Dallas, TX",
        "pickup_date": "2025-12-05",
        "delivery_date": "2025-12-09",
        "is_hazmat": False,
    },
    {
        "id": "ord-002",
        "payout_cents": 180000,
        "weight_lbs": 12000,
        "volume_cuft": 900,
        "origin": "Los Angeles, CA",
        "destination": "Dallas, TX",
        "pickup_date": "2025-12-04",
        "delivery_date": "2025-12-10",
        "is_hazmat": False,
    },
    {
        "id": "ord-003",
        "payout_cents": 320000,
        "weight_lbs": 30000,
        "volume_cuft": 1800,
        "origin": "Los Angeles, CA",
        "destination": "Dallas, TX",
        "pickup_date": "2025-12-06",
        "delivery_date": "2025-12-08",
        "is_hazmat": True,
    },
]


# ─── Health check ───────────────────────────────────────────────────────────

def test_health_check():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ─── Happy path ─────────────────────────────────────────────────────────────

def test_basic_optimization_returns_correct_orders():
    """
    ord-001 ($2500) + ord-002 ($1800) = $4300, 30,000 lbs, 2,100 cuft — fits.
    ord-003 alone = $3200 — less payout; also hazmat-isolated.
    Expected winner: ord-001 + ord-002.
    """
    payload = {"truck": TRUCK, "orders": ORDERS_SAMPLE}
    resp = client.post(BASE_URL, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["selected_order_ids"]) == {"ord-001", "ord-002"}
    assert body["total_payout_cents"] == 430000
    assert body["total_weight_lbs"] == 30000
    assert body["total_volume_cuft"] == 2100
    assert body["truck_id"] == "truck-123"


def test_utilization_percentages():
    payload = {"truck": TRUCK, "orders": ORDERS_SAMPLE}
    resp = client.post(BASE_URL, json=payload)
    body = resp.json()
    # 30000/44000 * 100 = 68.18, 2100/3000 * 100 = 70.0
    assert abs(body["utilization_weight_percent"] - 68.18) < 0.01
    assert abs(body["utilization_volume_percent"] - 70.0) < 0.01


# ─── Edge cases ─────────────────────────────────────────────────────────────

def test_empty_orders_returns_error():
    payload = {"truck": TRUCK, "orders": []}
    resp = client.post(BASE_URL, json=payload)
    assert resp.status_code == 200  # handled gracefully
    body = resp.json()
    assert body["selected_order_ids"] == []


def test_single_order_fits():
    order = {
        "id": "ord-solo",
        "payout_cents": 100000,
        "weight_lbs": 5000,
        "volume_cuft": 500,
        "origin": "Chicago, IL",
        "destination": "Houston, TX",
        "pickup_date": "2025-12-01",
        "delivery_date": "2025-12-05",
        "is_hazmat": False,
    }
    payload = {"truck": TRUCK, "orders": [order]}
    resp = client.post(BASE_URL, json=payload)
    assert resp.status_code == 200
    assert resp.json()["selected_order_ids"] == ["ord-solo"]


def test_no_order_fits_truck():
    """All orders exceed weight limit individually."""
    orders = [
        {
            "id": f"ord-{i}",
            "payout_cents": 100000,
            "weight_lbs": 50000,  # exceeds 44,000
            "volume_cuft": 100,
            "origin": "A",
            "destination": "B",
            "pickup_date": "2025-12-01",
            "delivery_date": "2025-12-05",
            "is_hazmat": False,
        }
        for i in range(3)
    ]
    payload = {"truck": TRUCK, "orders": orders}
    resp = client.post(BASE_URL, json=payload)
    assert resp.status_code == 200
    assert resp.json()["selected_order_ids"] == []


def test_hazmat_isolation_enforced():
    """
    Mix of hazmat and non-hazmat — they must not be combined.
    The single hazmat order ($3200) beats any single non-hazmat order
    but the optimizer must never combine them.
    """
    orders = [
        {
            "id": "hz-001",
            "payout_cents": 320000,
            "weight_lbs": 20000,
            "volume_cuft": 1000,
            "origin": "Los Angeles, CA",
            "destination": "Dallas, TX",
            "pickup_date": "2025-12-01",
            "delivery_date": "2025-12-05",
            "is_hazmat": True,
        },
        {
            "id": "nh-001",
            "payout_cents": 200000,
            "weight_lbs": 10000,
            "volume_cuft": 800,
            "origin": "Los Angeles, CA",
            "destination": "Dallas, TX",
            "pickup_date": "2025-12-01",
            "delivery_date": "2025-12-05",
            "is_hazmat": False,
        },
    ]
    payload = {"truck": TRUCK, "orders": orders}
    resp = client.post(BASE_URL, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    ids = set(body["selected_order_ids"])
    assert "hz-001" not in ids or "nh-001" not in ids  # never mixed


def test_duplicate_order_ids_rejected():
    orders = [
        {
            "id": "dup-001",
            "payout_cents": 100000,
            "weight_lbs": 5000,
            "volume_cuft": 500,
            "origin": "A",
            "destination": "B",
            "pickup_date": "2025-12-01",
            "delivery_date": "2025-12-05",
            "is_hazmat": False,
        },
        {
            "id": "dup-001",  # duplicate
            "payout_cents": 200000,
            "weight_lbs": 5000,
            "volume_cuft": 500,
            "origin": "A",
            "destination": "B",
            "pickup_date": "2025-12-01",
            "delivery_date": "2025-12-05",
            "is_hazmat": False,
        },
    ]
    payload = {"truck": TRUCK, "orders": orders}
    resp = client.post(BASE_URL, json=payload)
    assert resp.status_code == 422  # pydantic validation error


def test_invalid_pickup_after_delivery_rejected():
    order = {
        "id": "bad-dates",
        "payout_cents": 100000,
        "weight_lbs": 1000,
        "volume_cuft": 100,
        "origin": "A",
        "destination": "B",
        "pickup_date": "2025-12-10",
        "delivery_date": "2025-12-05",  # before pickup
        "is_hazmat": False,
    }
    payload = {"truck": TRUCK, "orders": [order]}
    resp = client.post(BASE_URL, json=payload)
    assert resp.status_code == 422


def test_too_many_orders_returns_413():
    orders = [
        {
            "id": f"ord-{i:03d}",
            "payout_cents": 100000,
            "weight_lbs": 100,
            "volume_cuft": 10,
            "origin": "A",
            "destination": "B",
            "pickup_date": "2025-12-01",
            "delivery_date": "2025-12-05",
            "is_hazmat": False,
        }
        for i in range(23)  # 23 > 22
    ]
    payload = {"truck": TRUCK, "orders": orders}
    resp = client.post(BASE_URL, json=payload)
    assert resp.status_code == 413


def test_money_is_integer_cents():
    """Ensure payout is never a float in the response."""
    payload = {"truck": TRUCK, "orders": ORDERS_SAMPLE}
    resp = client.post(BASE_URL, json=payload)
    body = resp.json()
    assert isinstance(body["total_payout_cents"], int)


def test_route_incompatible_orders_filtered():
    """
    Orders on different lanes — optimizer picks the lane with highest payout.
    """
    orders = [
        {
            "id": "lane-a-1",
            "payout_cents": 500000,
            "weight_lbs": 5000,
            "volume_cuft": 300,
            "origin": "Chicago, IL",
            "destination": "Miami, FL",
            "pickup_date": "2025-12-01",
            "delivery_date": "2025-12-05",
            "is_hazmat": False,
        },
        {
            "id": "lane-b-1",
            "payout_cents": 100000,
            "weight_lbs": 5000,
            "volume_cuft": 300,
            "origin": "Seattle, WA",
            "destination": "Denver, CO",
            "pickup_date": "2025-12-01",
            "delivery_date": "2025-12-05",
            "is_hazmat": False,
        },
    ]
    payload = {"truck": TRUCK, "orders": orders}
    resp = client.post(BASE_URL, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    # Only one lane's orders should be selected
    ids = set(body["selected_order_ids"])
    assert "lane-a-1" not in ids or "lane-b-1" not in ids
