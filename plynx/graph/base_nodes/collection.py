import os
import sys
from . import BaseNode


class NodeCollection:
    def __init__(self):
        self.name_to_class = {}
        path = os.path.dirname(os.path.abspath(__file__))
        for py in [f[:-3] for f in os.listdir(path) if f.endswith('.py') and f not in ['__init__.py', 'collection.py']]:
            mod = __import__('.'.join(['plynx', 'graph', 'base_nodes', py]), fromlist=[py])
            classes = [getattr(mod, x) for x in dir(mod) if isinstance(getattr(mod, x), type)]
            for cls in classes:
                if not issubclass(cls, BaseNode):
                    continue
                setattr(sys.modules[__name__], cls.__name__, cls)
                name = cls.get_base_name()
                if name is not None:
                    self.name_to_class[name] = cls

    # TODO ever used?
    def make_from_node_with_inputs(self, node_with_inputs):
        job = self.name_to_class[node_with_inputs.base_node_name]()
        job.restore_from_dict(node_with_inputs)
        return job

    def make_job(self, node):
        return self.name_to_class[node.base_node_name](node)


if __name__ == "__main__":
    collection = NodeCollection()
    print("Found classes:")
    for name, cls in collection.name_to_class.iteritems():
        print('- ' + '\t'.join(map(str, [name, cls])))
