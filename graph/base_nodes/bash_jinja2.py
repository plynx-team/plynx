import jinja2
from . import BaseBash, BaseNode


class BashJinja2(BaseBash, BaseNode):
    def __init__(self, node=None):
        super(self.__class__, self).__init__(node)

    def run(self):
        inputs = BaseBash._prepare_inputs(self.node.inputs)
        parameters = BaseBash._prepare_parameters(self.node.parameters)
        outputs = BaseBash._prepare_outputs(self.node.outputs)
        logs = BaseBash._prepare_logs(self.node.logs)
        cmd = self.node.get_parameter_by_name('cmd').value
        cmd_template = jinja2.Template(cmd)

        print "-"*30
        print "cmd", cmd
        print "-"*30

        script_location = self._get_script_fname()
        with open(script_location, 'w') as script_file:
            script_file.write(
                cmd_template.render(
                    input=inputs,
                    param=parameters,
                    output=outputs,
                    log=logs
                )
            )

        res = self.exec_script(script_location, logs)

        self._postprocess_outputs(outputs)
        self._postprocess_logs(logs)

        return res

    def status(self):
        pass

    def kill(self):
        pass

    @staticmethod
    def get_base_name():
        return 'bash_jinja2'
