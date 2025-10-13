"""Retry logic with exponential backoff."""

import functools
import time
from typing import Callable, Optional, Tuple, Type


def retry_with_backoff(
    retries: int = 3,
    delays: Optional[Tuple[float, ...]] = None,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Decorator for retrying a function with exponential backoff.

    Args:
        retries: Number of retries (default: 3)
        delays: Tuple of delays in seconds for each retry (default: (1, 2, 4))
        exceptions: Tuple of exception types to catch and retry (default: all exceptions)

    Example:
        @retry_with_backoff(retries=3)
        def fetch_data():
            # This will retry 3 times with delays of 1s, 2s, 4s
            return api_call()

        @retry_with_backoff(retries=2, delays=(0.5, 1.5))
        def query_database():
            # This will retry 2 times with custom delays
            return db.query()

        @retry_with_backoff(retries=3, exceptions=(ConnectionError, TimeoutError))
        def network_request():
            # This will only retry on specific exceptions
            return requests.get(url)
    """
    if delays is None:
        # Default exponential backoff: 1s, 2s, 4s
        delays = tuple(2**i for i in range(retries))
    elif len(delays) < retries:
        # Pad delays with the last value if not enough provided
        delays = delays + (delays[-1],) * (retries - len(delays))

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(retries + 1):  # +1 for initial attempt
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < retries:  # Don't sleep after last attempt
                        delay = delays[attempt]
                        time.sleep(delay)
                    # If last attempt, raise the exception
                    if attempt == retries:
                        raise

            # This should never be reached, but for type safety
            if last_exception:
                raise last_exception

        return wrapper

    return decorator
