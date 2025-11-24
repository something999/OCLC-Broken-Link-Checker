import atexit
import logging
import tkinter

from app.link_checker_controller import LinkCheckerController
from gui.link_checker_app_window import LinkCheckerAppWindow
from utils import log_utils

log_utils.setup_log()
atexit.register(log_utils.shutdown_log)

_logger = logging.getLogger(__name__)

def main():
    config_path = './config.json'
    resource_path = './caches/resource_cache.csv'
    results_path = './caches/results_cache.csv'

    controller = LinkCheckerController(config_path = config_path,
                                       resource_cache_path = resource_path,
                                       result_cache_path= results_path)
    root = tkinter.Tk()
    app = LinkCheckerAppWindow(root, controller)
    root.mainloop()

if __name__ == '__main__':
    main()