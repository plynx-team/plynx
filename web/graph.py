#!/usr/bin/env python
import json
from db import GraphCollectionManager
from db import Graph
from web.common import app, request
from utils.common import to_object_id, JSONEncoder
from collections import defaultdict, OrderedDict
import random

SAMPLE_SIZE = 10
graph_collection_manager = GraphCollectionManager()


@app.route('/plynx/api/v0/graphs', methods=['GET'])
@app.route('/plynx/api/v0/graphs/<graph_id>', methods=['GET'])
def get_graph(graph_id=None):
    if graph_id == 'new':
        return JSONEncoder().encode({
            'data': Graph().to_dict(),
            'status':'success'})
    elif graph_id:
        graph = graph_collection_manager.get_db_graph(graph_id)
        if graph:
            return JSONEncoder().encode({
                'data': graph,
                'status':'success'})
        else:
            return 'Graph was not found', 404
    else:
        return JSONEncoder().encode({
            'data': [graph for graph in graph_collection_manager.get_db_graphs()],
            'status':'success'})


@app.route('/plynx/api/v0/graphs/<graph_id>', methods=['PUT'])
# @app.route('/plynx/api/v0/graphs', methods=['POST'])
def post_graph(graph_id):
    print (request)
    data = json.loads(request.data)['body']

    graph = Graph()
    graph.load_from_mongo(data)

    graph.save(force=True)

    return JSONEncoder().encode({'status':'success'})
