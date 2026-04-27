from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.models import OptimizeRequest, OptimizeResponse
from app.optimizer import optimize
from app.exceptions import (
    ValidationError,
    PayloadTooLargeError,
    NoFeasibleCombinationError,
)

router = APIRouter(prefix="/api/v1/load-optimizer")


@router.post("/optimize", response_model=OptimizeResponse, status_code=200)
async def optimize_load(request: OptimizeRequest):
    """
    Given a truck and a list of candidate orders, returns the optimal
    subset that maximizes total payout while respecting:
      - Weight and volume capacity
      - Hazmat isolation (hazmat-only or non-hazmat-only per load)
      - Route compatibility (same headhaul lane)
      - Date validity (pickup_date <= delivery_date per order)
    """
    try:
        selected_orders, total_payout, total_weight, total_volume = optimize(
            truck=request.truck,
            orders=request.orders,
        )
    except PayloadTooLargeError as e:
        raise PayloadTooLargeError(str(e))
    except NoFeasibleCombinationError as e:
        raise NoFeasibleCombinationError(str(e))

    truck = request.truck
    weight_pct = round((total_weight / truck.max_weight_lbs) * 100, 2)
    volume_pct = round((total_volume / truck.max_volume_cuft) * 100, 2)

    return OptimizeResponse(
        truck_id=truck.id,
        selected_order_ids=[o.id for o in selected_orders],
        total_payout_cents=total_payout,
        total_weight_lbs=total_weight,
        total_volume_cuft=total_volume,
        utilization_weight_percent=weight_pct,
        utilization_volume_percent=volume_pct,
    )
