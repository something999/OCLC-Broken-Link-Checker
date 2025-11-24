"""
Asynchronous client for handling API requests to the OCLC WorldCat Knowledge Base API.

This module provides a client for performing API calls using the aiohttp and
aiodns libraries for asynchronous networking and DNS resolution.
Only one client instance should be active at a time to avoid
connection conflicts (as noted in the aiohttp documentation).
"""
import asyncio
import csv
import io
import logging
from dataclasses import dataclass
from typing import AsyncIterator

from clients.http_client import HTTPClient, HTTPResponse

_logger = logging.getLogger(__name__)

#########################
# APIClient Structs
#########################

@dataclass
class CollectionMetadata:
    """Structure that holds identifying information for an OCLC collection.

    Attributes:
        cid (str): The collection's OCLC identifier.
        title (str): The collection's OCLC title.
        link (str): A URL pointing to a file describing the collection's contents.
    """
    cid: str = ''
    title: str = ''
    link: str = ''

    def is_empty(self) -> bool:
        """Returns true if the collection has no download link."""
        return not self.link

@dataclass
class ResourceMetadata:
    """Structure that holds identifying information for an OCLC resource.

    Attributes:
        cid (str): The OCLC identifier of the holding collection.
        rid (str): The resource's OCLC identifier.
        title (str): The resource's OCLC title.
        link (str): A URL pointing to the online resource's location.
        code (int): The HTTP status response code returned when a
            host attempts to access the online resource.
    """
    cid: str = ''
    rid: str = ''
    title: str = ''
    link: str = ''
    code: int = -1

    def is_empty(self) -> bool:
        """Returns True if the resource has no accessible link."""
        return not self.link

#########################
# HTTPClient Exceptions
#########################

class APIClientException(Exception):
    """Base class for API request issues."""
    pass

class OCLCKnowledgeBaseAPIException(APIClientException):
    """Base class for API request issues related to the OCLC WorldCat Knowledge Base API."""

class APIAuthenticationError(OCLCKnowledgeBaseAPIException):
    """Raised when an API request fails due to invalid credentials."""
    pass

class APIAccessError(OCLCKnowledgeBaseAPIException):
    """Raised when an API request fails due to invalid HTTP request."""
    pass

class APIConnectionError(OCLCKnowledgeBaseAPIException):
    """Raised when an API request fails due to a lack of server response."""
    pass

class InvalidJSON(OCLCKnowledgeBaseAPIException):
    """Raised when the API returns an unexpected response for a JSON request."""
    pass

class InvalidKBART(OCLCKnowledgeBaseAPIException):
    """Raised when the API returns an unexpected response for a KBART request."""
    pass

class MissingKBART(OCLCKnowledgeBaseAPIException):
    """Raised when a KBART file cannot be fetched from OCLC."""
    pass

#########################
# APIClient Class
#########################

class APIClient(HTTPClient):

    def __init__(self, api_key: str) -> None:
        """Asynchronous API client built on top of aiohttp.
        
        An API Client sends calls to the OCLC WorldCat Knowledge Base API endpoint
        and returns the API call response to the user.
        These API calls should contain information about the collections held
        by an institution (specifically those that belong to the institution
        registered on the API key).
        Optional headers and parameters can be used to control client behavior.
        
        Attributes:
            api_key (str): The API key needed to access the API endpoint.
                This needs to be an unexpired, valid key registered with the
                OCLC WorldCat Knowledge Base API service.

        Private Attributes:
            _api (str): A link to the OCLC WorldCat Knowledge Base API endpoint.
        """
        # The OCLC WorldCat Knowledge Base API uses the WSKeyLite method for
        # authentication, which involves sending the API key through
        # an HTTP header.

        # Increase the wait time to give the server enough time to respond.
        
        # Skip the ingorelist in case the API endpoint was mistakenly added.
        
        # Skip the robots.txt check, since the API key should give the user
        # explicit permission to access the service.

        # Skip the domains check, since we don't want the URLs registered under
        # the API service to be skipped.
        
        # Assume that any API call is permitted whenever the user provides
        # valid credentials.
        super().__init__(headers = {'wskey': api_key},
                         retries = 2,
                         requests = 10,
                         wait = 300,
                         enforce_ignorelist = False,
                         enforce_robots_policy = False,
                         check_domains_only = False)
        self._api = 'https://worldcat.org/webservices/kb/rest/collections/search'
        
    def update_api_key(self, api_key: str) -> None:
        """Update the client's API credentials."""
        if api_key == self.headers['wskey']:
            return
        self.headers = {'wskey': api_key}
        _logger.debug('APIClient: Value of WSKEY changed to "%s".', api_key)
        
    async def get(self, url: str, parameters: dict ={}) -> HTTPResponse:
        """Fetch a response from the REST API endpoint."""

        def _check_status_code(response: HTTPResponse) -> None:
            """Check whether the API call was successful."""
            # A 401 code is returned when the user provides invalid or expired
            # API credentials (i.e. a key that does not have permission to
            # access the OCLC WorldCat Knowledge Base API service).

            # A 403 code is returned when the user is not authorized to access
            # the API service. This is usually due to the user not having the 
            # OCLC Knowedge Base API registered on their WSKey or the user
            # attempting to validate themselves through an unsupported 
            # method (i.e. HMAC signatures).

            # A 405 code is raised when the user attempts to access the 
            # service through an invalid HTTP method.

            # A 500 code is often returned when the user cannot access
            # the API service. This can be triggered when the user exceeds
            # the rate limit. 
            if not response:
                raise APIConnectionError
            match (response.code):
                case 200:
                    pass
                case 202:
                    pass
                case 401:
                    raise APIAuthenticationError
                case 403:
                    raise APIAuthenticationError
                case 405:
                    raise APIAccessError
                case 500:
                    raise APIConnectionError
                case _:
                    raise APIConnectionError

        response = await super().get(url, parameters)

        try:
            _check_status_code(response)
        except APIAuthenticationError:
            _logger.error('Failed to connect to OCLC WorldCat Knowledge Base -'
                          'User provided invalid or expired WSKey.')
        except APIAccessError:
            _logger.error('Failed to connect to OCLC WorldCat Knowledge Base - '
                          'Service does not support HTTP GET requests.')
        except APIConnectionError:
            _logger.error('Failed to connect to OCLC WorldCat Knowledge Base - '
                          'Could not connect to API endpoint '
                          'at URL "%s".', url)
        except Exception:
            _logger.exception(f'Failed to connect to OCLC WorldCat Knowledge Base')
        finally:
            return response
        
    async def get_connection_test_result(self) -> int:
        """Send a HTTP GET request to the API endpoint and return its status."""
        response = await self.get(self._api,
                                  parameters = {'startIndex': 1, 
                                                'itemsPerPage': 1})
        return response.code
            
    async def get_collections(self) -> AsyncIterator[CollectionMetadata]:
        """Return the collections enabled by the user's institution."""
        # OCLC issues API keys to institutions.
        # An API key only grants users access to collections that the
        # institution has enabled within the OCLC system.
        total = await self.get_total_collections()
        # The OCLC WorldCat Knowledge Base API allows users to retrieve up to 50 items
        # per search results page.
        batches = [(i, min(50, total - i + 1)) for i in range(1, total + 1, 50)]
        subcollections = await asyncio.gather(
            *(self.get
                (
                    self._api,
                    parameters={'startIndex': start, 'itemsPerPage': count}
                ) for start, count in batches),
            return_exceptions=True
        )
        # The OCLC WorldCat Knowledge Base API is supposed to return a series of
        # nested JSON objects.
        try:
            for subcollection in subcollections:
                if not isinstance(subcollection.content, dict):
                    raise InvalidJSON

                for entry in subcollection.content['entries']:
                    collection = self._get_collection_metadata(entry)
                    yield collection
        except (APIAuthenticationError, APIConnectionError):
            _logger.error('Failed to retrieve collections from OCLC - '
                          'Could not connect to API endpoint '
                          'at URL "%s".', self._api)
            yield CollectionMetadata()
        except InvalidJSON:
            _logger.error('Failed to retrieve collections from OCLC - '
                          'API did not return a JSON object.')
            yield CollectionMetadata()
        except Exception:
            _logger.exception('Failed to retrieve collections from OCLC')
            yield CollectionMetadata()

    async def get_resources(self, collection: CollectionMetadata) -> AsyncIterator[ResourceMetadata]:
        """Return the resources in an OCLC collection."""
        response = await self.get(collection.link)

        try:
            if not response or response.code >= 400:
                raise MissingKBART
            if not isinstance(response.content, str):
                raise InvalidKBART
            
            reader = csv.DictReader(io.StringIO(response.content), delimiter = '\t')
            for row in reader:
                resource = self._get_resource_metadata(collection.cid, row)
                yield resource
            
        except InvalidKBART:
            _logger.warning('Failed to find resources for collection %s - '
                            'API did not return KBART.', 
                            collection.cid)
            yield self._get_resource_metadata(collection.cid, None)
        except MissingKBART:
            _logger.warning('Failed to find resources for collection %s - '
                            'Could not download KBART from OCLC.', 
                            collection.cid)
            yield self._get_resource_metadata(collection.cid, None)
        except Exception:
            _logger.warning(f'Failed to find resources for collection %s', 
                            collection.cid)
            yield self._get_resource_metadata(collection.cid, None)

    async def get_total_collections(self) -> int:
        """Return the total number of collections held by the user's institution."""
        try:
            response = await self.get(self._api,
                                      parameters = {'startIndex': 1, 
                                                    'itemsPerPage': 1})
            return int(response.content['os:totalResults']) \
                    if response and response.code == 200 else 0
        except Exception:
            return 0

    def _get_collection_metadata(self, json: dict) -> CollectionMetadata:
        """Extract collection metadata elements from a nested JSON object.
        
        This function assumes that every collection has exactly one id,
        title, and link.
        
        Attributes:
            json (dict): A REST API JSON object that contains information on
                an OCLC collection. This function assumes that the JSON
                object follows the JSON specifications provided by the
                October 2025 OCLC WorldCat Knowledge Base API documentation.
        """
        def _get_cid(json: dict) -> int:
            # Helper function that extracts the collection's OCLC identifier.
            return json['kb:collection_uid'] if json and 'kb:collection_uid' in json else ''
        
        def _get_title(json: dict) -> str:
            # Helper function that extracts the collection's OCLC title.
            return json['title'] if json and 'title' in json else ''
        
        def _get_link(json: dict) -> str:
            # Helper function that extracts the collection's download link.
            if not json or not 'links' in json:
                return ''
            return {link['href'] for link in json['links'] \
                    if link['rel'] == 'enclosure'}.pop()
        
        if not json:
            return CollectionMetadata()
        return CollectionMetadata(cid = _get_cid(json),
                                  title = _get_title(json),
                                  link = _get_link(json))

    def _get_resource_metadata(self, cid: str, row: dict) -> ResourceMetadata:
        """Extract resource metadata elements from a KBART row."""
        # This function assumes that the row is being parsed by a 
        # csv.DictReader object.
        def _get_rid(row: dict) -> str:
            # Helper function that extracts the publication's OCLC identifier.
            return row['oclc_number'] if row and 'oclc_number' in row else ''

        def _get_title(row: dict) -> str:
            # Helper function that extracts the publication title
            return row['publication_title'] if row and 'publication_title' in row else ''

        def _get_link(row: dict) -> str:
            # Helper function that extracts the publication's URI.
            return row['title_url'] if row and 'title_url' in row else ''
        
        return ResourceMetadata(cid = cid,
                                rid = _get_rid(row),
                                title = _get_title(row),
                                link = _get_link(row),
                                code = -1)