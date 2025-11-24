"""
Utility functions for finding and naming files.

This module contains functions for retrieving, copying, and validating
file paths.
"""
from pathlib import Path
import logging
import os

_logger = logging.getLogger(__name__)

def _get_compatible_path(path: str) -> str:
    """Convert Windows-style backslashes in a file path to forward slashes.

    This ensures paths are compatible across platforms that expect
    forward slashes (i.e. Linux systems).
    
    Example:
        - _get_compatible_path('C:\\Users\\') -> 'C:/Users/'
    """
    return path.replace('\\', '/')

def is_directory(path: str) -> bool:
    """Check whether the given path points to a directory in the file system.

    Args:
        path (str): The path to check.
        
    Returns:
        bool: True if the path if a directory. False if not.
    """
    compat_path = _get_compatible_path(path)
    return os.path.isdir(compat_path.replace('\\', '/'))

def is_file(path: str) -> bool:
    """Check whether the given path points to an existing file.
    
    Args:
        path (str): The path to check.
        
    Returns:
        bool: True if the path is a file. False if not.
    """
    return os.path.isfile(path)

def add_file(path: str) -> bool:
    """Create an empty file at the specified path and confirm its creation.

    Args:
        path (str): An absolute or relative path to the target file location.
        
    Returns:
        bool: True if the file was successfully created. False if not.
    """
    compat_path = _get_compatible_path(path)
    result_path = Path(compat_path).resolve()
    result_path.parent.mkdir(parents = True, exist_ok = True)
    try:
        with open(result_path, mode = 'w'):
            pass
    except FileExistsError:
        _logger.error(f'Failed to create file at "{compat_path}" - '
                      f'File with same name already exists.')
        return False
    except (OSError, Exception) as e:
        _logger.error(f'Failed to create file at "{compat_path}" - '
                      f'{e}.')
        return False
    return is_file(result_path)

def remove_file(path: str) -> bool:
    """Delete the file at the specified path.
    
    Args:
        path (str): An absolute or relative path to the target file location.
        
    Returns:
        bool: True if the file was successfully deleted. False if not.
    """
    compat_path = _get_compatible_path(path)
    if is_file(compat_path):
        os.remove(compat_path)
    return not is_file(compat_path)

def get_files(path: str) -> list[str]:
    """Return the files within a directory.
    
    Args:
        path(str): An absolute or relative path to the target directory.
        
    Returns:
        list[str]: A list of absolute paths pointing to files within that
            directory.
    """
    compat_path = _get_compatible_path(path)
    if not is_directory(compat_path):
        return []
    return sorted([str(f) for f in Path(compat_path).rglob('*.log')])

def get_file_size(path: str) -> int:
    """Return the size of the file in bytes.
    
    Args:
        path (str): An absolute or relative path to the target file location.
        
    Returns:
        bool: The file size in bytes. If the file doesn't exist, the default
            return value is 0.
    """
    compat_path = _get_compatible_path(path)
    return os.path.getsize(compat_path) if is_file(compat_path) else 0
