import time


def get_current_time_ms() -> int:
    """Returns current unix timestamp in milliseconds

    Returns
    -------
    int
    """
    return int(time.time() * 1000)


def get_current_time_ms_as_string() -> str:
    """Returns current unix timestamp in milliseconds as string.

    Returns
    -------
    str
    """
    return f"{get_current_time_ms()}"
