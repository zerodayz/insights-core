import imp
import json
import logging
import os
import shlex
import sys
from contextlib import contextmanager
from subprocess import Popen, PIPE
from tempfile import mkdtemp, NamedTemporaryFile

from insights import dr, util
from insights.core.plugins import make_rule_type

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class Script(object):
    """
    Holds the script contents and metadata needed to integrate with insights.
    Also executes the script with an environment set up for the dependencies.
    """

    def __init__(self, name, path, data, requires, optional, interpreter):
        self.name = name
        self.path = path
        self.data = data
        self.requires = requires
        self.optional = optional
        self.interpreter = interpreter

        self.args = shlex.split(interpreter)
        self.full_name, _, _ = path.replace("/", ".").rpartition(".")
        self.log = logging.getLogger(self.full_name)

    @contextmanager
    def create_environment(self, broker):
        """
        Creates an environment based on dependencies and yields it for the
        script to be executed within. Responsible for setting up file locations
        when necessary and constructing the environment that exposes them to
        the script.
        """
        to_remove = []
        env = {}

        def locate(name, provider):
            if not provider:
                env[name] = None
                return

            if isinstance(provider, list):
                d = None
                paths = []
                for p in provider:
                    if os.path.exists(p.path):
                        path = p.path
                    else:
                        if not d:
                            d = mkdtemp()
                            to_remove.append(d)
                        with NamedTemporaryFile(dir=d, delete=False) as f:
                            f.write("\n".join(p.content))
                        path = f.name
                    paths.append(path)
                env[name] = ";".join(paths)
            else:
                if os.path.exists(provider.path):
                    path = provider.path
                else:
                    with NamedTemporaryFile(delete=False) as f:
                        f.write("\n".join(provider.content))
                    to_remove.append(f.name)
                    path = f.name
                env[name] = path

        for req in self.requires:
            if isinstance(req, list):
                for r in req:
                    locate(r.__name__, broker.get(r))
            else:
                locate(req.__name__, broker.get(req))

        for opt in self.optional:
            locate(opt.__name__, broker.get(opt))

        try:
            yield env
        finally:
            for f in to_remove:
                util.fs.remove(f)

    def run(self, broker):
        """
        Runs the script in the given environment. stdout is returned, and
        stderr is written to the logger.
        """
        with self.create_environment(broker) as env:
            try:
                proc = Popen(self.args, stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True, env=env)
                out, err = proc.communicate(self.data)
                if err:
                    for e in err.splitlines():
                        self.log.warn(e)
                return out if out else None
            except Exception as ex:
                self.log.exception(ex)


def parse_args(data):
    """
    Parse the arguments for requires or optional

    Args:
        data (unicode): the string after "# requires:" or "# optional:" comment

    Returns:
        A list of insights components loaded from insights.specs.Specs
    """
    default_comps = "insights.specs.Specs.%s"

    args = [l.strip() for l in data.split(",")]
    results = []

    for a in args:
        component = dr.get_component(default_comps % a)
        if not component:
            raise Exception("Invalid dependency: %s" % a)
        results.append(component)
    return results


def parse(path, data):
    """
    Converts a script into a rule plugin executable by Insights.

    Args:
        path (str): path to the script file
        data (unicode): the content of the script file

    Returns:
        Script object
    """
    lines = data.splitlines()
    if not lines or not lines[0].startswith("#"):
        raise Exception("Invalid script. Missing interpreter line: %s" % path)

    interpreter = lines[0].strip("#! ")

    is_rule = False
    name = None
    requires = []
    optional = []

    keywords = ("# requires:", "# optional:", "# type:", "# name:")

    for line in lines:
        line = line.strip()
        if line.startswith(keywords):
            keyword, args = [l.strip() for l in line.split(":")]
            if not is_rule and "type" in keyword and args == "rule":
                is_rule = True
                continue

            if "name" in keyword:
                name = args
                continue

            args = parse_args(args)
            if "requires" in keyword:
                if len(args) == 1:
                    requires.extend(args)
                else:
                    requires.append(args)
            elif "optional" in keyword:
                optional.extend(args)

    if is_rule:
        return Script(name, path, data, requires, optional, interpreter)


class ScriptType(dr.TypeSet):
    script_type = make_rule_type(use_broker_executor=True)
    """
    A rule type for scripts. Generated decorators take the broker as the only
    argument.
    """


def load(path, data, mod_name=None):
    """
    Creates a module and component that integrates insights with an arbitrary
    script so it can participate as a rule. The module name is based on the
    dirname of path. The component's name is based on the basename of path with
    the extention stripped. Scripts should write rule response JSON to stdout.

    Args:
        path (str): path to the script file
        data (unicode): the content of the script file

    Returns:
        the newly created insights component for the script.
    """
    script = parse(path, data)
    if not script:
        return

    mod_path, _ = os.path.splitext(path)
    mod_name = mod_name or mod_path.replace("/", ".")
    comp_name = script.name or "report"

    if mod_name not in sys.modules:
        mod = imp.new_module(mod_name)
        mod.__file__ = path
        mod.__package__ = None
        sys.modules[mod_name] = mod

    mod = sys.modules[mod_name]

    # this is the rule function that invokes the script and handles its
    # response.
    def driver(broker):
        raw_result = script.run(broker)
        if raw_result:
            result = {}
            try:
                result = json.loads(raw_result)
            except Exception:
                for line in raw_result.splitlines():
                    key, value = line.split(":", 1)
                    result[key.strip()] = value.lstrip()
            result["type"] = "rule"
            return result

    driver.__module__ = mod_name
    driver.__name__ = comp_name
    driver.__qualname__ = comp_name
    driver.__script__ = script

    dec = ScriptType.script_type(*script.requires, optional=script.optional)
    driver = dec(driver)
    setattr(mod, comp_name, driver)

    # required in case we're in the default insights_scripts module
    script.log = logging.getLogger(dr.get_name(driver))
    return mod


class ScriptImporter(object):
    """ Hook into python's import machinery so standard import statements
        can be used for scripts.
    """
    ext = (".py", ".pyc")

    def __init__(self, path):
        self.path = os.path.realpath(path)

        if not os.path.exists(self.path):
            raise ImportError()

        self.files = os.listdir(self.path)

        # we only allow __init__.py
        if any(n.endswith(self.ext) and not n.startswith("__init__")
               for n in self.files):
            raise ImportError()

    def find_module(self, fullname, paths=None):
        """
        Returns a ScriptLoader for script files.
        """
        name = fullname.split(".")[-1]
        for f in self.files:
            if f == name or f.startswith(name + "."):
                name = f
                break
        else:
            raise ImportError()

        filename = os.path.join(self.path, name)
        return ScriptLoader(filename)

    def iter_modules(self, prefix=''):
        """
        Allows this importer to work with other pkgutil functions like
        walk_packages.
        """
        if self.path is None or not os.path.isdir(self.path):
            return

        yielded = {}
        try:
            filenames = os.listdir(self.path)
        except OSError:
            # ignore unreadable directories like import does
            filenames = []
        filenames.sort()  # handle packages before same-named modules

        for fn in filenames:
            modname, _ = os.path.splitext(fn)
            if modname == '__init__' or modname in yielded:
                continue

            path = os.path.join(self.path, fn)
            ispkg = False

            if os.path.isdir(path):
                ispkg = True
                modname = fn

            if modname and '.' not in modname:
                yielded[modname] = 1
                yield prefix + modname, ispkg


class ScriptLoader(object):
    def __init__(self, filename):
        self.filename = filename
        self.source = None

    def is_package(self, fullname):
        return os.path.isdir(self.filename)

    def get_source(self, fullname=None):
        if self.source is None:
            return self._get_source()
        return self.source

    def get_code(self, fullname):
        mod = self.load_module(fullname)
        report = getattr("report", mod)
        return report.func_code

    def _get_source(self):
        try:
            with open(self.filename, "U") as f:
                return f.read()
        except Exception as ex:
            log.exception(ex)
            raise ImportError()

    def get_filename(self, path=None):
        return self.filename

    def load_module(self, fullname):
        try:
            return sys.modules[fullname]
        except KeyError:
            pass

        if self.is_package(fullname):
            mod = sys.modules.setdefault(fullname, imp.new_module(fullname))
            mod.__loader__ = self
            mod.__path__ = [self.filename]
            mod.__package__ = fullname
            return mod

        try:
            mod = load(self.filename, self.get_source(), fullname)
            mod.__loader__ = self
            mod.__file__ = self.filename
            mod.__package__ = fullname.rpartition(".")[0]
            return mod
        except Exception as ex:
            log.exception(ex)
            raise ImportError()


sys.path_hooks.append(ScriptImporter)
