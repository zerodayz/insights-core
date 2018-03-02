#!/usr/bin/env python
from contextlib import contextmanager
from StringIO import StringIO

from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
from ansible.playbook.play import Play
from ansible.vars.manager import VariableManager

from insights.core.context import ExecutionContext
from insights.util.subproc import CalledProcessError


class ResultCallback(CallbackBase):
    """A callback plugin used for performing an action as results come in

    If you want to collect all results into a single object for processing at
    the end of the execution, look into utilizing the ``json`` callback plugin
    or writing your own custom callback plugin
    """
    def v2_runner_on_ok(self, result, **kwargs):
        self.rc = result._result["rc"]
        self.output = result._result["stdout"]

    def v2_runner_on_failed(self, result, **kwargs):
        self.rc = result._result["rc"]
        self.output = result._result["stdout"]

    def generic_handler(self, result, **kwargs):
        self.rc = None
        self.output = "Could not reach host."

    v2_runner_on_skipped = generic_handler
    v2_runner_on_unreachable = generic_handler


class AnsibleContext(ExecutionContext):
    def __init__(self, inventory, loader, options, passwords, host):
        super(AnsibleContext, self).__init__()
        self.inventory = inventory
        self.loader = loader
        self.variable_manager = VariableManager(loader=loader, inventory=inventory)
        self.options = options
        self.passwords = passwords
        self.cb = ResultCallback()
        self.host = host
        self.reset_callback()

    def reset_callback(self):
        self.cb.rc = None
        self.cb.output = ""

    @contextmanager
    def get_tqm(self):
        tqm = None
        try:
            tqm = TaskQueueManager(
                          inventory=self.inventory,
                          variable_manager=self.variable_manager,
                          loader=self.loader,
                          options=self.options,
                          passwords=self.passwords,
                          stdout_callback=self.cb,
                  )
            yield tqm
        finally:
            if tqm is not None:
                tqm.cleanup()

    def check_output(self, cmd, timeout=None, keep_rc=False, shell=False):
        play_source = {
            "name": "Insights Collection",
            "hosts": self.host,
            "gather_facts": "no",
            "tasks": []
        }
        task = {
            "action": {
                "module": "raw",
                "args": cmd,
            }
        }

        if shell:
            task["action"]["executable"] = "/bin/bash"

        play_source["tasks"].append(task)

        with self.get_tqm() as tqm:
            play = Play().load(play_source, variable_manager=self.variable_manager, loader=self.loader)
            tqm.run(play)
            rc = int(self.cb.rc) if self.cb.rc is not None else None
            output = self.cb.output
            if keep_rc:
                result = rc, output
            else:
                if rc != 0:
                    raise CalledProcessError(rc, cmd, output)
                result = self.cb.output
            self.reset_callback()
            return result

    @contextmanager
    def read_file(self, path):
        cmd = "cat " + path
        output = self.check_output(cmd)
        yield StringIO(output)
