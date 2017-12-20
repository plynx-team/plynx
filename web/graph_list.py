#!/usr/bin/env python
from web.common import *
from db.graph_collection_manager import GraphCollectionManager

@app.route("/graphs/")
def get_pool_list():
    graph_collection_manager = GraphCollectionManager()
    return render_template('graph_list.html', graph_list=enumerate(graph_collection_manager.get_db_graphs()))
