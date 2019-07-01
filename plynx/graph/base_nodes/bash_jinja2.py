import jinja2
from plynx.constants import NodeResources
from plynx.graph.base_nodes import BaseBash

HELP_TEMPLATE = '''# Use templates: {}
# For example `{{{{ '{{{{' }}}} param['_timeout'] {{{{ '}}}}' }}}}` or `{{{{ '{{{{' }}}} input['abc'] {{{{ '}}}}' }}}}`

'''


class BashJinja2(BaseBash):
    def __init__(self, node=None):
        super(BashJinja2, self).__init__(node)

    def run(self, preview=False):
        inputs = self._prepare_inputs(preview)
        parameters = self._prepare_parameters()
        outputs = self._prepare_outputs(preview)
        logs = self._prepare_logs()
        if preview:
            help = HELP_TEMPLATE.format(list(inputs.keys()) + list(outputs.keys()) + [NodeResources.PARAM])
        else:
            help = ''
        cmd = '{help}{cmd}'.format(
            help=help,
            cmd=self._extract_cmd_text()
        )
        cmd_template = jinja2.Template(cmd)
        resources = inputs
        resources.update(outputs)
        cmd_string = cmd_template.render(
            param=parameters,
            log=logs,
            **resources
        )
        if preview:
            return cmd_string

        script_location = self._get_script_fname()
        with open(script_location, 'w') as script_file:
            script_file.write(
                cmd_string
            )

        res = self.exec_script(script_location)

        self._postprocess_outputs(outputs[NodeResources.OUTPUT])
        self._postprocess_logs()

        return res

    def status(self):
        pass

    @staticmethod
    def get_base_name():
        return 'bash_jinja2'
