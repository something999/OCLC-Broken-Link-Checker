"""
GUI logic for a windowed application.

This module defines and manages the widgets that make up the application's
graphical user interface. It provides helper functions for constructing common
GUI elements and connecting those elements to a backend controller.

The module is meant to be used with LinkCheckerController and LinkCheckerCore.
"""
import logging
import tkinter
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from typing import Any, Callable, Literal

from app.link_checker_controller import LinkCheckerController

_logger = logging.getLogger(__name__)

class LinkCheckerAppWindow:

    def __init__(self, root: tkinter.Tk, controller: LinkCheckerController) -> None:
        """Initialize and configure the display of the application.
        
        A LinkCheckerAppWindow provides a graphical interface for running the
        backend link-checking processes and displaying the results of those
        processes.
        
        Args:
            root (tkinter.Tk): The main Tkinter window hosting the GUI components.
            controller (LinkCheckerController): The controller coordinating
                logic between the GUI and backend.
        
        Private Attributes:
            _root (tkinter.Tk): A reference to the application window.
                Menu elements should be attached to this window.

            _controller (LinkCheckerController): A reference to the logic
                coordinator. Interactive elements should call backend
                processes through this controller.

            _style (ttk.Style): A reference to a tkinter.Style object that
                can define and change the appearance of the application window.

            _schema (dict[str, dict[str, dict[str, Any]]]): A nested series of
                objects that contain metadata about repeated GUI elements
                (i.e. buttons and text input fields).

            _menu (ttk.Notebook): A tab group container for organizing
                menu tab elements.

            _scans (dict[str, ttk.Button] | None): A series of button used to
                start the program. These buttons are initialized in `_setup_home`.

            _output (ScrolledText | None): A text area for displaying program
                outputs. This is initialized in `_setup_home`.

            _output_count (int): The total number of lines printed to the
                output text area.

            _fields (dict[str, ttk.Widget] | dict[str, None]): A series of
                input field widgets used to change and display the values of
                a config file. These fields are initialized in `_setup_settings`.
        """
        self._root = root
        self._root.title("OCLC Broken Link Checker")
        self._root.wm_minsize(width = 800, height = 600)
        self._controller = controller

        self._style = self._setup_style()
        self._menu = self._add_tab_group()
        self._schema = self._get_schema()

        self._scans = dict()
        self._output = None
        self._output_count = 0
        self._fields = dict()

        self._setup_home()
        self._setup_settings()
        
        _logger.debug('Opened Link Checker App Window.')

        self._register_events()

    #######################
    # GUI Schema
    #######################
    def _get_schema(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Defines a metadata schema for common GUI elements.

        This helper function provides a schema representing structured 
        information for buttons and input fields, making it easier
        to generate and manage GUI components programmatically.

        Each button and field is grouped under a parent tab and GUI category
        (i.e. 'home buttons' refer to buttons that appear under the
        application's Home tab).

        This schema is meant to be used in conjunction with GUI helper functions
        such as _add_button and _add_singleline field.
        """
        return {
            'home_buttons':
            {
                'home_button_quick_scan':
                {
                    'label': 'Quick Scan',
                    'description': 'Verify resource access by testing domains.\n(e.g., "example.com")',
                    'height': 1,
                    'width': 20,
                    'align': 'top',
                    'command': lambda: self.start_app(False)
                },
                'home_button_full_scan':
                {
                    'label': 'Full Scan',
                    'description': 'Verify resource access by testing each link.\n(e.g., "example.com/a", "example.com/b")',
                    'height': 1,
                    'width': 20,
                    'align': 'top',
                    'command': lambda: self.start_app(True)
                }
            },
            'settings_fields': 
            {
                # Input fields are registered under their associated
                # config file fieldname to make it easier to programmatically
                # reference and populate the input fields.
                'wskey':
                {
                    'type': 'single',
                    'label': 'WSKey (Required)',
                    'description': 'An API key registered with the OCC Knowledge Base API service.',
                    'width': 50,
                },
                'user_agent':
                {
                    'type': 'single',
                    'label': 'User-Agent',
                    'description': 'A string that identifies this computer to other web servers.',
                    'width': 50,
                },
                'failure_threshold':
                {
                    'type': 'single',
                    'label': 'Link Failure Threshold (Required)',
                    'description': 'A number between 0.0 and 1.0 representing the max percentage of broken links allowed within a collection.',
                    'width': 50
                },
                # Multi-line fields have a configurable height parameter.
                'ignorelist':
                {
                    'type': 'multi',
                    'label': 'Ignored Domains',
                    'description': 'A list of domains to ignore during the link-checking process (separated by comma).',
                    'height': 5,
                    'width': 50,
                },
            },
            'settings_buttons': 
            {
                'settings_button_save':
                {
                    'label': 'Save Config',
                    'height': 1,
                    'width': 20,
                    'align': 'top',
                    'command': lambda: self.save_settings()
                }
            }
        }

    #######################
    # GUI Set Up Functions
    #######################
    def _setup_style(self) -> None:
        """Set the visual theme of the GUI elements.

        This helper function selects and returns one of Tkinter's built-in
        visual themes to define the appearance of the application window and
        its widgets.

        For a full list of themes, see https://tkdocs.com/tutorial/styles.html
        """
        style = ttk.Style()
        style.theme_use('vista')
        return style
    
    def _setup_home(self) -> None:
        """Initialize the application Home tab.
        
        This helper function creates the following elements:
            - A 'Run' button that allows the user to run the application
                by starting a backend process.
            - A scrollable, read-only text area that allows
                the user to see program outputs.
        """
        def _get_scan_buttons(group: ttk.Frame) -> None:
            """Generate scan buttons based on schema definitions.
            
            This helper function uses the styling settings defined in 
            self._add_button and the metadata defined in 
            self._schema['settings_fields'] to create and configure the
            scan buttons.
            """
            for button, button_schema in self._schema['home_buttons'].items():
                self._add_text(group,
                               label = button_schema['description'],
                               align = 'top',
                               anchor = 'w',
                               fill_mode = 'x')
                temp_button = self._add_button(group,
                                               label = button_schema['label'],
                                               height = button_schema['height'],
                                               width = button_schema['width'],
                                               align = button_schema['align'],
                                               command = button_schema['command'])
                self._scans[button] = temp_button

        home_tab = self._add_nonscrollable_tab(self._menu, 'Home')
        home_tab_scan_group = self._add_labelled_group(home_tab,
                                                       label = 'Scan Options',
                                                       align = 'left',
                                                       fill_mode = 'y')

        _get_scan_buttons(home_tab_scan_group)
        # Cache widgets so we can change their active states later.
        self._output = self._add_textbox(home_tab,
                                         height = 35,
                                         width = 40,
                                         align = 'left')
    
    def _setup_settings(self) -> None:
        """Initialize the application Settings tab.
        
        This helper function creates the following elements:
            - A series of interactable text fields populated by values stored
                in a config file.
            - A series of dividers separating the text fields.
            - A 'Save Config' button that allows the user to modify the actual
                values stored within the config file.
        """
        def _add_basic_settings(group: ttk.Frame) -> None:
            """Add input fields for essential settings to the Settings tab."""
            settings_tab_input_group_basic = self._add_labelled_group(group, 
                                                                      label = 'Basic Settings',
                                                                      align = 'top',
                                                                      fill_mode = 'both')
            _get_settings_field(settings_tab_input_group_basic, ['wskey', 'failure_threshold'])
        
        def _add_advanced_settings(group: ttk.Frame) -> None:
            """Add input fields for optional settings to the Settings tab."""
            settings_tab_input_group_advan = self._add_labelled_group(group,
                                                                      label = 'Advanced Settings',
                                                                      align = 'top',
                                                                      fill_mode = 'both')
            _get_settings_field(settings_tab_input_group_advan, ['user_agent', 'ignorelist'])
        
        def _add_save_button(group: ttk.Frame) -> None:
            """Add a 'Save Config' button to the Settings Tab"""
            button_schema = self._schema['settings_buttons']['settings_button_save']
            self._add_button(group,
                             label = button_schema['label'],
                             height = button_schema['height'],
                             width = button_schema['width'],
                             align = button_schema['align'],
                             command = button_schema['command'])
            
        def _get_settings_field(group: ttk.Frame, fields: list[str]) -> None:
            """Generate input fields based on schema definitions.

            This helper function uses the styling settings defined in 
            _add_singleline_field and _add_multiline_field and the metadata
            defined in self._schema['settings_fields'] to create and configure
            the input fields.
            """
            for field in fields:
                if field not in self._schema['settings_fields']:
                    _logger.error(f'Failed to initialize input field for '
                                  f'setting {field} - schema was undefined.')
                input_schema = self._schema['settings_fields'][field]
                if input_schema['type'] == 'single':
                    temp_field = self._add_singleline_field(group,
                                                            label = input_schema['label'],
                                                            description = input_schema['description'],
                                                            width = input_schema['width'])
                else:
                    temp_field = self._add_multiline_field(group,
                                                           label = input_schema['label'],
                                                           description = input_schema['description'],
                                                           width = input_schema['width'],
                                                           height = input_schema['height'])
                # Cache this field so we can access the values later
                self._fields[field] = temp_field

        settings_tab = self._add_scrollable_tab(self._menu, 'Settings')
        settings_tab_input_group = self._add_nonlabelled_group(settings_tab,
                                                               align = 'top',
                                                               fill_mode = 'both')
        settings_tab_button_group = self._add_nonlabelled_group(settings_tab, 
                                                                align = 'top',
                                                                fill_mode = 'both')
        _add_basic_settings(settings_tab_input_group)
        _add_advanced_settings(settings_tab_input_group)
        _add_save_button(settings_tab_button_group)

        if len(self._fields) > 0:
            self.fill_settings()

    def _register_events(self) -> None:
        """Register controller events with their corresponding GUI handlers.

        This helper function links events emitted by self._controller to 
        methods in the LinkCheckerApplicationWindow class.
        When the controller triggers an event, the associated GUI function
        is called ane executed.
        """
        self._controller.register_event('on_app_stop', self.stop_app)
        self._controller.register_event('on_app_failure', self.log_error)
        self._controller.register_event('on_config_update', self.fill_settings)
        self._controller.register_event('on_output_update', self.log_message)
        
    ###############################
    # GUI Communication Functions
    ###############################
    def start_app(self, run_full_scan: bool) -> None:
        """Start the link-checking process and disable the 'Scan' buttons."""
        for button in self._scans.values():
            button.configure(state = 'disabled')
        self._controller.start_link_check(run_full_scan)
    
    def stop_app(self) -> None:
        """Re-enable the 'Run' button to allow a new link-checking process"""
        for button in self._scans.values():
            button.configure(state = 'normal')
    
    def log_error(self, error: str) -> None:
        """Display an error in a separate message window."""
        messagebox.showerror('Failure', error)

    def log_success(self, success: str) -> None:
        """Display a success message in a separate message window."""
        messagebox.showinfo('Success', success)

    def log_message(self, message: str) -> None:
        """Display backend outputs to the display box under the Home tab."""
        self._output.configure(state = 'normal')
        if self._output_count > 1000:
            self._output.delete('1.0', '2.0')
        self._output.insert(tkinter.END, message + '\n')
        self._output_count += 1
        self._output.configure(state = 'disabled')
        self._output.yview(tkinter.END)

    def fill_settings(self) -> None:
        """Populate Settings fields with the associated config file values."""
        config = self._controller.config

        # In the config file, the ignorelist is a list of strings.
        # Displaying the ignorelist would cause the square brackets to appear
        # in the multi-line input field, potentially confusing the user.
        config.ignorelist = ', '.join(config.ignorelist)

        for k, v in self._fields.items():
            # For the population of singleline-fields.
            if isinstance(v, tkinter.Entry):
                v.delete(0, tkinter.END)
                v.insert(0, getattr(config, k, ''))
            # For the population of multiline fields.
            else:
                v.delete('1.0', tkinter.END)
                v.insert('1.0', getattr(config, k, ''))
    
    def save_settings(self) -> None:
        """Save the current input field values into the config fille.

        This function collects the values from all of the input fields and
        passes them to the controller; the controller then attempts to save
        these values into an external file.

        The function will disaply a message box indicating whether the save
        operation was successful.
        """
        inputs = {k: (v.get('1.0', 'end').strip() if isinstance(v, tkinter.Text)
                      else v.get().strip()) for k, v in self._fields.items()}
        
        # `update_config` will return an error string for display within the
        # failure message window. An empty string indicates success.
        errors = self._controller.update_config(inputs)

        if errors:
            self.log_error(errors)
        else:
            self.log_success('Config settings successfully saved.')
        return

    #######################
    # GUI Helper Functions
    #######################
    def _add_nonlabelled_group(self, 
                               group: ttk.Frame,
                               align: Literal['left', 'right', 'top', 'bottom'],
                               fill_mode: Literal['none', 'x', 'y', 'both']) -> ttk.Frame:
        """Creates and configures a container to store non-labelled menu elements."""
        temp_group = ttk.Frame(group)
        temp_group.pack(side = align,
                        fill = fill_mode,
                        expand = True,
                        padx = 10,
                        pady = 10)
        return temp_group
    
    def _add_labelled_group(self,
                            group: ttk.Frame,
                            label: str,
                            align: Literal['left', 'right', 'top', 'bottom'],
                            fill_mode: Literal['none', 'x', 'y', 'both']) -> ttk.Frame:
        """Creates and configures a container to store labelled menu elements."""
        temp_group = ttk.LabelFrame(group,
                                   text = label)
        temp_group.pack(side = align,
                        fill = fill_mode,
                        padx = 10,
                        pady = 10)
        return temp_group

    def _add_tab_group(self) -> ttk.Notebook:
        """Creates and configures a container to store menu tabs."""
        temp_group = ttk.Notebook(self._root)
        temp_group.pack(fill = 'both', expand = True)
        return temp_group
    
    def _add_nonscrollable_tab(self, group: ttk.Notebook, label: str) -> ttk.Frame:
        """Creates and configures a non-scrollable tab."""
        temp_tab = ttk.Frame(group)
        group.add(temp_tab, text = label)
        return temp_tab
    
    def _add_scrollable_tab(self, group: ttk.Notebook, label: str) -> ttk.Frame:
        """Creates and configures a scrollable tab."""
        temp_tab = ttk.Frame(group)
        group.add(temp_tab, text = label)

        canvas = tkinter.Canvas(temp_tab)
        canvas.bind(
            '<Configure>',
             lambda e: canvas.itemconfig('frame', width = e.width)
        )
        scrollbar = ttk.Scrollbar(temp_tab, orient = 'vertical', command = canvas.yview)
        scrollbar_frame = ttk.Frame(canvas)
        scrollbar_frame.bind(
            '<Configure>', 
            lambda e: canvas.configure(scrollregion = canvas.bbox('all'))
        )
        canvas.create_window((0, 0), window = scrollbar_frame, anchor = 'nw', tags = 'frame')
        canvas.configure(yscrollcommand = scrollbar.set)
        canvas.pack(side = 'left', fill = 'both', expand = True)
        scrollbar.pack(side = 'right', fill = 'y')

        return scrollbar_frame
    
    def _add_button(self,
                    group: tkinter.Widget, 
                    label: str,
                    height: int, 
                    width: int,
                    align: Literal['left', 'right', 'top', 'bottom'],
                    command: Callable) -> tkinter.Button:
        """Creates and configures an interactable tab."""
        temp_button = tkinter.Button(group,
                                     text = label,
                                     height = height,
                                     width = width,
                                     command = command)
        temp_button.pack(side = align, 
                         padx = 10, 
                         pady = 10)
        return temp_button

    def _add_text(self,
                     group: tkinter.Widget,
                     label: str,
                     align: Literal['left', 'right', 'top', 'bottom'],
                     anchor: Literal['n', 'ne', 'e', 'center', 'se', 's', 'sw', 'w', 'nw'],
                     fill_mode: Literal['none', 'x', 'y', 'both']) -> tkinter.Label:
        """Creates and configures a text object."""
        temp_text = tkinter.Label(group,
                                  text = label)
        temp_text.pack(side = align, 
                       anchor = anchor,
                       fill = fill_mode)
        return temp_text

    def _add_singleline_field(self,
                              group: tkinter.Widget,
                              label: str, 
                              description: str,
                              width: int) -> tkinter.Entry:
        """Creates and configures an interactable text input field."""
        self._add_text(group,
                       label = label,
                       align = 'top',
                       anchor = 'w',
                       fill_mode = 'x')
        self._add_text(group,
                       label = description,
                       align = 'top',
                       anchor = 'w',
                       fill_mode = 'x')
        temp_input = tkinter.Entry(group, width = width)
        temp_input.pack(anchor = 'w', fill = 'x', padx = 10, pady = 10)
        return temp_input
    
    def _add_multiline_field(self,
                             group: tkinter.Widget,
                             label: str,
                             description: str,
                             width: int,
                             height: int) -> ScrolledText:
        """Creates and configures an interactable, scrollable text input field."""
        self._add_text(group,
                       label = label,
                       align = 'top',
                       anchor = 'w',
                       fill_mode = 'x')
        self._add_text(group,
                       label = description,
                       align = 'top',
                       anchor = 'w',
                       fill_mode = 'x')
        temp_input = ScrolledText(group,
                                  height = height,
                                  width = width,
                                  wrap = 'word',
                                  state = 'normal')
        temp_input.pack(anchor = 'w', fill = 'x', padx = 10, pady = 10)
        return temp_input

    def _add_textbox(self,
                     group: tkinter.Widget,
                     height: int,
                     width: int,
                     align: Literal['left', 'right', 'top', 'bottom']) -> ScrolledText:
        """Creates and configures a non-interactable, scrollable text field."""
        temp_textbox = ScrolledText(group,
                                    height = height,
                                    width = width,
                                    wrap = 'word',
                                    state = 'disabled')
        temp_textbox.pack(side = align, pady = 10, fill = 'both', expand = True)
        return temp_textbox 