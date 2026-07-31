from fastapi import APIRouter

router = APIRouter()


@router.get(
    "",
    status_code=200,
    summary="Health check",
    description=(
        "Return the API health status. Used by monitoring systems and load balancers."
    ),
)
def health_check() -> dict[str, str]:
    return {"status": "ok"}
