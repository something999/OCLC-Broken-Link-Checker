"""
Utility functions for generating timestamps.

This module contains functions for creating and formatting timestamps.
"""
import datetime

def get_file_timestamp() -> str:
    """Generate a file-safe timestamp string.

    The timestamp is formatted as 'YYYY.MM.DD.HH.MM.SS', representing
    the current year (YYYY), month (MM), day (DD), hour (HH), minute (MM),
    and second (SS) in UTC time.

    The '.' character is used to comply with file-naming standards for
    operating systems, which typically disallow the usage of characters like
    '/'.

    Examples:
        - get_file_timestamp() -> '1970.01.01.00.00.00' (1/1/1970 00:00:00 UTC)
    
    Returns:
        str: A string representing the current date and time in a file-safe format.
    """
    today = get_current_time()
    return today.strftime(_get_date_format('.') + '.' + _get_time_format('.'))

def get_datetime_format() -> str:
    """Generate a timestamp representing the current date and time in UTC.

    The timestamp is formatted as 'YYYY-MM-DD HH:MM:SS', representing
    the current year (YYYY), month (MM), day (DD), hour (HH), minute (MM),
    and second (SS) in UTC time.

    Examples:
        - get_datetime_format() -> '1970-01-01 00:00:00' (1/1/1970 00:00:00 UTC)

    Returns:
        str: A string representing the current date and time.
    """
    return _get_date_format('-') + ' ' + _get_time_format(':')

def _get_date_format(sep: str = '-') -> str:
    """Return a format string for displaying dates.
    
    The format string follows the pattern 'YYYY{sep}MM{sep}DD', representing
    a year (YYYY), month (MM), and date (DD) separated by a character (sep).

    This function is intended to be used in conjunction with
    datetime.strftime() along with datetime.utcnow() or datetime.now().

    By default, the date components will be separated by the '-' character,
    but any string can be used. The function does not check whether the 
    separator is safe for the chosen context (i.e. if a separator value of '/'
    can be used for constructing file names).

    Examples:
        - _get_date_format() -> '%Y-%m%d' ('1970-01-01')
        - _get_date_format('/') -> '%Y/%m%d' ('1970/01/01')
        - _get_date_format('x') -> '%Yx%m%d' ('1970x01x01')

    Args:
        sep (str): The string used to separate the year, month, and day.
        
    Returns:
        str: A format string for use with datetime.strftime()
    """
    return f'%Y{sep}%m{sep}%d'

def _get_time_format(sep: str = ':') -> str:
    """Return a format string for displaying times.
    
    The format string follows the pattern HH{sep}MM{sep}SS, representing
    the hours (HH), minutes (MM), and seconds (SS) separated by a character (sep).
    
    This function is intended to be used in conjunction with
    datetime.strftime() and datetime.now().
    
    By default, the time components will be separated by the ':' character,
    but any string can be used. The function does not check whether the 
    separator is safe for the chosen context (i.e. if a separator value of ':'
    can be used for constructing file names).

    Examples:
        - _get_time_format() -> '%H:%M:%S' ('00:00:00')
        - _get_time_format('/') -> '%H/%M/%S' ('00/00/00')
        - _get_time_format('x') -> '%Hx%Mx%S' ('00x00x00')

    Args:
        sep (str): The string used to separate the hours, minutes, and seconds.

    Returns:
        str: A format string for use with datetime.strftime()
    """
    return f'%H{sep}%M{sep}%S'

def get_current_time() -> datetime.datetime:
    """Return the current date and time in Coordinated Universal Time (UTC).
    
    Returns:
        datetime.datetime: A datetime object representing the current
            UTC date and time.
    """
    return datetime.datetime.now(datetime.timezone.utc)

def get_delta(time1: datetime.datetime, time2: datetime.datetime) -> float:
    """Calculate the absolute difference between two datetimes objects in seconds. 

    Args:
        time1 (datetime.datetime): A datetime object.
        time2 (datetime.datetime): Another datetime object.

    Returns:
        float: The absolute difference between the two times in seconds.
    """
    return abs((time2 - time1).total_seconds())