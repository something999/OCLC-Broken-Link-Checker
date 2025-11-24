"""
Configuration options and functions.

This module contains functions for reading and writing config files, which
are JSON files that store information related to program settings.
"""
from dataclasses import dataclass, field, asdict
import json
from json import JSONDecodeError
import logging
from typing import Any

from utils import file_utils, http_utils

_logger = logging.getLogger(__name__)

#########################
# ConfigManager Structs
#########################

@dataclass
class Config:
    """Store configurable modifiable program settings.
    
    Attributes:
        wskey (str): The WSKey required to access the OCLC WorldCat Knowledge Base API.

        user_agent (str): A string that servers can use to identify the client.
            Certain servers may not return a response if no user-agent string
            is provided.

        ignorelist (list[str]): A list of URL domains to exclude from broken
            link checks. This prevents links from known unreachable domains
            from being flagged as broken.

        failure_threshold (int | float): The maximum allowed proportion of
            broken links for a given collection, rendered as a decimal
            capped between 0.0 and 1.0.
            If the collection proportionally contains at least that many
            broken links, the entire collection is flagged as broken.
            A value of 0.0 corresponds to 0%; a value of 1.0 corresponds to 100%
    """
    wskey: str = ''
    user_agent: str = ''
    ignorelist: list[str] = field(default_factory = list[str])
    failure_threshold: int | float = 0.00

#########################
# ConfigManager Exceptions
#########################
class ConfigException(Exception):
    """Base class for errors related to the reading and writing of config files."""

class InvalidConfig(ConfigException):
    """Raised when the config file contains unusable values."""

class MissingConfig(ConfigException):
    """Raised when the config file cannot be loaded or parsed."""

#########################
# ConfigManager Class
#########################

class ConfigManager:

    def __init__(self, path: str) -> None:
        """JSON file reader and writer.
        
        A ConfigManager handles the storage and retrieval of modifiable program
        settings using persistent JSON files.
        These JSON files are automatically accessed upon program startup and
        saved whenever the uesr updates a setting through the GUI.
        
        Attributes:
            path (str): An absolute or relative path to a config file.
        
        Private Attributes:
            _last_config (Config): A copy of the last known program settings.
        """
        self.path = path
        self.reset_config()
        self._last_config = self.load_config()

    def reset_config(self) -> None:
        """Create a new config file, if one does not already exist."""
        if file_utils.is_file(self.path):
            return
        file_utils.add_file(self.path)
        self.save_config(Config())

    def save_config(self, config: Config) -> None:
        """Save new config settings into a JSON file."""
        try:
            with open(self.path, mode = 'w', encoding = 'utf-8', newline = '') as file:
                file.write(json.dumps(asdict(config), indent = 4))
            self._last_config = config
        except PermissionError:
            _logger.error('Failed to save config file - '
                          'User does not have permission to save files at '
                          '%s. Please check file and folder permissions.',
                          self.path)
        except OSError as e:
            _logger.debug('Failed to save config file - %s', e)
        except Exception as e:
            _logger.debug('Failed to save config file - %s', e)

    def load_config(self) -> Config:
        """Load a series of config settings from a JSON file.
        
        If a config file does not exist, the program will attempt to return
        the default configuration settings.
        """
        try:
            if not file_utils.is_file(self.path):
                raise MissingConfig
            with open(self.path, mode = 'r', encoding = 'ascii', newline = '') as file:
                data = json.load(file)
                wskey = self._load_setting(data, 'wskey')        
                user_agent = self._load_setting(data, 'user_agent')
                ignorelist = self._load_setting(data, 'ignorelist')
                failure_threshold = self._load_setting(data, 'failure_threshold')
                return Config(wskey = wskey,
                              user_agent = user_agent,
                              ignorelist = ignorelist,
                              failure_threshold = failure_threshold)
        except MissingConfig:
            _logger.error('Failed to load config file - '
                          'File does not exist at "%s". '
                          'Using default config settings.', self.path)
            return Config()
        except JSONDecodeError as e:
            _logger.error('Failed to load config file - %s', e)
        except PermissionError:
            _logger.error('Failed to load config file - '
                          'User does not have permission to read files at '
                          '%s. Please check file and folder permissions.',
                          self.path)
        except OSError as e:
            _logger.debug('Failed to load config file - %s', e)
        except Exception as e:
            _logger.debug('Failed to load config file - %s', e)
            
    def _load_setting(self, data: dict, setting: str) -> Any:
        """Load a single config value from the config file."""
        if setting not in data:
            _logger.warning('Failed to load config setting %s - '
                            'setting not found. '
                            'Replacing with default setting.', setting)
            return getattr(Config(), setting)
        else:
            return data[setting]

    def update_config(self, config: dict) -> str | None:
        """Update values stored within the config file.
        
        This function also performs value sanitization and validation.
        For the value to be valid:
            - The WSKey value must be a non-empty string.
            - The User-Agent value must be a string.
            - The ignorelist value must be a comma-separated string.
            - The failure_threshold value must be a float between 0.0 and 1.0.
        """
        def _get_wskey(config: dict, errors: str) -> tuple[str, str]:
            """Helper function that sanitizes and checks the WSKey value."""
            raw_wskey = str(config.get('wskey', '')).strip()
            if len(raw_wskey) == 0:
                errors += 'WSKey must be a non-empty string.'
            return raw_wskey, errors
        
        def _get_user_agent(config: dict, errors: str) -> tuple[str, str]:
            """Helper function that sanitizes and checks the User-Agent value."""
            raw_user_agent = str(config.get('user_agent', '')).strip()
            return raw_user_agent, errors
        
        def _get_ignorelist(config: dict, errors: str) -> tuple[list[str], str]:
            """Helper function that sanitizes and checks the ignorelist value."""

            raw_ignorelist = str(config.get('ignorelist', '')).split(',')
            ignorelist = [http_utils.get_domain(link) for link in raw_ignorelist]

            # Set would be more efficient, but list was more convenient.
            error_list = []
            for i in range(len(raw_ignorelist)):
                if raw_ignorelist[i] != ignorelist[i]:
                    error_list.append(raw_ignorelist[i])
            
            if len(error_list) > 0:
                errors = f"Domain(s) {', '.join (error_list)} " \
                         f"not recognized as valid domains."
        
            # Sort the ignorelist to make it easier to parse.
            return sorted(ignorelist), errors
        
        def _get_failure_threshold(config: dict, errors: str) -> tuple[float, str]:
            """Helper function that sanitizes and checks the fail threshold value."""
            try:
                raw_threshold = float(config.get('failure_threshold', -1.0))
                threshold = round(raw_threshold, 3)
                if threshold < 0.0 or threshold > 1.0:
                    raise ValueError
            except ValueError:
                errors += 'Fail threshold must be a numerical value between ' \
                        '0.0 and 1.0'
                # Signal that this value was invalid.
                threshold = -1.0
            finally:
                return threshold, errors
            
        # This is the error message that gets printed out to the console.
        error_string = ''
        errors = ''
        try:
            wskey, errors = _get_wskey(config, errors)
            user_agent, errors = _get_user_agent(config, errors)
            ignorelist, errors = _get_ignorelist(config, errors)
            failure_threshold, errors = _get_failure_threshold(config, errors)

            _logger.debug('Config: Detected attempt to update config with the '
                          'following values: WSKEY: %s, USER_AGENT: %s, '
                          'IGNORELIST: %s; failure_threshold: %s',
                          wskey, user_agent, ignorelist, failure_threshold)
            
            if len(errors) > 0:
                error_string = 'Failed to save all changes to config: ' + errors
            
            if wskey == '':
                wskey = self._last_config.wskey
            if user_agent == '':
                user_agent = self._last_config.user_agent
            if failure_threshold == -1.0:
                failure_threshold = self._last_config.failure_threshold

            self.save_config(Config(wskey = wskey,
                                    user_agent = user_agent,
                                    ignorelist = ignorelist,
                                    failure_threshold = failure_threshold))
            
            return error_string

        except PermissionError:
            _logger.error('Failed to update config file - '
                          'User does not have permission to access file at '
                          '%s. Please check file and folder permissions.',
                          self.path)
        except OSError as e:
            _logger.error('Failed to update config file - %s', e)
        except Exception as e:
            _logger.error('Failed to update config file - %s', e)