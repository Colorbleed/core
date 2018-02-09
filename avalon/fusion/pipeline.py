import sys
import contextlib
import importlib
import logging
from pyblish import api as pyblish


class CompLogHandler(logging.Handler):
    def emit(self, record):
        entry = self.format(record)
        comp = get_current_comp()
        if comp:
            comp.Print(entry)


def ls():
    """List containers from active Maya scene

    This is the host-equivalent of api.ls(), but instead of listing
    assets on disk, it lists assets already loaded in Maya; once loaded
    they are called 'containers'

    """

    comp = get_current_comp()
    tools = comp.GetToolList(False).values()
    for tool in tools:
        if tool.ID in ["Loader"]:
            from .pipeline import parse_container
            container = parse_container(tool)
            yield container


def install(config):
    """Install Fusion-specific functionality of avalon-core.

    This function is called automatically on calling `api.install(fusion)`.

    """

    # TODO: Register Fusion callbacks
    # TODO: Set project
    # TODO: Install Fusion menu (this is done with config .fu script actually)

    pyblish.register_host("fusion")

    # Remove all handlers associated with the root logger object, because
    # that one sometimes logs as "warnings" incorrectly.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Attach default logging handler that prints to active comp
    logger = logging.getLogger()
    formatter = logging.Formatter(fmt="%(message)s\n")
    handler = CompLogHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    # Trigger install on the config's "fusion" package
    try:
        config = importlib.import_module(config.__name__ + ".fusion")
    except ImportError:
        pass
    else:
        if hasattr(config, "install"):
            config.install()


def imprint_container(tool,
                      name,
                      namespace,
                      context,
                      loader=None):
    """Imprint a Loader with metadata

    Containerisation enables a tracking of version, author and origin
    for loaded assets.

    Arguments:
        tool (object): The node in Fusion to imprint as container, usually a
            Loader.
        name (str): Name of resulting assembly
        namespace (str): Namespace under which to host container
        context (dict): Asset information
        loader (str, optional): Name of loader used to produce this container.

    Returns:
        None

    """

    data = [
        ("schema", "avalon-core:container-2.0"),
        ("id", "pyblish.avalon.container"),
        ("name", str(name)),
        ("namespace", str(namespace)),
        ("loader", str(loader)),
        ("representation", str(context["representation"]["_id"])),
    ]

    for key, value in data:
        tool.SetData("avalon.{}".format(key), value)


def parse_container(tool):
    """Returns imprinted container data of a tool

    This reads the imprinted data from `imprint_container`.

    """
    container = {}
    for key in ['schema', 'id', 'name', 'namespace',
                'loader', 'representation']:
        value = tool.GetData('avalon.{}'.format(key))
        container[key] = value

    # Store the tool's name
    container["objectName"] = tool.Name

    # Store reference to the tool object
    container["_tool"] = tool

    return container


def get_current_comp():
    """Hack to get current comp in this session"""
    fusion = getattr(sys.modules["__main__"], "fusion", None)
    return fusion.CurrentComp if fusion else None


@contextlib.contextmanager
def comp_lock_and_undo_chunk(comp, undo_queue_name="Script CMD"):
    """Lock comp and open an undo chunk during the context"""
    try:
        comp.Lock()
        comp.StartUndo(undo_queue_name)
        yield
    finally:
        comp.Unlock()
        comp.EndUndo()