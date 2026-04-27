from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.router import router
from app.exceptions import (
    ValidationError,
    PayloadTooLargeError,
    NoFeasibleCombinationError,
)

app = FastAPI(
    title="SmartLoad Optimization API",
    description="Optimal truck load planner for logistics platforms",
    version="1.0.0",
)

app.include_router(router)


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(PayloadTooLargeError)
async def payload_too_large_handler(request: Request, exc: PayloadTooLargeError):
    return JSONResponse(status_code=413, content={"error": str(exc)})


@app.exception_handler(NoFeasibleCombinationError)
async def no_feasible_handler(request: Request, exc: NoFeasibleCombinationError):
    return JSONResponse(status_code=200, content={"error": str(exc), "selected_order_ids": []})


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}
