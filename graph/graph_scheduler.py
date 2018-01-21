from abc import ABCMeta, abstractmethod
from enum import Enum
from collections import defaultdict
from db import Block, Graph
from constants import BlockRunningStatus, GraphRunningStatus
from .base_blocks import BlockCollection


class GraphScheduler(object):
    """ Main graph scheduler.

    It works with a single db.graph.Graph object.
    GraphScheduler loads the Graph from DB.
    It determines blocks to be executed.
    
    Args:
        graph (str or Graph)

    """
    def __init__(self, graph, block_collection=None):
        if isinstance(graph, Graph):
            self.graph_id = graph._id
            self.graph = graph
        else:
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
        if block_collection:
            self.block_collection = block_collection
        else:
            self.block_collection = BlockCollection()

        for block in self.graph.blocks:
            block_id = block._id
            dependency_index = 0
            for name, link in block.inputs.iteritems():
                # link: {u'type': u'file', u'value': {u'output_id': u'out', u'block_id': u'5a62f2d15825680000bd4ebd'}}
                parent_block_id = link['value']['block_id']
                self.block_id_to_dependents[parent_block_id].add(block_id)
                if self.block_id_to_block[parent_block_id].block_running_status not in {BlockRunningStatus.SUCCESS, BlockRunningStatus.FAILED}:
                    dependency_index += 1
            if block.block_running_status not in {BlockRunningStatus.SUCCESS, BlockRunningStatus.FAILED}:
                self.uncompleted_blocks_count +=1
            self.dependency_index_to_block_ids[dependency_index].add(block_id)
            self.block_id_to_dependency_index[block_id] = dependency_index

    def finished(self):
        return self.graph.block_running_status in {GraphRunningStatus.SUCCESS, GraphRunningStatus.FAILED}

    def pop_jobs(self):
        """Get a set of blocks with satisfied dependencies"""
        res = []
        for block_id in self.dependency_index_to_block_ids[0]:
            block = self._get_block_with_inputs(block_id)
            job = self.block_collection.make_from_block_with_inputs(block)
            job.graph_id = self.graph_id
            res.append(job)
        del self.dependency_index_to_block_ids[0]
        return res

    def set_block_status(self, block, block_running_status):
        block_id = block.block_id
        self.block_id_to_block[block_id].block_running_status = block_running_status

        if block_running_status == BlockRunningStatus.FAILED:
            self.graph.graph_running_status = GraphRunningStatus.FAILED

        if block_running_status in {BlockRunningStatus.SUCCESS, BlockRunningStatus.FAILED}:
            for dependent_block_id in self.block_id_to_dependents[block_id]:

                dependent_block = self.block_id_to_block[dependent_block_id]
                prev_dependency_index = self.block_id_to_dependency_index[dependent_block_id]

                removed_dependencies = 0
                for name, link in dependent_block.inputs.iteritems():
                    if link['value']['block_id'] == block_id:
                        removed_dependencies += 1
                dependency_index = prev_dependency_index - removed_dependencies

                self.dependency_index_to_block_ids[prev_dependency_index].remove(dependent_block_id)
                self.dependency_index_to_block_ids[dependency_index].add(dependent_block_id)
            self.uncompleted_blocks_count -= 1
            self.block_id_to_block[block_id].outputs = block.outputs
            self.block_id_to_block[block_id].logs = block.logs

        if self.uncompleted_blocks_count == 0:
            self.graph.graph_running_status = GraphRunningStatus.SUCCESS

        self.graph.save()

    def _get_block_with_inputs(self, block_id):
        res = self.block_id_to_block[block_id].copy()
        for input_name in res.inputs.keys():
            parent_block_id = res.inputs[input_name]['value']['block_id']
            parent_resource = res.inputs[input_name]['value']['output_id']
            res.inputs[input_name] = self.block_id_to_block[parent_block_id].outputs[parent_resource]
        return res


def main():
    graph_scheduler = GraphScheduler('5a2e038f0310e9d485621f4a')

    while not graph_scheduler.finished():
        blocks = graph_scheduler.pop_blocks()
        for block in blocks:
            print repr(block)
            for k in block.outputs:
                block.outputs[k] = 'A'
            graph_scheduler.set_block_status(block, BlockRunningStatus.SUCCESS)


if __name__ == "__main__":
    main()