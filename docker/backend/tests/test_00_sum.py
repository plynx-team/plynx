#!/usr/bin/env python
from plynx.constants import NodeRunningStatus
import plynx.db.node
import plynx.utils.file_handler as file_handler
import plynx.plugins.executors.local as local
import plynx.plugins.executors.dag as dag
import plynx.plugins.resources.common as common


SEQ_OUTPUT = 'seq_o'
GREP_INPUT = 'grep_i'
GREP_OUTPUT = 'grep_o'
SUM_INPUT = 'sum_i'
SUM_OUTPUT = 'sum_o'


def create_seq_operation(num):
    node = local.BashJinja2.get_default_node(is_workflow=False)
    node.title = '1 to {}'.format(num)
    node.kind = 'basic-bash-jinja2-operation'
    node.node_running_status = NodeRunningStatus.READY

    node.parameters.append(
        plynx.db.node.Parameter.from_dict({
            'name': 'N',
            'parameter_type': plynx.db.node.ParameterTypes.INT,
            'value': num,
            'widget': 'N',
        })
    )

    node.outputs.append(
        plynx.db.node.Output.from_dict({
            'name': SEQ_OUTPUT,
            'file_type': common.FILE_KIND,
        })
    )

    cmd_param = node.get_parameter_by_name('_cmd', throw=True)
    cmd_param.value.value = 'seq {{{{ params.N }}}} > {{{{ outputs.{0} }}}}\n'.format(SEQ_OUTPUT)

    return node


def create_grep_operation(input_reference, template):
    node = local.BashJinja2.get_default_node(is_workflow=False)
    node.title = 'Template "{}"'.format(template)
    node.kind = 'basic-bash-jinja2-operation'
    node.node_running_status = NodeRunningStatus.READY

    node.inputs.append(
        plynx.db.node.Input.from_dict({
            'name': GREP_INPUT,
            'file_type': common.FILE_KIND,
            'input_references': [input_reference]
        })
    )

    node.parameters.append(
        plynx.db.node.Parameter.from_dict({
            'name': 'template',
            'parameter_type': plynx.db.node.ParameterTypes.STR,
            'value': template,
            'widget': 'Template',
        })
    )

    node.outputs.append(
        plynx.db.node.Output.from_dict({
            'name': GREP_OUTPUT,
            'file_type': common.FILE_KIND,
        })
    )

    cmd_param = node.get_parameter_by_name('_cmd', throw=True)
    cmd_param.value.value = 'cat {{{{ inputs.{0} }}}} | grep {{{{ params.template }}}} > {{{{ outputs.{1} }}}}\n'.format(
        GREP_INPUT,
        GREP_OUTPUT
    )

    return node


def create_sum_operation(input_references):
    node = local.PythonNode.get_default_node(is_workflow=False)
    node.title = 'Sum integers'
    node.kind = 'basic-python-node-operation'
    node.node_running_status = NodeRunningStatus.READY

    node.inputs.append(
        plynx.db.node.Input.from_dict({
            'name': SUM_INPUT,
            'file_type': common.FILE_KIND,
            'is_array': True,
            'input_references': input_references,
        })
    )

    node.outputs.append(
        plynx.db.node.Output.from_dict({
            'name': SUM_OUTPUT,
            'file_type': common.FILE_KIND,
        })
    )

    cmd_param = node.get_parameter_by_name('_cmd', throw=True)
    CMD = """
res = 0
for filename in inputs['{inputs}']:
    with open(filename, 'r') as f:
        for n in f:
            res += int(n)

with open(outputs['{outputs}'], 'w') as f:
    f.write(str(res) + '\\n')

    """.format(
        inputs=SUM_INPUT,
        outputs=SUM_OUTPUT,
    )
    cmd_param.value.value = CMD

    return node


def create_dag_executor(N):
    """
    Create a Dag with the following layout:

                +-- (grep ^0) --+
    (seq 100) --+   ...         +-- (sum)
                +-- (grep ^9) --+

    Args:
        N: int, sequence
    """

    dag_node = dag.DAG.get_default_node(is_workflow=True)
    dag_node.title = 'Test sum DAG'
    dag_node.kind = 'basic-dag-workflow'
    dag_node.node_running_status = 'READY'
    nodes = dag_node.get_parameter_by_name('_nodes', throw=True).value.value

    seq_operation = create_seq_operation(N)
    nodes.append(seq_operation)

    grep_nodes = []
    input_reference = {
        'node_id': seq_operation._id,
        'output_id': SEQ_OUTPUT,
    }
    sum_input_references = []

    for ii in range(1, 10):
        grep_node = create_grep_operation(input_reference, '^{}'.format(ii))
        grep_nodes.append(grep_node)
        sum_input_references.append(
            {
                'node_id': grep_node._id,
                'output_id': GREP_OUTPUT,
            }
        )

    nodes.extend(grep_nodes)

    sum_node = create_sum_operation(sum_input_references)
    nodes.append(sum_node)

    return dag.DAG(dag_node)


def test_dag():
    N = 100
    executor = create_dag_executor(N)

    validation_error = executor.validate()
    assert validation_error is None, validation_error

    executor.run()

    output_ids = executor.node.get_parameter_by_name('_nodes').value.value[-1].get_output_by_name(SUM_OUTPUT).values
    assert len(output_ids) == 1, 'Unexpected number of outputs: `{}`'.format(len(output_ids))

    res = int(file_handler.get_file_stream(output_ids[0]).read())
    res_expected = ((1 + N) * N) // 2
    assert res == res_expected, 'Expected `{}` but got `{}`'.format(res_expected, res)

    print('Test successfully passed with result `{}`'.format(res))


if __name__ == "__main__":
    test_dag()
