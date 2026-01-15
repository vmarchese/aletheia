"""
Patch for Python's deepcopy to handle bound methods gracefully.

This module provides a monkey-patch for copy.deepcopy to prevent errors
when trying to deepcopy bound methods that contain unpicklable objects.
"""
import copy
import types
from aletheia.utils.logging import log_debug


_original_deepcopy = copy.deepcopy
_original_dispatch = None
_patched = False


def _copy_method(x, memo):
    """
    Custom copy function for bound methods.
    
    Instead of trying to deepcopy the method (which fails with unpicklable objects),
    we just return the same method instance.
    """
    log_debug(f"deepcopy: Returning same bound method {x.__name__} without copying")
    return x


def patch_deepcopy():
    """
    Monkey-patch copy.deepcopy to handle bound methods gracefully.
    
    This prevents "cannot pickle 'builtins.Bindings' object" errors
    when the agent framework tries to deepcopy agent options that
    contain bound methods in the tools list.
    """
    global _patched, _original_dispatch
    
    if _patched:
        log_debug("deepcopy already patched, skipping")
        return
    
    log_debug("Patching copy._deepcopy_dispatch for MethodType to handle bound methods")
    
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
    
    log_debug("Restoring original copy._deepcopy_dispatch for MethodType")
    
    if _original_dispatch is not None:
        copy._deepcopy_dispatch[types.MethodType] = _original_dispatch
    else:
        # Remove our custom handler
        copy._deepcopy_dispatch.pop(types.MethodType, None)
    
    _patched = False
