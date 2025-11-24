"""
Main execution logic for the OCLC Link Checker application.

This module provides functions that handle the execution logic for link-checks.
These functions handle the retrieving, caching, validation, and analysis of
links.

The module is meant to be used with LinkCheckerController and 
LinkCheckerAppWindow.
"""
import asyncio
from collections import defaultdict
from typing import Callable

from app.cache import Cache
from clients.api_client import APIClient, CollectionMetadata
from clients.http_client import HTTPClient

class LinkCheckerCore:

    def __init__(self, 
                 api_client: APIClient,
                 http_client: HTTPClient,
                 resource_cache: Cache,
                 results_cache: Cache) -> None:
        """Core class for managing the link-checking workflow.
        
        The LinkCheckerCore class coordinates interactions between the 
        API and HTTP clients and Cache classes to retrieve and cache online
        resources from OCLC collections, check and cache the status codes
        returned when checking the availability of the resources, and analyze
        the results to see if any collections exceed a failure threshold.
        
        Private Attributes:
            _api_client (APIClient): A client for conducting API calls, which
                can then be used to retrieve collections and resources from
                OCLC.

            _http_client (HTTPClient): A client for sending HTTP requests.

            _resource_cache (Cache): A cache that stores resource-level metadata.

            _results_cache (Cache): A cache that stores link check results.

            _lock (asyncio.Lock): A lock used to synchronize counters.
        """
        self._api_client = api_client
        self._http_client = http_client
        self._resource_cache = resource_cache
        self._results_cache = results_cache
        self._lock = asyncio.Lock()

    def update_clients(self, wskey: str,
                       ignorelist: list[str],
                       check_domains_only: bool) -> None:
        """Update API and HTTP client configurations."""
        self._api_client.update_api_key(wskey)
        self._http_client.update_ignorelist(ignorelist)
        self._http_client.update_check_type(check_domains_only)

    async def find_resources(self,
                              on_cache_start_event: Callable, 
                              on_cache_event: Callable,
                              on_cache_end_event: Callable,
                              on_cache_failure: Callable) -> None:
        """Fetch and cache resources in OCLC collections.
        
        This function attempts to retrieve all of the collections enabled by
        an institution from the OCLC system. The function then iterates through
        the collection contents, caching any non-empty resources.

        To communicate progress, the function uses a counter to track the
        number of cached resources and displays messages through the callbacks
        provided in `on_cache_start_event`, `on_cache_event`, and
        `on_cache_end_event`.

        Args:
            on_cache_start_event (Callable): The function to call upon starting
                the resource gathering and caching process.

            on_cache_event (Callable): The function to call during the
                the resource gathering and caching process.

            on_cache_end_event (Callable): The function to call upon stopping
                the resource gathering and caching process.

        Returns:
            None: This function does not return a value.
        """
        async def _cache_resource(cache: Cache,
                                  collection: CollectionMetadata,
                                  client: APIClient) -> None:
            """Asynchronously fetch and cache resources in one collection."""
            count = 0
            async for resource in client.get_resources(collection):
                if resource.is_empty():
                    continue
                await cache.cache_object(resource)
                count += 1
            async with self._lock:
                nonlocal resource_total
                resource_total += count
            on_cache_event(f'Cached {count} online resources '
                           f'for collection {collection.title.strip()}.')
        
        resource_total = 0
        collection_total = 0
        tasks = []

        on_cache_start_event('Searching for resources. Please do not exit...')

        async with self._api_client as client:
            test_code = await client.get_connection_test_result()
            if test_code == 200:
                async for collection in client.get_collections():
                    tasks.append(asyncio.create_task(
                        _cache_resource(self._resource_cache, collection, client)
                    ))
                    collection_total += 1
                await asyncio.gather(*tasks)
            elif test_code == 401:
                on_cache_failure(f'Failed to retrieve online resources from OCLC: '
                                 f'The WSKey was invalid.')
            else:
                on_cache_failure(f'Failed to retrieve online resources from OCLC: '
                                 f'Could not connect to the OCLC WorldCat '
                                 f'Knowledge Base API endpoint.')
        await client.close()

        on_cache_end_event(f'Search complete. '
                           f'Found {resource_total} online resource(s) '
                           f'across {collection_total} collection(s).')
        
    async def check_resources(self,
                              on_check_start_event: Callable,
                              on_check_event: Callable,
                              on_check_end_event: Callable) -> None:
        """Check the availability of online resources by sending HTTP requests.

        This function attempts to identify the availability of online resources
        by sending HTTP HEAD requests to the resource's URL.
        The response code is added to the resource object, which is then
        cached.

        To communicate progress, the function uses a counter to track the
        number of cached results and displays messages through the callbacks
        provided in `on_check_start_event`, `on_check_event`, and
        `on_check_end_event`.

        Args:
            on_check_start_event (Callable): The function to call upon starting
                the link checking process.

            on_check_event (Callable): The function to call during
                the link checking process.

            on_check_end_event (Callable): The function to call upon stopping
                the link checking process.

        Returns:
            None: This function does not return a value.
        """
        async def _cache_result(cache: Cache, resource: dict, client: HTTPClient) -> None:
            """Asynchronously check an online resource's availability."""
            response = await client.head(resource['link'])
            resource['code'] = response.code
            # The entire resource object is cached to aid debugging.
            # This could be refactored to store only the collection ID and
            # the HTTP response code to save a bit of memory.
            await cache.cache_object(resource)
            async with self._lock:
                nonlocal link_count
                link_count += 1
                on_check_event(f'Checked {link_count} / {link_total} links.')

        link_count = 0
        link_total = await self._resource_cache.get_total_objects()

        on_check_start_event(f'Identified {link_total} links.')
        on_check_event(f'Checking links. Please do not exit...')

        async with self._http_client as client:
            # Randomization is used to decrease the chance of hitting multiple
            # URLs from the same domain in consecutive order (which might
            # result in us hitting a rate limit).
            async for resource in self._resource_cache.get_cached_objects(randomize = True):
                await _cache_result(self._results_cache, resource, client)
        await client.close()

        on_check_end_event(f'Check complete.')
    
    async def check_results(self,
                            on_analysis_start_event: Callable,
                            on_analysis_event: Callable,
                            on_analysis_end_event: Callable,
                            failure_threshold: float) -> None:
        """Analyze the cached link check results and report broken collections.
        
        This function looks through a cache file and counts the number of
        resources in each collection with non-200 status codes.
        If the total number of broken resources within a collection meets or
        exceeds the specified failure threshold, the collection is flagged
        as broken, and a message is displayed.
        
        To communicate progress, the function displays messages through callbacks
        provided in `on_analysis_start_event`, `on_analysis_event`, and
        `on_analysis_end_event`.

        Args:
            on_analysis_start_event (Callable): The function to call upon
                starting the link analysis process.

            on_analysis_event (Callable): The function to call during
                the link analysis process.

            on_analysis_end_event (Callable): The function to call upon
                stopping the link analysis process.

            failure_threshold (float): The maximum allowed proportion of broken
                links for a collection, rendered as a decimal (i.e. 0.5 for 5%).

        Returns:
            None: This function does not return a value.
        """
        async def get_results(cache: Cache) -> defaultdict[list[int]]:
            results = defaultdict(list[int])
            async for result in cache.get_cached_objects():
                results[result['cid']].append(1 if int(result['code']) != 200 else 0)
            return results
        
        on_analysis_start_event(f'Calculating percentages...')

        results = await get_results(self._results_cache)
        total_collections_broken = 0
        for k, v in results.items():
            total_resources = len(v)
            total_resources_broken = sum(v)
            percent_broken = round(total_resources_broken / total_resources, 2) \
                                   if total_resources > 0 \
                                   else 0.0
            if percent_broken >= failure_threshold:
                on_analysis_event(f'{percent_broken * 100}% '
                                  f'({total_resources_broken} / {total_resources}) '
                                  f'of links in collection {k} '
                                  f'could not be accessed.')
                total_collections_broken += 1
        on_analysis_end_event(f'Analysis complete. '
                              f'{total_collections_broken} collection(s) '
                              f'exceeded the failure threshold.')