import plynx.constants
import plynx.db.node
import plynx.utils.plugin_manager

workflow_manager = plynx.utils.plugin_manager.get_workflow_manager()
executor_manager = plynx.utils.plugin_manager.get_executor_manager()


def create_template(user, kind, cmd, title, description, inputs=None, parameters=None, outputs=None):
    node = executor_manager.kind_to_executor_class[kind].get_default_node(
        is_workflow=kind in workflow_manager.kind_to_workflow_dict
    )
    node.author = user
    node.title = title
    node.description = description

    cmd_parameter = next(filter(lambda parameter: parameter.name == '_cmd', node.parameters))
    cmd_parameter.value = cmd

    node.inputs.extend(inputs or [])
    node.parameters.extend(parameters or [])
    node.outputs.extend(outputs or [])

    import logging
    from plynx.utils.common import JSONEncoder
    logging.info(JSONEncoder().encode(node.to_dict()))


def create_default_templates(user):
    create_template(
        user=user,
        kind='basic-bash-jinja2-operation',
        cmd='seq {{params["from"]}} {{params["to"]}} >> {{outputs["out"]}}',
        title='Numbers A to B',
        description='Print text',
        parameters=[
            plynx.db.node.Parameter({
                'name': 'from',
                'type': plynx.constants.ParameterTypes.INT,
                'value': '1',
                'widget': 'From',
            }),
            plynx.db.node.Parameter({
                'name': 'to',
                'type': plynx.constants.ParameterTypes.INT,
                'value': '100',
                'widget': 'To',
            }),
        ],
        outputs=[
            plynx.db.node.Output({
                'name': 'out',
            }),
        ],
    )

    create_template(
        user=user,
        kind='basic-bash-jinja2-operation',
        cmd='cat {{inputs["in"]}} >> {{outputs["out"]}}',
        title='Sum of numbers',
        description='sum',
        inputs=[
            plynx.db.node.Input({
                'name': 'in',
                'is_array': True,
            }),
        ],
        outputs=[
            plynx.db.node.Output({
                'name': 'out',
            }),
        ],
    )
