#!/usr/bin/env python
from db.graph_collection_manager import GraphCollectionManager
from constants import BLOCK_RUNNING_STATUS_MAP, GRAPH_RUNNING_STATUS_MAP
from web.common import *
from utils.common import to_object_id, JSONEncoder
from collections import defaultdict, OrderedDict
import random

SAMPLE_SIZE = 10
graph_collection_manager = GraphCollectionManager()


def _modify_graph_in_place(graph):
    graph['graph_running_status'] = GRAPH_RUNNING_STATUS_MAP[graph['graph_running_status']]
    for block in graph['blocks']:
        block['block_running_status'] = BLOCK_RUNNING_STATUS_MAP[block['block_running_status']]
    return graph


@app.route('/plynx/api/v0/graphs', methods=['GET'])
@app.route('/plynx/api/v0/graphs/<graph_id>', methods=['GET'])
def get_graph(graph_id=None):
    if graph_id:
        return JSONEncoder().encode({
            'data': _modify_graph_in_place(graph_collection_manager.get_db_graph(graph_id)),
            'status':'success'})
    else:
        return JSONEncoder().encode({
            'data': [_modify_graph_in_place(graph) for graph in graph_collection_manager.get_db_graphs()],
            'status':'success'})
