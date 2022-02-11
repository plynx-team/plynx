import logging


class Registry:
    def __init__(self):
        self.code_function_location_to_node = {}
        self.code_function_location_to_hash = {}

    def register_node(self, node):
        self.code_function_location_to_node[node.code_function_location] = node
        self.code_function_location_to_hash[node.code_function_location] = node.code_hash
        logging.warn(f"Registered operation with location `{node.code_function_location}`")

    def find_nodes(self, function_locations):
        res = []
        for fl in function_locations:
            if fl not in self.code_function_location_to_node:
                continue
            res.append(self.code_function_location_to_node[fl])
        return res


registry = Registry()
