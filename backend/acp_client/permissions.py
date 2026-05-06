"""
Permission handling for ACP agent actions during pipeline execution.

When an AI agent needs to perform a potentially dangerous action (e.g., writing
files, executing commands), the ACP protocol can pause and request user approval.
This module manages that approval flow.

There are two permission modes:
  - "auto": automatically approves all actions (used for non-interactive runs)
  - any other mode: pauses execution and waits for a human to approve or deny
    the action via the REST API (POST /api/v1/runs/<run_id>/permissions/<prompt_id>)

The pending permissions are stored as asyncio Futures in an in-memory dict.
When the REST endpoint is called, resolve_permission() looks up the Future and
sets its result, unblocking the waiting pipeline stage. If no human responds
within 5 minutes, the permission request times out and is automatically cancelled.

This is designed for single-process deployments. For multi-process setups,
the pending permissions dict would need to be replaced with a shared store
(e.g., Redis).
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# In-memory store of pending permission requests, keyed by "{run_id}:{prompt_id}".
# Each value is an asyncio Future that will be resolved when the user responds
# via the REST API.
_pending_permissions: dict[str, asyncio.Future[dict[str, Any]]] = {}


async def handle_permission_request(
    run_id: str,
    prompt_id: str,
    mode: str = "auto",
) -> dict[str, str]:
    """
    Handle a permission request from an ACP agent.

    In "auto" mode, immediately returns approval. In interactive mode, creates
    an asyncio Future and waits up to 5 minutes for a human to resolve it via
    the resolve_permission() function.

    Args:
        run_id: The pipeline run that triggered the permission request.
        prompt_id: Unique identifier for this specific permission prompt.
        mode: Permission mode -- "auto" for automatic approval, anything else
            for interactive human-in-the-loop approval.

    Returns:
        A dict with an "outcome" key: "allowed_once" (approved), or "cancelled" (timeout).
    """
    if mode == "auto":
        return {"outcome": "allowed_once"}

    # Create a Future that will be resolved when the REST endpoint is called
    future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
    key = f"{run_id}:{prompt_id}"
    _pending_permissions[key] = future

    try:
        # Wait for the human decision with a 5-minute timeout
        result = await asyncio.wait_for(future, timeout=300)
        return result
    except asyncio.TimeoutError:
        # No human responded in time -- cancel the action
        return {"outcome": "cancelled"}
    finally:
        # Clean up the pending permission regardless of outcome
        _pending_permissions.pop(key, None)


def resolve_permission(run_id: str, prompt_id: str, decision: dict[str, Any]) -> bool:
    """
    Resolve a pending permission request with the user's decision.

    Called by the REST API when a human approves or denies an agent action.

    Args:
        run_id: The pipeline run that owns the permission request.
        prompt_id: The specific permission prompt to resolve.
        decision: The user's decision dict (e.g., {"outcome": "allowed_once"}).

    Returns:
        True if the permission was successfully resolved, False if no matching
        pending permission was found (already timed out or never existed).
    """
    key = f"{run_id}:{prompt_id}"
    future = _pending_permissions.get(key)
    if future and not future.done():
        future.set_result(decision)
        return True
    return False
