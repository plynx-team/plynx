import copy
from abc import ABCMeta, abstractmethod
from enum import Enum
from collections import defaultdict
from db.graph import Graph
from common.block_enums import BlockRunningStatus
from common.graph_enums import GraphRunningStatus


class GraphScheduler(object):
    """ Main graph scheduler.

    It works with a single db.graph.Graph object.
    GraphScheduler loads the Graph from DB.
    It determines blocks to be executed.
    
    Args:
        graph_id (str)

    """
    def __init__(self, graph_id):
        self.graph_id = graph_id

        self.graph = Graph(self.graph_id)

        self.block_id_to_block = {
            block._id : block for block in self.graph.blocks
        }

        # number of dependencies to ids 
        self.dependency_index_to_block_ids = defaultdict(lambda: set())
        self.block_id_to_dependents = defaultdict(lambda: set())
        self.block_id_to_dependency_index = defaultdict(lambda: 0)
        self.uncompleted_blocks_count = 0

        for block in self.graph.blocks:
            block_id = block._id
            dependency_index = 0
            for name, link in block.inputs.iteritems():
                parent_block_id = link['block_id']
                self.block_id_to_dependents[parent_block_id].add(block_id)
                if self.block_id_to_block[parent_block_id].running_status not in {BlockRunningStatus.SUCCESS, BlockRunningStatus.FAILED}:
                    dependency_index += 1
            if block.running_status not in {BlockRunningStatus.SUCCESS, BlockRunningStatus.FAILED}:
                self.uncompleted_blocks_count +=1
            self.dependency_index_to_block_ids[dependency_index].add(block_id)
            self.block_id_to_dependency_index[block_id] = dependency_index

    def completed(self):
        return self.graph.running_status in {GraphRunningStatus.SUCCESS, GraphRunningStatus.FAILED}

    def pop_blocks(self):
        """Get a set of blocks with satisfied dependencies"""
        res = [self.get_block_with_inputs(block_id) for block_id in self.dependency_index_to_block_ids[0]]
        del self.dependency_index_to_block_ids[0]
        return res

    def set_block_status(self, block, running_status):
        block_id = block._id
        self.block_id_to_block[block_id].running_status = running_status

        if running_status == BlockRunningStatus.FAILED:
            self.graph.running_status = GraphRunningStatus.FAILED

        if running_status in {BlockRunningStatus.SUCCESS, BlockRunningStatus.FAILED}:
            for dependent_block_id in self.block_id_to_dependents[block_id]:

                dependent_block = self.block_id_to_block[dependent_block_id]
                prev_dependency_index = self.block_id_to_dependency_index[dependent_block_id]

                removed_dependencies = 0
                for name, link in dependent_block.inputs.iteritems():
                    if link['block_id'] == block_id:
                        removed_dependencies += 1
                dependency_index = prev_dependency_index - removed_dependencies

                self.dependency_index_to_block_ids[prev_dependency_index].remove(dependent_block_id)
                self.dependency_index_to_block_ids[dependency_index].add(dependent_block_id)
            self.uncompleted_blocks_count -= 1
            self.block_id_to_block[block_id].outputs = block.outputs

        if self.uncompleted_blocks_count == 0:
            self.graph.running_status = GraphRunningStatus.SUCCESS

        # self.graph.save()

    def get_block_with_inputs(self, block_id):
        res = copy.copy(self.block_id_to_block[block_id])
        for input_name in res.inputs.keys():
            parent_block_id = res.inputs[input_name]['block_id']
            parent_resource = res.inputs[input_name]['resource']
            res.inputs[input_name] = self.block_id_to_block[parent_block_id].outputs[parent_resource]
        return res


def main():
    graph_scheduler = GraphScheduler('5a2cdd1d0310e9c68798ff38')

    while not graph_scheduler.completed():
        blocks = graph_scheduler.pop_blocks()
        for block in blocks:
            print repr(block)
            for k in block.outputs:
                block.outputs[k] = 'A'
            graph_scheduler.set_block_status(block, BlockRunningStatus.SUCCESS)


if __name__ == "__main__":
    main()