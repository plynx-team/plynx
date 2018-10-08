from . import BaseBash, BaseNode


class PythonNode(BaseBash, BaseNode):
    def __init__(self, node=None):
        super(self.__class__, self).__init__(node)

    def run(self, preview=False):
        inputs = BaseBash._prepare_inputs(self.node.inputs, preview, pythonize=True)
        parameters = BaseBash._prepare_parameters(self.node.parameters, pythonize=True)
        outputs = BaseBash._prepare_outputs(self.node.outputs, preview)
        logs = BaseBash._prepare_logs(self.node.logs)
        cmd = self.node.get_parameter_by_name('cmd').value
        cmd_array = [
            self._get_arguments_string('input', inputs),
            self._get_arguments_string('output', outputs),
            self._get_arguments_string('param', parameters),
            self._get_arguments_string('log', logs),
            cmd
        ]
        cmd_string = '\n'.join(cmd_array)

        if preview:
            return cmd_string

        script_location = self._get_script_fname(extension='.py')
        with open(script_location, 'w') as script_file:
            script_file.write(
                cmd_string
            )

        res = self.exec_script(script_location, logs, command='python')

        self._postprocess_outputs(outputs)
        self._postprocess_logs(logs)

        return res

    def status(self):
        pass

    def kill(self):
        pass

    @staticmethod
    def get_base_name():
        return 'python'

    @staticmethod
    def _get_arguments_string(var_name, arguments):
        res = ['{} = {{}}'.format(var_name)]
        for key, value in arguments.iteritems():
            res.append('{var_name}["{key}"] = {value}'.format(
                var_name=var_name,
                key=key,
                value=PythonNode._pythonize(value)
                )
            )
        return '\n'.join(res)

    @staticmethod
    def _pythonize(value):
        if isinstance(value, basestring):
            return '"""{}"""'.format(value)
        return value
