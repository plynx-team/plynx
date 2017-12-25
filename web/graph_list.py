#!/usr/bin/env python
from web.common import *
from db.graph_collection_manager import GraphCollectionManager
from utils.common import JSONEncoder

graph_collection_manager = GraphCollectionManager()

@app.route("/graphs/")
def get_pool_list():
    return render_template('graph_list.html', graph_list=enumerate(graph_collection_manager.get_db_graphs()))

@app.route('/plynx/api/v0/graphs', methods=['GET'])
def get_graphs():
    return JSONEncoder().encode({'data': graph_collection_manager.get_db_graphs(), 'status':'success'})
