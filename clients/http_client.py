"""
Asynchronous client for handling HTTP requests.

This module provides a generic client for performing HTTP requests using
the aiohttp and aiodns libraries for asynchronous networking and DNS
resolution. 
Only one client instance should be active at a time to avoid
connection conflicts (as noted in the aiohttp documentation).
"""
import asyncio
from dataclasses import dataclass
import logging
import random
import urllib.parse
import urllib.robotparser

import aiohttp # Requires Python 3.10+. Optional aiodns library recommended.

from utils import http_utils
from utils import time_utils

_logger = logging.getLogger(__name__)

#########################
# HTTPClient Structs
#########################

@dataclass
class HTTPResponse:
    """Structure to store information returned by an HTTP request.

    A HTTPResponse stores metadata about the response returned by a web
    server, including the request URL, HTTP status code, and HTTP message 
    body.
    
    Attributes:
        url (str): The URL that the HTTP request was sent to.
        code (int): The HTTP status code.
        content (str): The HTTP message body.
    """
    url: str = ''
    code: int = -1
    content: str = ''

    def is_empty(self) -> bool:
        """Return True if the response has no content."""
        return not self.url and self.code == -1 and not self.content


#########################
# HTTPClient Exceptions
#########################

class HTTPClientException(Exception):
    """Base class for HTTP request issues not covered in aiohttp."""
    pass

class UnsupportedRequest(HTTPClientException):
    """Raised when the user attempts to send a HTTP request using an unknown method."""
    # Supported methods: GET, HEAD
    pass

class MaxRetriesExceeded(HTTPClientException):
    """Raised when the user has exceeded the max number of retries."""
    pass

class RobotsTxtException(Exception):
    """Base class for robots.txt issues."""

class MissingRobotsTxtURL(RobotsTxtException):
    """Raised when a robots.txt URL cannot be found or formed."""
    pass

class MissingRobotsTxtFile(RobotsTxtException):
    """Raised when a robots.txt fille cannot be found."""
    pass

class MissingRedirect(Exception):
    """Raised when a link contains no known redirect policy."""
    pass

#########################
# HTTPClient Class
#########################

class HTTPClient:

    def __init__(self,
                 headers: dict[str, str] = None,
                 retries: int = 2,
                 requests: int = 5,
                 wait: int = 60,
                 ignorelist: set[str] = set(),
                 enforce_ignorelist: bool = True,
                 enforce_robots_policy: bool = True,
                 check_domains_only: bool = False) -> None:
        """Asynchronous HTTP client built on top of aiohttp.

        A HTTP Client sends GET and HEAD requests to specified URLs and returns
        their responses to the user.
        Optional headers and parameters can be used to control client behavior.

        Attributes:
            headers (dict[str, str], optional): The headers to include
                with each request.

            max_retries (int, optional): The maximum number of times to retry
                 a failed request (failure defined as not in the range of 
                 200, 202, 400, 401, 403, 404, 410, 429, 451, or 503).
            
            max_requests (int, optional): The maximum number of concurrent
                requests.

            max_wait (int, optional): The maximum number of seconds to wait on
                a request.

            ignorelist (set[str], optional): A series of domains to "skip" when
                performing requests (i.e. sites known to block web-crawlers or
                web-scrappers). If the client attempts to send a response to
                a URL that falls under this ignorelist, the client will return
                a fallback empty response.

            enforce_ignorelist (bool, optional): If True, forces the client to
                not use the ignorelist.

            enforce_robots_policy (bool, optional): If True, forces the client
                to check for a robots.txt file before scrapping the URL.

            check_domains_only (bool, optional): If True, forces the client to
                determine URL access based on domain access 
                (i.e. 'https://google.com' is considered accessible if
                'google.com' returned a 200 response).

        Private Attributes:
            _session (aiohttp.ClientSession | None): The active client session
                used to send requests. If None, the _session is initialized
                lazily.

            _semaphore (asyncio.Semaphore): The semaphore that controls the
                number of concurrent HTTP requests.

            _timeout (aiohttp.ClientTimeout): An object that manages request
                timeouts.

            _tasks (dict[str, asyncio.Future]): An internal cache of pending 
                tasks. This cache is used to control the order of
                the robots.txt checks.

            _redirect_policies (dict[str, bool]): An internal cache that
                records redirection behaviors by domain (with True meaning
                that the domain redirects users to other links).

            _robots_policies (dict[str, bool]): An internal cache that
                records the robots.txt results by domain (with True meaning
                that the domain allows users to scrape the website).
        """
        self.headers = headers or {}
        self.max_retries = retries
        self.max_requests = requests
        self.max_wait = wait
        self.ignorelist = ignorelist
        self.enforce_ignorelist = enforce_ignorelist
        self.enforce_robots_policy = enforce_robots_policy
        self.check_domains_only = check_domains_only
        
        self._session = None
        self._semaphore = asyncio.Semaphore(self.max_requests)
        self._timeout = aiohttp.ClientTimeout(total = self.max_wait)
        self._tasks = dict()
        self._redirect_policies = dict()
        self._robots_policies = dict()

        _logger.debug(
            'Initialized client with the following parameters: '
            'HEADERS: %s, MAX RETRIES: %s, MAX REQUESTS: %s, MAX_WAIT_TIME: %s, '
            'IGNORELIST: %s; ENFORCE_IGNORELIST: %s, ENFORCE_ROBOTS_POLICY: %s, '
            'CHECK_DOMAINS_ONLY: %s',
            self.headers,
            self.max_retries,
            self.max_requests,
            self.max_wait,
            self.ignorelist,
            self.enforce_ignorelist,
            self.enforce_robots_policy,
            self.check_domains_only
        )

    async def __aenter__(self) -> None:
        """Initialize a persistent aiohttp ClientSession if one doesn't exist.

        This allows the client to be reused across multiple context entries.
        """
        if not self._session:
            connector = aiohttp.TCPConnector(limit = self.max_requests, 
                                             limit_per_host = self.max_requests)
            self._session = aiohttp.ClientSession(connector = connector, 
                                                  headers = self.headers)
        return self
    
    async def __aexit__(self, *args, **kwargs) -> None:
        """Override the default context exit behavior to keep the session open.

        The default behavior is overwritten to prevent the automatic teardown
        of the aiohttp ClientSession, allowing this client to be reused.
        """
        pass

    async def close(self) -> None:
        """Close the current aiohttp ClientSession if it is still open."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def update_user_agent(self, user_agent: str) -> None:
        """Update the client's User-Agent header."""
        if 'User-Agent' in self.headers and self.headers['User-Agent'] == user_agent:
            return
        self.headers['User-Agent'] = user_agent
        _logger.debug('HTTPClient: Value of HEADERS changed to "%s".',
                      self.headers)

    def update_ignorelist(self, ignorelist: list[str]) -> None:
        """Replace the domains within this client's ignorelist."""
        if self.ignorelist == set(ignorelist):
            return
        # Set used to eliminate duplicate domains and provide O(1) access.
        self.ignorelist = set(ignorelist)
        _logger.debug('HTTPClient: Value of IGNORELIST changed to "%s".',
                      self.ignorelist)

    def update_check_type(self, check_domains_only: bool) -> None:
        """Update the client's link-checking policy."""
        if self.check_domains_only == check_domains_only:
            return
        self.check_domains_only = check_domains_only
        _logger.debug('HTTPClient: Value of CHECK_DOMAINS_ONLY changed to "\%s".',
                      self.check_domains_only)

    async def _send(self,
                    method: str,
                    url: str,
                    headers: dict,
                    parameters: dict = dict(),
                    allow_retries: bool = True) -> HTTPResponse:
        """Send an HTTP request and return the response.
        
        Provides a GET or HEAD request to the specified URL, interprets the
        server's response, and stores the result in an HTTPResponse object.
        
        If the response cannot be parsed, an empty HTTPResponse object is
        returned.
        """    
        def _get_code(response: aiohttp.ClientResponse) -> int:
            """Fetch the status code from the HTTP response."""
            return response.status if response else -1

        async def _get_content(response: aiohttp.ClientResponse) -> str:
            """Fetch and parse the message body from the HTTP response."""
            if not response or method == 'HEAD':
                return ''
            
            match (response.content_type):
                case 'application/json':
                    return await response.json()
                case 'application/octet-stream':
                    return await response.text(encoding = 'utf-8', errors = 'replace')
                case 'text/html' | 'text/plain' | 'text/xml':
                    return await response.text(encoding = 'utf-8', errors = 'replace')
                case _:
                    _logger.error('Unable to decode HTTP message body for '
                                  'URL "%s".',
                                  response.url)
                    return ''

        async def _get_response(response: aiohttp.ClientResponse) -> HTTPResponse:
            """Generate a HTTPResponse object for the aiohttp.ClientResponse"""
            # aiohttp.CilentResponse stores the URL as a yarl.URL object.
            # A typecast is used here to avoid issues with the http_utils
            # functions (which expect the URL to be a string object).
            url = str(response.url)
            code = _get_code(response)
            content = await _get_content(response)
            return HTTPResponse(url, code, content)
        
        def _get_wait_time(response: aiohttp.ClientResponse, retries: int) -> float:
            """Determine the amount of wait time before retrying a request.
            
            The helper function attempts to look for a Retry-After header to
            determine the wait time.

            If no Retry-After header is found, the client defaults to an
            exponential backoff with jitter that is capped at 60 seconds.
            """
            time = response.headers.get('Retry-After')
            if time != None and http_utils.is_http_date(time):
                return time_utils.get_delta(http_utils.get_http_date(time),
                                            time_utils.get_current_time())
            elif time != None and time.isdigit():
                return float(time) + random.uniform(0, 1)
            return min(2 ** retries + random.uniform(0, 1), 60)

        def _is_valid_method(method: str) -> bool:
            """Check whether the method is supported by this client."""
            return method in {'GET', 'HEAD'}

        def _has_valid_code(response: HTTPResponse) -> bool:
            """Check whether the response contains a valid status code.
             
            Because the link checker is only concerned with URL access, the 
            acceptable response status codes are:
                - 200 (OK)
                - 202 (Accepted)
                - 400 (Bad Request)
                - 401 (Unauthorized)
                - 403 (Forbidden)
                - 404 (Not Found)
                - 410 (Gone)
                - 429 (Too Many Requests)
                - 451 (Unavailable for Legal Reasons)
                - 503 (Service Unavailable)
            """
            if not response:
                return False
            return response.code in {200, 202, 400, 401, 403, 404, 410, 429, 451, 503}
        
        def _has_valid_content(response: HTTPResponse) -> bool:
            """Check whether the repsonse contains content.
            
            This helper function checks if a GET request returned any content
            from the web server.
            """
            if not response:
                return False
            if method == 'HEAD':
                return True
            if method == 'GET':
                return len(response.content) > 0
            return False

        def _log_request(method: str,
                         url: str,
                         headers: dict[str, str],
                         parameters: dict[str, str]) -> None:
            """Record the HTTP request in a log file."""
            _logger.info('Sent HTTP %s request to URL "%s" with headers "%s" '
                         'and parameters "%s".', method, url, headers, parameters)
            
        def _log_response(response: aiohttp.ClientResponse,
                          url: str,
                          retries: int) -> None:
            """Record the HTTP response returned by aiohttp."""
            _logger.info('Received response %s from URL "%s" '
                         'after %s retries.', response, url, retries)

        retries = 0
        response = None
        result = HTTPResponse()

        try:
            if not _is_valid_method(method):
                raise UnsupportedRequest

            while (not _has_valid_code(result) \
                    or not _has_valid_content(result)) \
                    and retries <= self.max_retries:
                _log_request(method, url, headers, parameters)

                async with self._semaphore:
                    response = await self._session.request(method = method,
                                                           url = url,
                                                           headers = headers,
                                                           params = parameters,
                                                           timeout = self._timeout)
                result = await _get_response(response)
                _log_response(response, url, retries)
                
                # Process one HTTP request before breaking the loop
                if not allow_retries:
                    break
                retries += 1
                # Sleep for politeness.
                await asyncio.sleep(_get_wait_time(response, retries))

            if retries >= self.max_retries:
                raise MaxRetriesExceeded

        except aiohttp.InvalidURL:
            _logger.warning('Failed to send HTTP %s request to URL "%s" - '
                            'URL is not a link.', method, url, url)
        except (aiohttp.ConnectionTimeoutError, TimeoutError):
            _logger.warning('Failed to send HTTP %s request to URL "%s" - '
                            'Request timed out.', method, url)
        except MaxRetriesExceeded:
            # Loop breaks when retries exceeds self.max_retries.
            # This means that retries will always be self.max_retries + 1.
            _logger.warning('Failed to send HTTP %s request to URL "%s" - '
                            'Server returned invalid response after %s retries.',
                            method, url, retries - 1)
        except UnsupportedRequest:
            _logger.error('Failed to send HTTP %s request to URL "%s" - '
                          'Method was not of type GET or HEAD.', method, url)
        except aiohttp.ClientConnectionError:
            _logger.warning('Failed to send HTTP %s request to URL "%s" - '
                            'Client could not connect to server.', method, url)
        except aiohttp.ServerConnectionError:
            _logger.warning('Failed to send HTTP %s request to URL "%s" - '
                            'Server could not be reached.', method, url)
        except Exception:
            _logger.exception('Failed to send HTTP %s request to URL "%s"',
                              method, url)
        finally:
            return result if isinstance(result, HTTPResponse) else HTTPResponse()
     
    async def _can_access(self, method: str, url: str) -> tuple[bool, str]:
        """Check whether a user can scrape a website for information."""

        async def _resolve_redirect(url: str) -> str:
            """Check whether a URL will redirect a user to a new website."""
            # In an ideal world, the headers of a HTTP request would tell us
            # the final destination of the resource.
            
            # In practice, persistent identifiers (i.e. DOIs) will often
            # designate themselves as the final destination, even though they
            # redirect to other websites.

            # Since the headers are not reliable, we send a HEAD request to
            # determine the true target domain. This means that we technically
            # access the page before checking the robots.txt file.

            # We want to ensure that the robots.txt file is sent to the
            # final target domain, not the identifier's domain. But in doing
            # so, the function adds overhead to the link-checking process.

            # The function could be refactored for performance reasons.
            domain = http_utils.get_domain(url)
            try:
                is_redirect = self._redirect_policies.get(domain)
                if is_redirect != None and not is_redirect:
                    return url
                raise MissingRedirect
            except MissingRedirect:
                response = await self._send(method = 'HEAD',
                                            url = url,
                                            headers = self.headers,
                                            allow_retries = False)
                target = response.url if response and not response.is_empty() else url
                self._redirect_policies[domain] = (target != url)
                return target
            except Exception as e:
                _logger.warning('Failed to resolve URL "%s" - %s', url, e)
                return url

        def _check_ignorelist(domain: str) -> bool:
            """Check whether a URL should be skipped (using the ignorelist)."""
            if domain in self.ignorelist:
                _logger.warning('Failed to send HTTP %s request to URL "%s" - '
                                'Domain was in ignorelist.', method, url)
                return False
            return True

        async def _check_robots_txt(domain: str, url: str) -> bool:
            """Check whether a URL can be accessed (using the robots.txt file)."""
            if domain in self._robots_policies:
                _logger.debug('Used robots.txt check value of ' \
                              '%s for domain "%s".', self._tasks[domain], domain)
                return self._robots_policies[domain]
            
            robots_result = self._tasks.get(domain)
            if robots_result:
                return await robots_result
            
            robots_result = asyncio.Future()
            self._tasks[domain] = robots_result

            try:
                # Assume that if the robots.txt file cannot be found,
                # we are allowed to crawl this website.
                result = True

                if len(domain) == 0:
                    raise MissingRobotsTxtURL
                
                robots_url = urllib.parse.urljoin(f'https://{domain}', '/robots.txt')
                response = await self._send(method = 'GET',
                                            url = robots_url,
                                            headers = self.headers,
                                            allow_retries = False)
                if not response:
                    raise MissingRobotsTxtFile
                if response.code == 200:
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse(response.content.splitlines())
                    result = parser.can_fetch('*', url)
                elif 400 <= response.code <= 499:
                    result = False
                else:
                    result = False
            except (aiohttp.InvalidURL, MissingRobotsTxtURL):
                _logger.warning('Failed to find robots.txt file for URL "%s" - '
                                'URL is missing components.', url)
            except MissingRobotsTxtURL:
                _logger.warning('Failed to find robots.txt file for URL "%s" - '
                                'No file found.', url)
            except Exception as e:
                _logger.warning('Failed to find robots.txt file for URL "%s" - '
                                '%s.', url, e)
            finally:
                self._robots_policies[domain] = result
                _logger.debug(f'Recorded robots.txt check value of %s '
                              f'for domain "%s".', result, domain)
                robots_result.set_result(result)

            return await robots_result
            
        # Skip check entirely if we know we have express permission
        # to access this website.
        # This is meant to help reduce overhead during API calls.
        if not self.enforce_ignorelist and not self.enforce_robots_policy:
            return True, url

        # The redirection resolution is meant to account for identifiers such as
        # doi.org, which will always redirect the user to another website.
        target = await _resolve_redirect(url)
        domain = http_utils.get_domain(target)
        _logger.debug('Resolved URL "%s" to URL "%s" under domain "%s".',
                      url, target, domain)
        passed_ignorelist = _check_ignorelist(domain) \
                        if self.enforce_ignorelist \
                        else True
        passed_robots = await _check_robots_txt(domain, target) \
                        if self.enforce_robots_policy \
                        else True

        if not passed_robots:
            _logger.warning('Failed to send HTTP %s request to URL "%s" - '
                            'URL domain does not allow crawling.',
                            method, url)

        return passed_ignorelist and passed_robots, target
    
    async def get(self, url: str, parameters: dict[str, str] = dict()) -> HTTPResponse:
        """Send an HTTP GET request to a URL and return the response.
        
        Args:
            url (str): The target link.
            parameters (dict[str, str], optional): The parameters to send with
                each request.
        """
        access, target = await self._can_access('GET', url)
        if not access:
            return HTTPResponse(url, -1, -1)
        if self.check_domains_only:
            return HTTPResponse(url, 200, '') \
                   if self._robots_policies[http_utils.get_domain(target)] \
                   else HTTPResponse(url, -1, '')
        return await self._send(method = 'GET', 
                                url = url,
                                headers = self.headers,
                                parameters = parameters)
        
    async def head(self, url: str, parameters: dict = {}) -> HTTPResponse:
        """Send an HTTP HEAD request to a URL and return the response.
        
        Args:
            url (str): The target link.
            parameters (dict[str, str], optional): The parameters to send with
                each request.
        """
        access, target = await self._can_access('HEAD', url)
        if not access:
            return HTTPResponse(url, -1, -1)
        if self.check_domains_only:
            return HTTPResponse(url, 200, '') \
                   if self._robots_policies[http_utils.get_domain(target)] \
                   else HTTPResponse(url, -1, '')
        return await self._send(method = 'HEAD', 
                                url = url,
                                headers = self.headers,
                                parameters = parameters)