"""Create default empty Operations"""
# TODO: delete this file? Why do we need it?
# pylint: disable-all
import plynx.constants
import plynx.db.node
import plynx.utils.plugin_manager

workflow_manager = plynx.utils.plugin_manager.get_workflow_manager()
executor_manager = plynx.utils.plugin_manager.get_executor_manager()


def create_template(user, kind, cmd, title, description, inputs=None, parameters=None, outputs=None):
    node = executor_manager.kind_to_executor_class[kind].get_default_node(
        is_workflow=kind in workflow_manager.kind_to_workflow_dict
    )
    node.author = user._id
    node.title = title
    node.description = description
    node.kind = kind

    cmd_parameter = next(filter(lambda parameter: parameter.name == '_cmd', node.parameters))
    cmd_parameter.value.value = cmd

    node.inputs.extend(inputs or [])
    node.parameters.extend(parameters or [])
    node.outputs.extend(outputs or [])

    validation_error = executor_manager.kind_to_executor_class[kind](node).validate()
    if validation_error:
        raise Exception('Validation failed')

    node.node_status = plynx.constants.NodeStatus.READY

    node.save(force=True)


def create_default_templates(user):
    create_template(
        user=user,
        kind='basic-bash-jinja2-operation',
        cmd='cat {{inputs["in"] | join(" ")}} | paste -sd+ | bc >> {{outputs["out"]}}',
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
