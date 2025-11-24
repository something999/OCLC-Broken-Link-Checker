"""
Logic coordinator for the OCLC Link Checker application.

This module provides functions that handle communication between the GUI logic
in LinkCheckerAppWindow and the execution logic in LinkCheckerCore. These 
functions handle event registration and config file manipulation. 

This module is meant to be used with LinkCheckerCore and LinkCheckerAppWindow.
"""
import asyncio
import threading
from typing import Callable

from app.config import ConfigManager
from app.cache import Cache
from app.link_checker_core import LinkCheckerCore
from clients.api_client import APIClient
from clients.http_client import HTTPClient

class LinkCheckerController:

    def __init__(self, config_path: str,
                 resource_cache_path: str,
                 result_cache_path: str) -> None:
        """Controller for coordinating logic between the GUI and core.
        
        The LinkCheckerController class acts as the central logical coordinator
        between the front-end of the application (the GUI) and the back-end of
        the application (the link-checking and link-analysis functions).

        In order to coordinate this logic, the LinkCheckerController class
        holds information about the current program configuration settings and
        registers and triggers events upon receiving signalls from either
        LinkCheckerAppWindow or LinkCheckerCore.

        Args:
            config_path (str): An absolute or relative path to the config file.

            resource_cache_path (str): An absolute or relative path to the
                resource cache file.

            result_cache_path (str): An absolute or relative path to the
                result cache fille.

        Attributes:
            config (Config): The current program configuration settings.

            core (LinkCheckerCore): A reference to the core library that can
                handle the link-checking processes.

        Private Attributes:
            _config_manager (ConfigManager): An object that handles the
                reading and writing of config files.
            
            _events (dict[str, Callable]): A series of registered events and
                their associated callbacks.
        """
        self._config_manager = ConfigManager(config_path)
        self.config = self._config_manager.load_config()

        self.core = LinkCheckerCore(
            api_client = APIClient(api_key = self.config.wskey),
            http_client = HTTPClient(headers = {'User-Agent': self.config.user_agent},
                                     ignorelist = self.config.ignorelist,
                                     check_domains_only = False),
            resource_cache = Cache.create(resource_cache_path, True),
            results_cache = Cache.create(result_cache_path, True)
        )

        self._events = {}

    def register_event(self, event: Callable, callback: Callable) -> None:
        """Connect an event name to a callback."""
        self._events[event] = callback

    def _trigger_event(self, event: str, **kwargs) -> None:
        """Evoke a registered event."""
        if event in self._events:
            self._events[event](**kwargs)

    def can_run_app(self) -> bool:
        """Ensure that the necessary config file elements are filled."""
        return self.config.wskey and len(self.config.wskey.strip()) > 0

    def update_config(self, config: dict) -> None:
        """Update the values within the configuration file."""
        errors = self._config_manager.update_config(config)
        self.config = self._config_manager.load_config()
        self._trigger_event('on_config_update')
        self.core.update_clients(self.config.wskey, self.config.ignorelist,
                                 self.core._http_client.check_domains_only)

        return errors
    
    def update_output(self, message: str) -> None:
        """Push a message to the GUI for eventual display."""
        self._trigger_event('on_output_update', message = message)

    def start_link_check(self, run_full_scan: bool) -> None:
        """Asynchronously start the link-checking process in a background thread.
        
        This method spawns a thread that will handle the finding, checking,
        and analysis of resource links. As the process continues, progress
        messages will be sent to the GUI through the `on_output_update` event.
        
        Upon ending the process, the `on_app_stop` event is triggered.
        """

        async def _check() -> None:
            """Helper coroutine that performs the link-checking workflow."""
            await self.core.find_resources(
                on_cache_start_event = lambda m: self._trigger_event('on_output_update', message = m),
                on_cache_event = lambda m: self._trigger_event('on_output_update', message = m),
                on_cache_end_event = lambda m: self._trigger_event('on_output_update', message = m),
                on_cache_failure = lambda e: self._trigger_event('on_app_failure', error = e)
            )
            await self.core.check_resources(
                on_check_start_event = lambda m: self._trigger_event('on_output_update', message = m),
                on_check_event = lambda m: self._trigger_event('on_output_update', message = m),
                on_check_end_event = lambda m: self._trigger_event('on_output_update', message = m)
            )
            await self.core.check_results(
                on_analysis_start_event = lambda m: self._trigger_event('on_output_update', message = m),
                on_analysis_event = lambda m: self._trigger_event('on_output_update', message = m),
                on_analysis_end_event = lambda m: self._trigger_event('on_output_update', message = m),
                failure_threshold = self.config.failure_threshold
            )

        def _run_link_check(run_full_scan: bool) -> None:
            """Helper function to wrap the asynchronous link-checking workflow."""
            if not self.config.wskey or len(self.config.wskey.strip()) == 0:
                error = f'Failed to run the OCLC Broken Link Checker: No WSKey was found. ' + \
                        f'Please add a WSKey to the config file through the Settings tab.'
                self._trigger_event('on_app_failure', error = error)
            else:
                self.core.update_clients(self.config.wskey,
                                         self.config.ignorelist,
                                         run_full_scan)
                asyncio.run(_check())
            self._trigger_event('on_app_stop')
        
        threading.Thread(target = _run_link_check,
                         args = (not run_full_scan,),
                         daemon = True).start()