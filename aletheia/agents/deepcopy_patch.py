"""
Patch for Python's deepcopy to handle bound methods gracefully.

This module provides a monkey-patch for copy.deepcopy to prevent errors
when trying to deepcopy bound methods that contain unpicklable objects.
"""

import copy
import types

import structlog

logger = structlog.get_logger(__name__)


_original_deepcopy = copy.deepcopy
_original_dispatch = None
_patched = False


def _copy_method(x, memo):
    """
    Custom copy function for bound methods.

    Instead of trying to deepcopy the method (which fails with unpicklable objects),
    we just return the same method instance.
    """
    logger.debug(f"deepcopy: Returning same bound method {x.__name__} without copying")
    return x


def _copy_with_logging(x, memo, deepcopy_func):
    """Wrapper to log what's being deepcopied."""
    # Check if this is a dict that might contain response_format
    if isinstance(x, dict) and "response_format" in x:
        logger.debug(
            f"deepcopy: Copying dict with response_format: {x.get('response_format')}"
        )

    result = deepcopy_func(x, memo)

    # Check if response_format was lost
    if isinstance(x, dict) and "response_format" in x:
        if isinstance(result, dict) and "response_format" not in result:
            logger.debug("⚠️  deepcopy: response_format was LOST during deepcopy!")
        elif isinstance(result, dict):
            logger.debug(
                f"deepcopy: response_format preserved: {result.get('response_format')}"
            )

    return result


def patch_deepcopy():
    """
    Monkey-patch copy.deepcopy to handle bound methods gracefully.

    This prevents "cannot pickle 'builtins.Bindings' object" errors
    when the agent framework tries to deepcopy agent options that
    contain bound methods in the tools list.
    """
    global _patched, _original_dispatch

    if _patched:
        logger.debug("deepcopy already patched, skipping")
        return

    logger.debug(
        "Patching copy._deepcopy_dispatch for MethodType to handle bound methods"
    )

    # Save the original dispatch function for MethodType (if any)
    _original_dispatch = copy._deepcopy_dispatch.get(types.MethodType)

    # Replace with our custom function that just returns the same method
    copy._deepcopy_dispatch[types.MethodType] = _copy_method

    _patched = True


def unpatch_deepcopy():
    """Restore the original deepcopy dispatch."""
    global _patched, _original_dispatch

    if not _patched:
        return

    logger.debug("Restoring original copy._deepcopy_dispatch for MethodType")

    if _original_dispatch is not None:
        copy._deepcopy_dispatch[types.MethodType] = _original_dispatch
    else:
        # Remove our custom handler
        copy._deepcopy_dispatch.pop(types.MethodType, None)

    _patched = False
