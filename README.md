# SmartLoad Optimization API

A stateless REST microservice that finds the **optimal combination of freight orders** for a given truck, maximizing carrier payout while respecting weight, volume, hazmat, and route constraints.

## Algorithm

Uses **Bitmask Dynamic Programming** — the classic solution for subset selection with `n ≤ 22`:

- State space: `2ⁿ` bitmasks (each bit = whether order `i` is selected)
- For `n = 22`: ~4 million states, evaluated in well under 800 ms
- Pre-filters orders that individually violate limits, shrinking `n` further
- Enforces hazmat isolation: a load is either **all-hazmat** or **all-non-hazmat**
- Route compatibility: selects the dominant headhaul lane if mixed lanes are provided
- Money handled exclusively as **64-bit integer cents** — no floats anywhere

## How to Run

```bash
git clone <your-repo-url>
cd smartload
docker compose up --build
# → Service available at http://localhost:8080
```

## Health Check

```bash
curl http://localhost:8080/healthz
# → {"status":"ok"}
```

## Example Request

```bash
curl -X POST http://localhost:8080/api/v1/load-optimizer/optimize \
  -H "Content-Type: application/json" \
  -d @sample-request.json
```

### Expected Response

```json
{
  "truck_id": "truck-123",
  "selected_order_ids": ["ord-001", "ord-002"],
  "total_payout_cents": 430000,
  "total_weight_lbs": 30000,
  "total_volume_cuft": 2100,
  "utilization_weight_percent": 68.18,
  "utilization_volume_percent": 70.0
}
```

## API Reference

### `POST /api/v1/load-optimizer/optimize`

| Field | Type | Description |
|---|---|---|
| `truck.id` | string | Truck identifier |
| `truck.max_weight_lbs` | integer | Max payload weight |
| `truck.max_volume_cuft` | integer | Max payload volume |
| `orders[].id` | string | Unique order ID |
| `orders[].payout_cents` | integer | Revenue in cents (never float) |
| `orders[].weight_lbs` | integer | Order weight |
| `orders[].volume_cuft` | integer | Order volume |
| `orders[].origin` | string | Origin city |
| `orders[].destination` | string | Destination city |
| `orders[].pickup_date` | date | ISO 8601 date |
| `orders[].delivery_date` | date | ISO 8601 date (≥ pickup) |
| `orders[].is_hazmat` | boolean | Hazmat flag |

### HTTP Status Codes

| Code | Meaning |
|---|---|
| `200` | Success (or no feasible combination found) |
| `400` | Invalid input (business rule violation) |
| `413` | Too many orders (> 22) |
| `422` | Schema validation error |

## Constraints Enforced

1. **Weight & Volume** — never exceed truck limits
2. **Hazmat isolation** — mixed hazmat/non-hazmat loads are rejected
3. **Route compatibility** — only same-lane orders combined
4. **Date validity** — `pickup_date ≤ delivery_date` per order
5. **Unique order IDs** — duplicates rejected at request level

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Project Structure

```
smartload/
├── app/
│   ├── main.py          # FastAPI app + exception handlers
│   ├── router.py        # POST /optimize endpoint
│   ├── optimizer.py     # Bitmask DP core algorithm
│   ├── models.py        # Pydantic request/response models
│   └── exceptions.py    # Custom exception classes
├── tests/
│   └── test_optimizer.py
├── Dockerfile           # Multi-stage, non-root user
├── docker-compose.yml
├── requirements.txt
├── sample-request.json
└── README.md
```

## Design Notes

- **Stateless** — no database, no disk writes; every request is self-contained
- **Multi-stage Docker build** — slim runtime image (~150 MB)
- **Non-root container** — runs as `appuser` for security
- **Uvicorn with 2 workers** — handles concurrent requests safely (optimizer is pure function)
- **Caching opportunity** — the bitmask DP result for a given set of order IDs + truck spec could be memoized with an LRU cache keyed on a hash of the sorted input, reducing repeated calls to O(1)
