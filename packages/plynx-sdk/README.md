# plynx-sdk

Zero-dependency Python SDK for authoring [PLynx](https://pypi.org/project/plynx/) operations and Node Packs. Standard library only.

## Installation

Add `plynx-sdk` as a dependency of your Node Pack:

```bash
uv add plynx-sdk
```

Or install with pip:

```bash
pip install plynx-sdk
```

## Quick Example

```python
from typing import TypedDict
from plynx_sdk import Op, checkpoint, op


@op(title="Greet")
def greet(name: str) -> str:
    return f"Hello, {name}!"


class PickOption(Op):
    TITLE = "Pick Option"

    class Outputs(TypedDict):
        choice: str

    def run(self, question: str) -> Outputs:
        answer = checkpoint(question, options=["yes", "no"])
        return {"choice": answer}
```

## Documentation

- [Guide: Authoring a Node Pack](https://github.com/plynx-team/plynx/blob/main/docs/guides/author_pack.md)
- [PLynx Repository](https://github.com/plynx-team/plynx)
- [Changelog](https://github.com/plynx-team/plynx/blob/main/CHANGELOG.md)

## License

Apache-2.0
