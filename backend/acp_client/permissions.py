import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_pending_permissions: dict[str, asyncio.Future[dict[str, Any]]] = {}


async def handle_permission_request(
    run_id: str,
    prompt_id: str,
    mode: str = "auto",
) -> dict[str, str]:
    if mode == "auto":
        return {"outcome": "allowed_once"}

    future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
    key = f"{run_id}:{prompt_id}"
    _pending_permissions[key] = future

    try:
        result = await asyncio.wait_for(future, timeout=300)
        return result
    except asyncio.TimeoutError:
        return {"outcome": "cancelled"}
    finally:
        _pending_permissions.pop(key, None)


def resolve_permission(run_id: str, prompt_id: str, decision: dict[str, Any]) -> bool:
    key = f"{run_id}:{prompt_id}"
    future = _pending_permissions.get(key)
    if future and not future.done():
        future.set_result(decision)
        return True
    return False
