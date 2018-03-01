from abc import ABCMeta, abstractmethod
from enum import Enum
from collections import defaultdict
from db import Block, Graph
from constants import BlockRunningStatus, GraphRunningStatus
from .base_blocks import BlockCollection
from utils.common import to_object_id


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
            self.graph_id = graph
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
            for block_input in block.inputs:
                for input_value in block_input.values:
                    parent_block_id = to_object_id(input_value.block_id)
                    self.block_id_to_dependents[parent_block_id].add(block_id)
                    if self.block_id_to_block[parent_block_id].block_running_status not in {BlockRunningStatus.SUCCESS, BlockRunningStatus.FAILED}:
                        dependency_index += 1

            if block.block_running_status not in {BlockRunningStatus.SUCCESS, BlockRunningStatus.FAILED}:
                self.uncompleted_blocks_count +=1
            self.dependency_index_to_block_ids[dependency_index].add(block_id)
            self.block_id_to_dependency_index[block_id] = dependency_index

    def finished(self):
        return self.graph.graph_running_status in {GraphRunningStatus.SUCCESS, GraphRunningStatus.FAILED}

    def pop_jobs(self):
        """Get a set of blocks with satisfied dependencies"""
        res = []
        for block_id in self.dependency_index_to_block_ids[0]:
            block = self._get_block_with_inputs(block_id).copy()       
            job = self.block_collection.make_job(block)
            res.append(job)
        del self.dependency_index_to_block_ids[0]
        return res

    def update_block(self, block):
        self._set_block_status(block._id, block.block_running_status)
        self.block_id_to_block[block._id].load_from_dict(block.to_dict())   # copy
        self.graph.save(force=True)

    def _set_block_status(self, block_id, block_running_status):
        # if block is already up to date
        if block_running_status == self.block_id_to_block[block_id].block_running_status:
            return

        self.block_id_to_block[block_id].block_running_status = block_running_status

        if block_running_status == BlockRunningStatus.FAILED:
            self.graph.graph_running_status = GraphRunningStatus.FAILED

        if block_running_status in {BlockRunningStatus.SUCCESS, BlockRunningStatus.FAILED}:
            for dependent_block_id in self.block_id_to_dependents[block_id]:

                dependent_block = self.block_id_to_block[dependent_block_id]
                prev_dependency_index = self.block_id_to_dependency_index[dependent_block_id]

                removed_dependencies = 0
                for block_input in dependent_block.inputs:
                    for input_value in block_input.values:
                        if to_object_id(input_value.block_id) == to_object_id(block_id):
                            removed_dependencies += 1
                dependency_index = prev_dependency_index - removed_dependencies

                self.dependency_index_to_block_ids[prev_dependency_index].remove(dependent_block_id)
                self.dependency_index_to_block_ids[dependency_index].add(dependent_block_id)
                self.block_id_to_dependency_index[dependent_block_id] = dependency_index
            self.uncompleted_blocks_count -= 1

        if self.uncompleted_blocks_count == 0 and self.graph.graph_running_status != GraphRunningStatus.FAILED:
            self.graph.graph_running_status = GraphRunningStatus.SUCCESS

        # self.graph.save()

    def _get_block_with_inputs(self, block_id):
        """Get the block and init its inputs, i.e. filling its resource_ids"""
        res = self.block_id_to_block[block_id]
        for block_input in res.inputs:
            for value in block_input.values:
                value.resource_id = self.block_id_to_block[to_object_id(value.block_id)].get_output_by_name(
                    value.output_id
                    ).resource_id
        return res


def main():
    graph_scheduler = GraphScheduler('5a6d78570310e925ad2437a5')

    while not graph_scheduler.finished():
        jobs = graph_scheduler.pop_jobs()
        for job in jobs:
            block = job.block
            print repr(block)
            for output in block.outputs:
                output.resource_id = 'A'
            block.block_running_status = BlockRunningStatus.SUCCESS
            graph_scheduler.update_block(block)


if __name__ == "__main__":
    main()