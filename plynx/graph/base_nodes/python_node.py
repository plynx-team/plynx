from past.builtins import basestring
from plynx.graph.base_nodes import BaseBash


class PythonNode(BaseBash):
    def __init__(self, node=None):
        super(PythonNode, self).__init__(node)

    def run(self, preview=False):
        inputs, cloud_inputs = self._prepare_inputs(preview, pythonize=True)
        parameters = self._prepare_parameters(pythonize=True)
        outputs, cloud_outputs = self._prepare_outputs(preview)
        logs = self._prepare_logs()
        cmd = self._extract_cmd_text()
        cmd_array = [
            self._get_arguments_string('input', inputs),
            self._get_arguments_string('cloud_input', cloud_inputs),
            self._get_arguments_string('output', outputs),
            self._get_arguments_string('cloud_output', cloud_outputs),
            self._get_arguments_string('param', parameters),
            self._get_arguments_string('log', logs),
            "\n",
            "# User code starts there:",
            cmd,
        ]
        cmd_string = '\n'.join(cmd_array)

        if preview:
            return cmd_string

        script_location = self._get_script_fname(extension='.py')
        with open(script_location, 'w') as script_file:
            script_file.write(
                cmd_string
            )

        res = self.exec_script(script_location, command='python')

        self._postprocess_outputs(outputs)
        self._postprocess_logs()

        return res

    def status(self):
        pass

    @staticmethod
    def get_base_name():
        return 'python'

    @classmethod
    def _get_arguments_string(cls, var_name, arguments):
        res = ['{} = {{}}'.format(var_name)]
        for key, value in arguments.items():
            res.append('{var_name}["{key}"] = {value}'.format(
                var_name=var_name,
                key=key,
                value=repr(cls._pythonize(value))
                )
            )
        return '\n'.join(res)

    @staticmethod
    def _pythonize(value):
        if isinstance(value, basestring):
            repr(value)
        return value
