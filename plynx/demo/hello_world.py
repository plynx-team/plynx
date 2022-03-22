"""PLynx Operations defined as python code."""
import plynx.node


@plynx.node.param(name='your_name', var_type=str, default="World")
@plynx.node.output(name='name', var_type=str)
@plynx.node.operation(
    title="Get name",
)
def get_name(your_name):
    """Pass `your_name` parameter as output."""
    return {
        "name": your_name,
    }


@plynx.node.input(name='name', var_type=str)
@plynx.node.output(name='message', var_type=str)
@plynx.node.operation(
    title="Print message",
)
def print_message(name):
    """Print greeting message."""
    res = f"Hello {name}!"
    print(res)
    return {
        'message': res,
    }


GROUP = plynx.node.utils.Group(
    title="Hello World",
    items=[
        get_name,
        print_message,
    ]
)
