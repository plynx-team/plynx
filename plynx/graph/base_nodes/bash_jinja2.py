import jinja2
from plynx.graph.base_nodes import BaseBash


class BashJinja2(BaseBash):
    def __init__(self, node=None):
        super(BashJinja2, self).__init__(node)

    def run(self, preview=False):
        inputs = self._prepare_inputs(preview)
        parameters = self._prepare_parameters()
        outputs = self._prepare_outputs(preview)
        logs = self._prepare_logs()
        cmd = self.node.get_parameter_by_name('cmd').value
        cmd_template = jinja2.Template(cmd)
        cmd_string = cmd_template.render(
            input=inputs,
            param=parameters,
            output=outputs,
            log=logs
        )
        if preview:
            return cmd_string

        script_location = self._get_script_fname()
        with open(script_location, 'w') as script_file:
            script_file.write(
                cmd_string
            )

        res = self.exec_script(script_location, logs)

        self._postprocess_outputs(outputs)
        self._postprocess_logs(logs)

        return res

    def status(self):
        pass

    def kill(self):
        return self.kill_process()

    @staticmethod
    def get_base_name():
        return 'bash_jinja2'
