"""
Utility functions for handling URLs.

This module contains functions for reading, writing, and checking URL components
and HTTP headers.
"""
from datetime import datetime

import tldextract # Requires Python 3.9+
import validators # Requires Python 3.9+

# tldextract caches a copy of the Public Suffix List to avoid
# re-downloading the list on every use.

# While it is possible to skip the caching process, by calling
# tldextract.TLDExtract(cache_dir = None) in get_domain, 
# each new TLDExtract object will require us to re-download the
# Public Suffix List, adding an unnecessary network call.
_tldextract = tldextract.TLDExtract(cache_dir = './caches/')

def get_domain(url: str) -> str:
    """Extract the domain from the URL.

    URL extraction is performed through the tldextract library, which uses
    information provided by the Public Suffix List to identify the registered
    domain and suffix.

    Examples:
        - get_domain('https://google.com') -> 'google.com'
        - get_domain('https://google.github.io') -> 'github.io'
        - get_domain('https://about.google.com') -> 'about.google.com'
    
    Args:
        url (str): A full URL string.
        
    Returns:
        (str): The domain portion of the URL. If the domain cannot be parsed,
            an empty string is returned.
    """
    if not isinstance(url, str):
        return ''
    return _tldextract.extract_str(url).top_domain_under_registry_suffix

def is_domain(domain: str) -> bool:
    """Check whether a string is a syntactically correct domain name.

    Domain validation is performed through the validators library, which uses
    regular expressions to determine if a string could represent the domain.

    The function is unable to determine whether the domain exists.

    Examples:
        - is_domain('x') -> False
        - is_domain('google.com') -> True
    
    Args:
        domain (str): The string to validate.

    Returns:
        bool: True if the string could represent a domain. False if not.
    """
    try:
        return validators.domain(domain)
    except validators.ValidationError:
        return False
    except Exception:
        return False
    
def get_http_date(date: str) -> datetime | None:
    """Convert a HTTP Date header string into a datetime object.

    The rules for identifying HTTP Date header strings are defined at:
    https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Date
    
    Args:
        date (str): A HTTP Date header string 
            (i.e. 'Thurs, 01 Jan 1970 00:00:00 GMT')
            
    Returns:
        datetime.datetime: A datetime object if the conversion is successful.
            None if not.
    """
    try:
        return datetime.strptime(date, '%a, %d %b %Y %H:%M:%S GMT')
    except ValueError:
        return None
    except Exception:
        return None

def is_http_date(date: str) -> bool:
    """Check whether a string represents a valid HTTP Date header.
    
    The rules for validating HTTP Date header strings are defined at:
    https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Date
    
    Args: 
        date (str): A string to validate against the HTTP Date format.
        
    Returns:
        bool: True if the string matches the expected format. False if not.
    """
    return get_http_date(date) != None