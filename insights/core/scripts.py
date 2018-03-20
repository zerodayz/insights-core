import imp
import json
import logging
import os
import shlex
import sys
from insights import dr, util
from insights.core.plugins import make_rule_type
from subprocess import Popen, PIPE
from tempfile import mkdtemp, NamedTemporaryFile


class Script(object):
    """
    Holds the script contents and metadata needed to integrate with insights.
    Also executes the script with an environment set up for the dependencies.
    """

    def __init__(self, path, data, requires, optional, interpreter):
        self.path = path
        self.data = data
        self.requires = requires
        self.optional = optional
        self.interpreter = interpreter

        self.args = shlex.split(interpreter)
        self.name, _, _ = path.replace("/", ".").rpartition(".")
        self.log = logging.getLogger(self.name)

    def _run(self, env):
        """
        Runs the script in the given environment. stdout is returned, and stderr
        is written to the logger.
        """
        try:
            proc = Popen(self.args, stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True, env=env)
            out, err = proc.communicate(self.data)
            if err:
                for e in err.splitlines():
                    self.log.warn(e)
            return out
        except Exception as ex:
            self.log.exception(ex)

    def run(self, broker):
        """
        Creates an environment based on dependencies and executes the script
        within it. Responsible for setting up file locations when necessary
        and constructing the environment that exposes them to the script.
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
            out = self._run(env)
            if out:
                return out
        finally:
            for f in to_remove:
                util.fs.remove(f)


def parse_args(data):
    """
    Parse the arguments for requires or optional

    Args:
        data (unicode): the string after "# requires:" or "# optional:" comment

    Returns:
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
    lines = lines[1:]

    is_rule = False
    requires = []
    optional = []

    keywords = ("# requires", "# optional", "# type")

    for line in lines:
        line = line.strip()
        if not line:
            continue
        elif line.startswith(keywords):
            keyword, args = [l.strip() for l in line.split(":")]
            if not is_rule and "type" in keyword and args == "rule":
                is_rule = True
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
        return Script(path, data, requires, optional, interpreter)


class ScriptType(dr.TypeSet):
    script_type = make_rule_type(use_broker_executor=True)
    """
    A rule type for scripts. Generated decorators take the broker as the only
    argument.
    """


def load(path, data):
    """
    Creates a module and component that integrates insights with an arbitrary
    script so it can participate as a rule. The module name is based on the
    dirname of path. The component's name is based on the basename of path with
    the extention stripped. Scripts should write rule repsonse JSON to stdout.

    Args:
        path (str): path to the script file
        data (unicode): the content of the script file

    Returns:
        the newly created module containing the insights component for the
        script.
    """
    script = parse(path, data)
    if not script:
        return

    default_module = "insights_scripts"
    mod_name = os.path.dirname(path).replace("/", ".") or default_module
    comp_name = os.path.basename(path).split(".")[0]

    if mod_name not in sys.modules:
        sys.modules[mod_name] = imp.new_module(mod_name)

    mod = sys.modules[mod_name]

    def driver(broker):
        raw_result = script.run(broker)
        result = {}
        if raw_result:
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

    dec = ScriptType.script_type(*script.requires, optional=script.optional)
    driver = dec(driver)
    setattr(mod, comp_name, driver)

    # required in case we're in the default insights_scripts module
    script.log = logging.getLogger(dr.get_name(driver))
    return mod
