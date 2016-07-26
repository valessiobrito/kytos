"""Utilities"""

import logging

from abc import abstractmethod, ABCMeta
from threading import Thread

from kyco.core.events import KycoEvent
from kyco.core.exceptions import KycoNAppMissingInitArgument

log = logging.getLogger('kytos[A]')

APP_MSG = "[App %s] %s | ID: %02d | R: %02d | P: %02d | F: %s"


def start_logger():
    """Starts the loggers, both the Kyco and the KycoNApp"""
    general_formatter = logging.Formatter('%(asctime)s - %(levelname)s '
                                          '[%(name)s] %(message)s')
    app_formatter = logging.Formatter('%(asctime)s - %(levelname)s '
                                      '[%(name)s] %(message)s')

    controller_console_handler = logging.StreamHandler()
    controller_console_handler.setLevel(logging.DEBUG)
    controller_console_handler.setFormatter(general_formatter)

    app_console_handler = logging.StreamHandler()
    app_console_handler.setLevel(logging.DEBUG)
    app_console_handler.setFormatter(app_formatter)

    controller_log = logging.getLogger('Kyco')
    controller_log.setLevel(logging.DEBUG)
    controller_log.addHandler(controller_console_handler)

    app_log = logging.getLogger('KycoNApp')
    app_log.setLevel(logging.DEBUG)
    app_log.addHandler(app_console_handler)

    return controller_log


class ListenTo(object):
    """Decorator for Event Listener methods.

    This decorator should be used on methods, inside an APP, to define which
    type of event the method will handle. With this, we will be able to
    'schedule' the app/method to receive an event when a new event is
    registered on the controller buffers. The decorator also guarantee that
    the method (handler) will be called from inside a new thread, avoiding
    this method to block its caller.

    The decorator will add an attribute to the method called 'events', that
    will be a list of the events that the method will handle.

    The event that will be listened to is always a string, but it can represent
    a regular expression to match against multiple Event Types.

    Example of usage:

    .. code-block:: python3

        class MyAppClass(KycoApp):
            @listen_to('KycoMessageIn')
            def my_handler_of_message_in(self, event):
                # Do stuff here...

            @listen_to('KycoMessageOut')
            def my_handler_of_message_out(self, event):
                # Do stuff here...

            @listen_to('KycoMessage*')
            def my_stats_handler_of_any_message(self, event):
                # Do stuff here...
    """
    def __init__(self, event, *events):
        """Initial setup of handler methods.

        This will be called when the class is created.
        It need to have at least one event type (as string).

        Args:
            event (str): String with the name of a event to be listened to.
            events (str): other events to be listened to.
        """
        self.events = [event]
        self.events.extend(events)

    def __call__(self, handler):
        """Just return the handler method on a thread with the event attribute
        """
        def wrapped_handler(*args):
            """Ensure the handler method runs inside a new thread"""
            thread = Thread(target=handler, args=args)
            thread.start()
        wrapped_handler.events = self.events
        return wrapped_handler


class KycoNApp(Thread, metaclass=ABCMeta):
    """Base class for any KycoNApp to be developed."""

    def __init__(self, **kwargs):
        """Go through all of the instance methods and selects those that have
        the events attribute, then creates a dict containing the event_name
        and the list of methods that are responsible for handling such event.

        At the end, the setUp method is called as a complement of the init
        process.
        """
        Thread.__init__(self,daemon=False)
        self._listeners = {}

        handler_methods = [getattr(self, method_name) for method_name in
                           dir(self) if method_name[0] != '_' and
                           callable(getattr(self, method_name)) and
                           hasattr(getattr(self, method_name), 'events')]

        # Building the listeners dictionary
        for method in handler_methods:
            for event_name in method.events:
                if event_name not in self._listeners:
                    self._listeners[event_name] = []
                self._listeners[event_name].append(method)

        if 'add_to_msg_in_buffer' not in kwargs:
            raise KycoNAppMissingInitArgument('add_to_msg_in_buffer')
        self.add_to_msg_in_buffer = kwargs['add_to_msg_in_buffer']

        if 'add_to_msg_out_buffer' not in kwargs:
            raise KycoNAppMissingInitArgument('add_to_msg_out_buffer')
        self.add_to_msg_out_buffer = kwargs['add_to_msg_out_buffer']

        if 'add_to_app_buffer' not in kwargs:
            raise KycoNAppMissingInitArgument('add_to_app_buffer')
        self.add_to_app_buffer = kwargs['add_to_app_buffer']

        log.info("%s App instantiated", self.name)

    def run(self):
        """This method will call the setup and the execute methos.

        It should not be overriden."""
        log.info("Running %s App", self.name)
        # TODO: If the setup method is blocking, then the execute method will
        #       never be called. Should we execute it inside a new thread?
        self.setup()
        self.execute()

    @ListenTo('KycoShutdownEvent')
    def _shutdown_handler(self, event):
        self.shutdown()

    @abstractmethod
    def setup(self):
        """'Replaces' the 'init' method for the KycoApp subclass.

        The setup method is automatically called by the run method.
        Users shouldn't call this method directly."""
        pass

    @abstractmethod
    def execute(self):
        """Method to be runned once on app 'start' or in a loop.

        The execute method is called by the run method of KycoNApp class.
        Users shouldn't call this method directly."""
        pass

    @abstractmethod
    def shutdown(self):
        """Called before the app is unloaded, before the controller is stopped.

        The user implementation of this method should do the necessary routine
        for the user App and also it is a good moment to break the loop of the
        execute method if it is in a loop.

        This methods is not going to be called directly, it is going to be
        called by the _shutdown_handler method when a KycoShutdownEvent is
        sent."""
        pass


class KycoCoreNApp(KycoNApp):
    """Base class for any KycoCoreNApp to be developed."""
    pass