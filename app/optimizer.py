"""
Optimization engine for truck load planning.

Algorithm: Bitmask Dynamic Programming
- State space: 2^n bitmasks where each bit = whether order i is selected
- For n <= 22, this gives at most ~4M states, well within 2-second budget
- Each state tracks (total_weight, total_volume, total_payout)
- We iterate over all 2^n subsets and track the best feasible one

Complexity: O(2^n) time, O(2^n) space — acceptable for n <= 22.

Pruning: We pre-filter orders that individually violate constraints before DP,
which shrinks n and dramatically reduces the state space in practice.
"""

from typing import List, Tuple, Optional
from app.models import Order, Truck
from app.exceptions import PayloadTooLargeError, NoFeasibleCombinationError


MAX_ORDERS = 22


def _normalize_lane(origin: str, destination: str) -> Tuple[str, str]:
    """Normalize origin/destination to lowercase stripped strings for comparison."""
    return origin.strip().lower(), destination.strip().lower()


def _filter_compatible_orders(orders: List[Order]) -> List[Order]:
    """
    Filter orders to only those sharing the same headhaul lane.
    The dominant lane (most orders) is chosen if multiple lanes exist.
    """
    if not orders:
        return []

    # Group orders by lane
    lane_groups: dict[Tuple[str, str], List[Order]] = {}
    for order in orders:
        lane = _normalize_lane(order.origin, order.destination)
        lane_groups.setdefault(lane, []).append(order)

    # Pick the lane with the most orders (ties broken by highest total payout)
    def lane_score(lane_orders: List[Order]) -> Tuple[int, int]:
        return len(lane_orders), sum(o.payout_cents for o in lane_orders)

    best_lane = max(lane_groups.values(), key=lane_score)
    return best_lane


def _check_hazmat_isolation(orders: List[Order]) -> bool:
    """
    Returns True if hazmat isolation is violated:
    A combination containing hazmat orders cannot also contain non-hazmat orders.
    (A truck can carry ONLY hazmat or ONLY non-hazmat per load.)
    """
    has_hazmat = any(o.is_hazmat for o in orders)
    has_non_hazmat = any(not o.is_hazmat for o in orders)
    return has_hazmat and has_non_hazmat


def optimize(truck: Truck, orders: List[Order]) -> Tuple[List[Order], int, int, int]:
    """
    Find the optimal subset of orders using bitmask DP.

    Returns:
        (selected_orders, total_payout_cents, total_weight_lbs, total_volume_cuft)

    Raises:
        PayloadTooLargeError: if more than MAX_ORDERS orders are provided
        NoFeasibleCombinationError: if no valid combination exists
    """
    if len(orders) > MAX_ORDERS:
        raise PayloadTooLargeError(
            f"Too many orders: {len(orders)}. Maximum supported is {MAX_ORDERS}."
        )

    if not orders:
        raise NoFeasibleCombinationError("No orders provided.")

    # Step 1: Filter to compatible lane
    compatible = _filter_compatible_orders(orders)

    # Step 2: Pre-filter orders that individually exceed truck limits
    feasible = [
        o for o in compatible
        if o.weight_lbs <= truck.max_weight_lbs
        and o.volume_cuft <= truck.max_volume_cuft
    ]

    if not feasible:
        raise NoFeasibleCombinationError(
            "No individual order fits within the truck's weight and volume limits."
        )

    n = len(feasible)
    total_masks = 1 << n  # 2^n

    # Step 3: Bitmask DP over all subsets
    best_payout: int = 0
    best_mask: int = 0

    for mask in range(1, total_masks):
        weight = 0
        volume = 0
        payout = 0
        selected: List[Order] = []

        for i in range(n):
            if mask & (1 << i):
                o = feasible[i]
                weight += o.weight_lbs
                volume += o.volume_cuft
                payout += o.payout_cents
                selected.append(o)

                # Early exit if already over limits
                if weight > truck.max_weight_lbs or volume > truck.max_volume_cuft:
                    break
        else:
            # All bits processed without breaking → within weight/volume limits
            if _check_hazmat_isolation(selected):
                continue  # Mixed hazmat/non-hazmat — skip

            if payout > best_payout:
                best_payout = payout
                best_mask = mask

    if best_payout == 0 and best_mask == 0:
        raise NoFeasibleCombinationError(
            "No feasible combination of orders satisfies all constraints."
        )

    # Reconstruct selected orders from best_mask
    selected_orders = [
        feasible[i] for i in range(n) if best_mask & (1 << i)
    ]
    total_weight = sum(o.weight_lbs for o in selected_orders)
    total_volume = sum(o.volume_cuft for o in selected_orders)

    return selected_orders, best_payout, total_weight, total_volume
