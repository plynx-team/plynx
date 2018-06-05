#!/usr/bin/env python
from __future__ import absolute_import
import json
from db import Node, NodeCollectionManager
from graph.base_nodes import NodeCollection
from web.common import app, request, auth, g
from utils.common import to_object_id, JSONEncoder
from constants import NodeStatus, NodePostAction, NodePostStatus

node_collection_manager = NodeCollectionManager()
node_collection = NodeCollection()


def _make_fail_response(message):
    return JSONEncoder().encode({
        'status': NodePostStatus.FAILED,
        'message': message
        })

@app.route('/plynx/api/v0/nodes', methods=['GET'])
@app.route('/plynx/api/v0/nodes/<node_link>', methods=['GET'])
@auth.login_required
def get_nodes(node_link=None):
    author = to_object_id(g.user._id)
    # if node_link is a base node
    if node_link in node_collection.name_to_class:
        return JSONEncoder().encode({
            'data': node_collection.name_to_class[node_link].get_default().to_dict(),
            'status':'success'})
    # if node_link is defined (Node id)
    elif node_link:
        try:
            node_id = to_object_id(node_link)
        except:
            return 'Invalid ID', 404
        node = node_collection_manager.get_db_node(node_id, author)
        if node:
            return JSONEncoder().encode({
                'data': node,
                'status':'success'})
        else:
            return 'Node was not found', 404
    else:
        query = json.loads(request.args.get('query', "{}"))
        query["author"] = to_object_id(g.user._id)
        nodes_query = {k: v for k, v in query.iteritems() if k in {'per_page', 'offset', 'status', 'author'}}
        count_query = {k: v for k, v in query.iteritems() if k in {'status', 'author'}}
        return JSONEncoder().encode({
            'nodes': node_collection_manager.get_db_nodes(**nodes_query),
            'total_count': node_collection_manager.get_db_nodes_count(**count_query),
            'status':'success'})


@app.route('/plynx/api/v0/nodes', methods=['POST'])
@auth.login_required
def post_node():
    app.logger.debug(request.data)
    try:
        body = json.loads(request.data)['body']

        node = Node()
        node.load_from_dict(body['node'])
        node.author = g.user._id

        action = body['action']
        if action == NodePostAction.SAVE:
            if node.node_status != NodeStatus.CREATED:
                return _make_fail_response('Cannot save node with status `{}`'.format(node.node_status))

            node.save(force=True)

        elif action == NodePostAction.APPROVE:
            if node.node_status != NodeStatus.CREATED:
                return _make_fail_response('Node status `{}` expected. Found `{}`'.format(NodeStatus.CREATED, node.node_status))
            validation_error = node.get_validation_error()
            if validation_error:
                return JSONEncoder().encode({
                            'status': NodePostStatus.VALIDATION_FAILED,
                            'message': 'Node validation failed',
                            'validation_error': validation_error.to_dict()
                            })

            node.node_status = NodeStatus.READY
            node.save(force=True)

        elif action == NodePostAction.VALIDATE:
            validation_error = node.get_validation_error()

            if validation_error:
                return JSONEncoder().encode({
                            'status': NodePostStatus.VALIDATION_FAILED,
                            'message': 'Node validation failed',
                            'validation_error': validation_error.to_dict()
                            })
        elif action == NodePostAction.DEPRECATE:
            if node.node_status != NodeStatus.READY:
                return _make_fail_response('Node status `{}` expected. Found `{}`'.format(NodeStatus.READY, node.node_status))

            node.node_status = NodeStatus.DEPRECATED
            node.save(force=True)

        else:
            return _make_fail_response('Unknown action `{}`'.format(action))

        return JSONEncoder().encode(
            {
                'status': NodePostStatus.SUCCESS,
                'message': 'Node(_id=`{}`) successfully updated'.format(str(node._id))
            })
    except Exception as e:
        app.logger.error(e)
        return _make_fail_response('Internal error: "{}"'.format(str(e)))
