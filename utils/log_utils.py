"""
Utility functions for setting up log (.log) files.

This module contains functions for retrieving .log file paths and formatting
strings to insert into .log files.

Log files are not automatically deleted on program startup 
and should be removed manually if no longer needed.
"""
import logging
import logging.handlers
import queue

from utils import file_utils
from utils import time_utils

# Global logging queue and listener (singletons)
_log_queue = queue.Queue(-1)
_log_listener = None

def setup_log() -> None:
    """Initialize the global logging system.
    
    Returns:
        This function does not return a value.
    """
    global _log_listener
    if _log_listener:
        return _log_listener
    
    _log_listener = logging.handlers.QueueListener(_log_queue, 
                                                  _get_file_handler())
    _log_listener.start()

    queue_handler = logging.handlers.QueueHandler(_log_queue)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(queue_handler)

    return _log_listener

def shutdown_log() -> None:
    """Deconstruct the global logging system.
    
    Returns:
        None: This function does not return a value.
    """
    global _log_listener
    if _log_listener:
        _log_listener.stop()

def _get_file_handler() -> logging.FileHandler:
    """Create and configure a file handler for logging messages.

    The log file handler enforces UTF-8 encoding in order to support the
    display and recording of non-foreign characters.

    Returns:
        logging.FileHandler: A handler that writes log messages to a file.
    """
    # TODO: Add more robust error-checking in the event that the log file
    # cannot be created.
    handler = logging.FileHandler(_get_log_path(),
                                  encoding = 'utf-8',
                                  errors = 'replace')
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(_get_log_format(),
                                           datefmt = time_utils.get_datetime_format()))
    return handler

def _remove_oldest_log() -> None:
    """Remove the oldest log file when more than two exist."""
    logs = file_utils.get_files('./logs')
    # file_utils.get_files should have sorted the log files by name.
    # The name is derived from the timestamp, so older files should appear
    # earlier in the list.
    while len(logs) > 2:
        file_utils.remove_file(logs[0])
        logs.pop(0)

def _get_log_path() -> str:
    """Construct a path for a log file.

    Each log file name includes a timestamp in the format YYYY.MM.DD.HH.MM.SS
    to distinguish it from other files. The timestamp is derived from the
    current system time and date.

    This function will not create the log file itself.

    Examples:
        - _get_log_path() -> './logs/1970.01.01.00.00.00.log'

    Returns:
        str: Upon success, an absolute or relative path to the log file.
            If file creation was not successful, return an empty string.
    """
    path = f'./logs/{time_utils.get_file_timestamp()}.log'
    _remove_oldest_log()
    result = file_utils.add_file(path)
    return path if result else ''

def _get_log_format() -> str:
    """Return a format string for logging messages.

    The format string follows the pattern of 'YYYY-MM-DD HH:MM:SS LEVEL MESSAGE',
    representing the current date (YYYY-MM-DD), time (HH:MM:SS),
    log level (LEVEL), and message (MESSAGE).
    
    Returns:
        str: A format string displaying the timestamp, log level, and message.    
    """
    return '%(asctime)s %(levelname)s %(message)s\n'