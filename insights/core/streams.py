"""
The streams module allows you to develop components that produce data for their
dependents and consume data from their dependencies. Requirements are declared
in the standard way, but the resolution step wires together queues between
components.
"""

import logging
import threading

from six.moves.queue import Queue, Empty

from insights import dr


class Stream(threading.Thread):
    """
    ``Stream`` is the base class for components that want to emit data to
    dependents or consume data from dependencies.
    """

    def __init__(self, *args):
        super(Stream, self).__init__()
        self.observers = []
        self.queue = None
        self.log = logging.getLogger(__name__)

        # wire up our input queue to our dependencies
        for a in args:
            if isinstance(a, Stream):
                if self.queue is None:
                    self.queue = Queue()
                a._add_observer(self)

        # die when the parent dies
        self.daemon = True

    def _add_observer(self, o):
        self.observers.append(o.queue)

    def emit(self, data):
        """ Use emit to send data to all downstream dependencies. """
        for o in self.observers:
            o.put((self.__class__, data))

    def update(self, src, data):
        """
        The update function is called any time a ``Stream`` dependency emits
        data.

        Args:
            src (class): This will be the class of the ``Stream`` that emitted
                the data.
            data: This will be whatever the ``src`` emitted.
        """
        pass

    def run(self):
        """
        The default ``run`` implementation gets data off the queue and passes
        it into ``update``. Override ``run`` if you want to produce data, say
        from an external resource.
        """
        while True:
            try:
                # Just return if we're not listening to anybody.
                if not self.queue:
                    return
                data = self.queue.get(2)
                self.update(*data)
                self.queue.task_done()
            except Empty:
                pass
            except Exception as ex:
                self.log.exception(ex)
                self.queue.task_done()


class stream(dr.ComponentType):
    """
    ``stream`` is the decorator used to signify that a component is a
    ``Stream``. It should only decorate ``Stream`` subclasses. Otherwise, it's
    a component decorator like any other.
    """
    group = "stream"

    def __call__(self, component):
        if not issubclass(component, Stream):
            raise Exception("@stream only valid on Stream subclasses.")
        return super(stream, self).__call__(component)
