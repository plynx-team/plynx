import os, sys
from . import BlockBase

class BlockCollection:
    def __init__(self):
        self.name_to_class = {}
        path = os.path.dirname(os.path.abspath(__file__))
        for py in [f[:-3] for f in os.listdir(path) if f.endswith('.py') and f not in ['__init__.py', 'collection.py']]:
            mod = __import__('.'.join(['graph', 'base_blocks', py]), fromlist=[py])
            classes = [getattr(mod, x) for x in dir(mod) if isinstance(getattr(mod, x), type)]
            for cls in classes:
                if not issubclass(cls, BlockBase):
                    continue
                setattr(sys.modules[__name__], cls.__name__, cls)
                name = cls.get_base_name()
                if name is not None:
                    self.name_to_class[name] = cls

    def make_from_block_with_inputs(self, block_with_inputs):
        job = self.name_to_class[block_with_inputs.base_block_name]()
        job.restore_from_dict(block_with_inputs)
        return job


if __name__ == "__main__":
    collection = BlockCollection()
    print("Found classes:")
    for name, cls in collection.name_to_class.iteritems():
        print('- ' + '\t'.join(map(str, [name, cls])))
