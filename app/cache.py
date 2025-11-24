"""
Asynchronous file writer and reader for caching objects.

This module provides methods for recording and retrieving data in .csv files
(which are used to cache outputs returned throughout the link-checking process).
"""

import asyncio
import csv
from dataclasses import asdict, is_dataclass
import io
import logging
import random
from typing import Any, AsyncIterator, Type

import aiofiles # Requires Python 3.9+

from utils import file_utils

_logger = logging.getLogger(__name__)

class Cache:

    def __init__(self, path: str, allow_delete: bool = True) -> None:
        """Asynchronous .csv file I/O manager built on top of aiofiles.
        
        A Cache stores information about dataclass objects into a .csv file for
        future reference. Each object is represented by a single row of strings,
        with each column representing an attribute of the object.
        
        As an example, if the object is of type HTTPResponse and has the 
        attributes `url`, `code` and `content`, then the rows would look like this:
        
        url,code,content
        https://example.com,200,OK
        
        The Cache is able to store any type of dataclass object in a .csv file
        but doesn't know its own file contents. This can lead to issues such
        as duplicate header rows.
        
        Attributes:
            path (str): An absolute or relative file path pointing to the 
                cache's file ocation.
                
        Private Attributes:
            _has_header (bool): If True, forces the cache to add a header row
                to the .csv file (regardless of whether this row exists).
            
            _allow_delete (bool): If True, forces the program to delete the
                existing cache and create a new cache upon startup.
                
            _lock (asyncio.Lock): A lock used to synchronize file writes.
        """
        self.path = path
        self._has_header = False
        self._allow_delete = allow_delete
        self._lock = asyncio.Lock()

    @classmethod
    def create(cls: Type['Cache'], path: str, allow_delete: bool = True) -> 'Cache':
        """Factory method for initializing the cache."""
        cache = cls(path, allow_delete)
        asyncio.run(cache._make_cache())
        return cache

    async def _make_cache(self) -> None:
        """Asynchronously create an empty cache file if one doesn't exist."""
        if self._allow_delete and file_utils.is_file(self.path):
            file_utils.remove_file(self.path)
            _logger.info('Refreshed cache file at "%s".', self.path)
            return
        elif not self._allow_delete and file_utils.is_file(self.path):
            _logger.info('Found existing cache file at "%s".', self.path)
            return

        try:
            if not file_utils.is_file(self.path):
                result = file_utils.add_file(self.path)
            if result:
                _logger.info('Created cache file at "%s".', self.path)
            else:
                raise FileNotFoundError
        except FileNotFoundError:
            _logger.error('Failed to create cache at "%s" - '
                          'Unable to add file at this path.', self.path)
        except PermissionError:
            _logger.error('Failed to create cache at "%s" - '
                          'User does not have permission to save files.'
                          'Please check file and folder permissions.', self.path)
        except (OSError, Exception):
            _logger.exception('Failed to create cache at "%s"')
            
    async def cache_object(self, row_object: Any) -> None:
        """Asynchronously record a dataclass-like object into a .csv file."""

        def _write_header(writer: csv.DictWriter) -> str:
            """Helper function that adds a header row to the cache's .csv file."""
            if not self._has_header and file_utils.get_file_size(self.path) == 0:
                writer.writeheader()
            self._has_header = True

        def _get_row(row_object: dict) -> str:
            """Render the dataclass-like object as a .csv-styled row."""
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames = row_object.keys())
            _write_header(writer)
            writer.writerow(row_object)
            return buffer.getvalue()

        try:
            async with self._lock:
                row = None
                if is_dataclass(row_object):
                    row = _get_row(asdict(row_object))
                else:
                    # Assume the object being cached is a dictionary representation
                    # of the dataclass object
                    row = _get_row(row_object)

                async with aiofiles.open(self.path, mode = 'a', encoding = 'utf-8', errors = 'replace', newline = '') as cache_file:
                    await cache_file.write(row)
                    await cache_file.flush()

        except FileNotFoundError:
            _logger.error('Failed to cache object at "%s" - '
                          'No cache file found.', self.path)
        except PermissionError:
            _logger.error('Failed to cache object at "%s" - '
                          'User does not have permission to modify this cache.'
                          'Please check file and folder permissions.', self.path)
        except (OSError, Exception):
            _logger.exception('Failed to cache object at "%s"')

    async def get_cached_objects(self, randomize: bool = False) -> AsyncIterator[dict]:
        """Asynchronously fetch the contents of a cache in a specified order."""
        try:
            async with self._lock:
                async with aiofiles.open(self.path, mode = 'r', encoding = 'utf-8', errors = 'replace', newline = '') as cache_file:
                    content = await cache_file.read()
                    text = content.splitlines()
                    # During the link-checking process, we might want to 
                    # randomize the order of the links to decrease the chance
                    # of us hitting the same domain multiple times in a row.

                    # If we move this to LinkCheckerCore, the program will
                    # end up being written in a way that causes the calls
                    # to be queued before execution (which makes it difficult
                    # for the user to discern whether the program is running
                    # or is frozen).

                    # Additionally, shuffling the order in LinkCheckerCore
                    # would require us to consume the generator in a list
                    # comprehension, which would diminish the streaming benefit
                    # of the AsyncGenerator.

                    # So instead, the randomization process is moved to the
                    # Cache class.
                    if randomize:
                        random.shuffle(text[1:])
                    reader = csv.DictReader(text)
                    for row in reader:
                        yield row
        except FileNotFoundError:
            _logger.error('Failed to read cache at "%s" - '
                          'No cache file found.', self.path)
        except PermissionError:
            _logger.error('Failed to read cache at "%s" - '
                          'User does not have permission to read from this cache.'
                          'Please check file and folder permissions.', self.path)
        except (OSError, Exception) as e:
            _logger.error('Failed to read cache at "%s" - %s',
                          self.path, e)
            
    async def get_total_objects(self) -> int:
        """Return the number of cached objects."""
        try:
            count = 0
            async with aiofiles.open(self.path, mode = 'r', encoding = 'utf-8', errors = 'replace', newline = '') as cache_file:
                async for _ in cache_file:
                    count += 1
        except FileNotFoundError:
            _logger.error('Failed to calculate cache size for cache at "%s" - '
                          'No cache file found.', self.path)
        except Exception as e:
            _logger.error('Failed to calculate cache size for cache at "%s" - %s',
                          self.path, e)
        finally:
            return count - 1 if count > 0 else 0