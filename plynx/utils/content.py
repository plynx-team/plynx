"""Create default empty Operations"""
# TODO: delete this file? Why do we need it?
# pylint: disable-all
import logging

import plynx.constants
import plynx.db.node
import plynx.utils.plugin_manager
from plynx.utils.db_connector import get_db_connector

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

    cmd_parameter = next(filter(lambda parameter: parameter.name == "_cmd", node.parameters))
    cmd_parameter.value.value = cmd

    node.inputs.extend(inputs or [])
    node.parameters.extend(parameters or [])
    node.outputs.extend(outputs or [])

    validation_error = executor_manager.kind_to_executor_class[kind](node).validate()
    if validation_error:
        raise Exception("Validation failed")

    node.node_status = plynx.constants.NodeStatus.READY

    node.save(force=True)


def create_default_templates(user):
    create_template(
        user=user,
        kind="basic-bash-jinja2-operation",
        cmd="cat {{inputs[\"in\"] | join(\" \")}} | paste -sd+ | bc >> {{outputs[\"out\"]}}",
        title="Sum of numbers",
        description="sum",
        inputs=[
            plynx.db.node.Input(
                name="in",
                is_array=True,
            ),
        ],
        outputs=[
            plynx.db.node.Output(name="out"),
        ],
    )

    create_template(
        user=user,
        kind="basic-bash-jinja2-operation",
        cmd="seq {{params[\"from\"]}} {{params[\"to\"]}} >> {{outputs[\"out\"]}}",
        title="Numbers A to B",
        description="Print text",
        parameters=[
            plynx.db.node.Parameter(
                name="from",
                parameter_type=plynx.constants.ParameterTypes.INT,
                value="1",
                widget="From",
            ),
            plynx.db.node.Parameter(
                name="to",
                parameter_type=plynx.constants.ParameterTypes.INT,
                value="100",
                widget="To",
            ),
        ],
        outputs=[
            plynx.db.node.Output(name="out"),
        ],
    )


def _is_corrupted_name(name_val) -> bool:
    return isinstance(name_val, dict) or (
        isinstance(name_val, str) and name_val.startswith("{") and name_val.endswith("}")
    )


def _has_corrupted_fields(node_dict: dict) -> bool:
    for item in node_dict.get("inputs", []) + node_dict.get("parameters", []):
        if _is_corrupted_name(item.get("name")):
            return True
    for param in node_dict.get("parameters", []):
        if param.get("name") == "_nodes" and isinstance(param.get("value"), dict):
            for sub_node in param["value"].get("value", []):
                if _has_corrupted_fields(sub_node):
                    return True
    return False


def repair_corrupted_templates():
    collection = get_db_connector()[plynx.constants.Collections.TEMPLATES]
    for doc in collection.find({}):
        if _has_corrupted_fields(doc):
            node = plynx.db.node.Node.from_dict(doc)
            node.save(force=True)
            logging.info(f"Repaired corrupted template `{node.title}` ({node._id})")
