from pydantic import BaseModel, Field, model_validator
from typing import List
from datetime import date


class Truck(BaseModel):
    id: str = Field(..., min_length=1)
    max_weight_lbs: int = Field(..., gt=0)
    max_volume_cuft: int = Field(..., gt=0)


class Order(BaseModel):
    id: str = Field(..., min_length=1)
    payout_cents: int = Field(..., ge=0, description="Payout in integer cents, never float")
    weight_lbs: int = Field(..., ge=0)
    volume_cuft: int = Field(..., ge=0)
    origin: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    pickup_date: date
    delivery_date: date
    is_hazmat: bool = False

    @model_validator(mode="after")
    def validate_dates(self) -> "Order":
        if self.pickup_date > self.delivery_date:
            raise ValueError(
                f"Order {self.id}: pickup_date must be <= delivery_date"
            )
        return self


class OptimizeRequest(BaseModel):
    truck: Truck
    orders: List[Order] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_order_ids_unique(self) -> "OptimizeRequest":
        ids = [o.id for o in self.orders]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate order IDs detected in the request")
        return self


class OptimizeResponse(BaseModel):
    truck_id: str
    selected_order_ids: List[str]
    total_payout_cents: int
    total_weight_lbs: int
    total_volume_cuft: int
    utilization_weight_percent: float
    utilization_volume_percent: float
