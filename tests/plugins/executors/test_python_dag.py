"""Test the node utils."""
from plynx.db.node import Input, Output
from plynx.plugins.executors.python.dag import DAG
from plynx.plugins.executors.python.local import PythonNode


def create_add_1_operation():
    """
    Operation that sums the input and adds 1
    """
    node = PythonNode.get_default_node(is_workflow=False)
    node.title = "Node"
    node.kind = "python-code-operation"

    node.inputs = [
        Input(name="input_a", file_type="int", primitive_override=0),
        Input(name="input_b", file_type="int", primitive_override=0),
    ]
    node.outputs = [
        Output(name="out", file_type="int"),
    ]
    node.get_parameter_by_name("_cmd").value.value = (
        "def operation(input_a, input_b):\n"
        "    return {'out': input_a + input_b + 1}\n"
    )

    return node


def create_graph_flow():
    """Create a graph flow.
    Structure:
        (default==-1) +-> A-ADD_1[out==0] +-> B-ADD_1[out==1] +-> D-ADD_1[out==3]
                                          |                   |
                                          +-> C-ADD_1[out==1] +

    """
    dag_node = DAG.get_default_node(is_workflow=True)
    dag_node.title = "Graph"
    dag_node.kind = 'python-workflow'
    nodes = dag_node.get_sub_nodes()

    add_a = create_add_1_operation()
    add_a.get_input_by_name("input_a").primitive_override = -1
    add_a.title = "A"
    add_a.description = "0"

    add_b = create_add_1_operation()
    add_b.get_input_by_name("input_a").add_input_reference(add_a._id, "out")
    add_b.title = "B"
    add_b.description = "1"

    add_c = create_add_1_operation()
    add_c.get_input_by_name("input_a").add_input_reference(add_a._id, "out")
    add_c.title = "C"
    add_c.description = "1"

    add_d = create_add_1_operation()
    add_d.get_input_by_name("input_a").add_input_reference(add_b._id, "out")
    add_d.get_input_by_name("input_b").add_input_reference(add_c._id, "out")
    add_d.title = "D"
    add_d.description = "3"

    nodes.extend([
        add_a,
        add_b,
        add_c,
        add_d,
    ])

    return dag_node


def test_python_workflow():
    flow_node = create_graph_flow()
    executor = DAG(flow_node)

    validation_error = executor.validate()
    if validation_error is not None:
        raise Exception(f"Validation failed. Please check validation_error: {validation_error}")
    executor.run()
    for node in executor.node.get_sub_nodes():
        assert node.outputs[0].values[0] == int(node.description), f"Expected {node.description}, got {node.outputs[0].values[0]}"
    return
