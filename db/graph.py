import datetime
from collections import deque, defaultdict
from . import Block, File, DBObject, Node, ValidationError
from utils.db_connector import *
from utils.common import to_object_id, ObjectId
from constants import GraphRunningStatus, ValidationTargetType, ValidationCode


class Graph(DBObject):
    """
    Basic graph with db interface
    """

    def __init__(self, graph_id=None):
        super(Graph, self).__init__()
        self._id = None
        self.title = 'Title'
        self.description = 'Description'
        self.graph_running_status = GraphRunningStatus.CREATED
        self.author = None
        self.public = False
        self.nodes = []

        if graph_id:
            self._id = to_object_id(graph_id)
            self.load()

        if not self._id:
            self._id = ObjectId()

    def to_dict(self):
        return {
            "_id": self._id,
            "title": self.title,
            "description": self.description,
            "graph_running_status": self.graph_running_status,
            "author": self.author,
            "public": self.public,
            "nodes": [node.to_dict() for node in self.nodes]
        }

    def save(self, force=False):
        assert isinstance(self._id, ObjectId)

        if not self.is_dirty() and not force:
            return True

        now = datetime.datetime.utcnow()

        graph_dict = self.to_dict()
        graph_dict["update_date"] = now

        db.graphs.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": graph_dict
            },
            upsert=True,
            )

        self._dirty = False
        return True

    def load(self):
        graph = db.graphs.find_one({'_id': self._id})
        self.load_from_dict(graph)

    def load_from_dict(self, graph):
        for key, value in graph.iteritems():
            if key != 'nodes':
                setattr(self, key, graph[key])

        self._id = to_object_id(self._id)
        self.author = to_object_id(self.author)

        self.nodes = []
        for node_dict in graph['nodes']:
            node = Node()
            node.load_from_dict(node_dict)
            self.nodes.append(node)

        self._dirty = False

    def get_validation_error(self):
        """Return validation error if found; else None"""
        violations = []
        if self.title == '':
            violations.append(
                ValidationError(
                    target=ValidationTargetType.PROPERTY,
                    object_id='title',
                    validation_code=ValidationCode.MISSING_PARAMETER
                ))
        if self.description == '':
            violations.append(
                ValidationError(
                    target=ValidationTargetType.PROPERTY,
                    object_id='description',
                    validation_code=ValidationCode.MISSING_PARAMETER
                ))

        # Meaning the node is in the graph. Otherwise souldn't be in validation step
        for node in self.nodes:
            node_violation = node.get_validation_error()
            if node_violation:
                violations.append(node_violation)

        if len(violations) == 0:
            return None

        return ValidationError(
                    target=ValidationTargetType.GRAPH,
                    object_id=str(self._id),
                    validation_code=ValidationCode.IN_DEPENDENTS,
                    children=violations
                    )

    def arrange_auto_layout(self):
        """Use heuristic to rearange nodes.
        """
        HEADER_HEIGHT = 23
        DESCRIPTION_HEIGHT = 20
        FOOTER_HEIGHT = 10
        BORDERS_HEIGHT = 2
        ITEM_HEIGHT = 20
        SPACE_HEIGHT = 50
        LEFT_PADDING = 30
        TOP_PADDING = 80
        LEVEL_WIDTH = 252
        min_node_height = HEADER_HEIGHT + DESCRIPTION_HEIGHT + FOOTER_HEIGHT + BORDERS_HEIGHT

        node_id_to_level = defaultdict(lambda: -1)
        node_id_to_node = {}
        queued_node_ids = set()
        children_ids = defaultdict(set)

        node_ids = set([node._id for node in self.nodes])
        non_zero_node_ids = set()
        for node in self.nodes:
            node_id_to_node[node._id] = node
            for input in node.inputs:
                for value in input.values:
                    parent_node_id = to_object_id(value.node_id)
                    non_zero_node_ids.add(parent_node_id)
                    children_ids[parent_node_id].add(node._id)

        leaves = node_ids - non_zero_node_ids
        to_visit = deque()
        for leaf_id in leaves:
            node_id_to_level[leaf_id] = 0
            to_visit.append(leaf_id)

        while to_visit:
            node_id = to_visit.popleft()
            node = node_id_to_node[node_id]
            node_level = max([node_id_to_level[node_id]] + [node_id_to_level[child_id] + 1 for child_id in children_ids[node_id]])
            node_id_to_level[node_id] = node_level
            for input in node.inputs:
                for value in input.values:
                    parent_node_id = to_object_id(value.node_id)
                    parent_level = node_id_to_level[parent_node_id]
                    node_id_to_level[parent_node_id] = max(node_level + 1, parent_level)
                    if parent_node_id not in queued_node_ids:
                        to_visit.append(parent_node_id)
                        queued_node_ids.add(parent_node_id)

        max_level = max(node_id_to_level.values())
        level_to_node_ids = defaultdict(list)
        row_heights = defaultdict(lambda: 0)

        def get_index_helper(node, level):
            if level < 0:
                return 0
            parent_node_ids = set()
            for input in node.inputs:
                for value in input.values:
                    parent_node_ids.add(to_object_id(value.node_id))

            for index, node_id in enumerate(level_to_node_ids[level]):
                if node_id in parent_node_ids:
                    return index
            return -1

        def get_index(node, max_level, level):
            return tuple(
                    [get_index_helper(node, lvl) for lvl in range(max_level, level, -1)]
                )

        for node_id, level in node_id_to_level.items():
            level_to_node_ids[level].append(node_id)

        for level in range(max_level, -1, -1):
            level_node_ids = level_to_node_ids[level]
            index_to_node_id = []
            for node_id in level_node_ids:
                node = node_id_to_node[node_id]
                index = get_index(node, max_level, level)
                index_to_node_id.append((index, node_id))

            index_to_node_id.sort()
            level_to_node_ids[level] = [node_id for _, node_id in index_to_node_id]

            for index, node_id in enumerate(level_to_node_ids[level]):
                node = node_id_to_node[node_id]
                node_height = min_node_height + ITEM_HEIGHT * max(len(node.inputs), len(node.outputs))
                row_heights[index] = max(row_heights[index], node_height)

        cum_heights = [0]
        for index in range(len(row_heights)):
            cum_heights.append(cum_heights[-1] + row_heights[index] + SPACE_HEIGHT)

        for level in range(max_level, -1, -1):
            level_node_ids = level_to_node_ids[level]
            for index, node_id in enumerate(level_node_ids):
                node = node_id_to_node[node_id]
                node.x = LEFT_PADDING + (max_level - level) * LEVEL_WIDTH
                node.y = TOP_PADDING + cum_heights[index]

    def __str__(self):
        return 'Graph(_id="{}", nodes={})'.format(self._id, [str(b) for b in self.nodes])

    def __repr__(self):
        return 'Graph(_id="{}", title="{}", nodes={})'.format(self._id, self.title, str(self.nodes))

    def __getattr__(self, name):
        raise Exception("Can't get attribute '{}'".format(name))


if __name__ == "__main__":
    graph = Graph()
    graph.title = "Test graph"
    graph.description = "Test description"

    node_id = db.nodes.find_one({'base_node_name': 'get_resource'})['_id']
    get_resource = Block(node_id)
    get_resource.parameters['resource_id'] = 'Piton.txt'
    get_resource.derived_from = node_id

    node_id = db.nodes.find_one({'base_node_name': 'echo'})['_id']
    echo = Block(node_id)
    echo.parameters['text'] = 'hello world'
    echo.derived_from = node_id

    node_id = db.nodes.find_one({'base_node_name': 'grep'})['_id']
    grep = Block(node_id)
    grep.inputs = {'in': {'node_id': get_resource._id, 'resource': 'out'}}
    grep.parameters['text'] = 'def'
    grep.derived_from = node_id

    graph.nodes = [get_resource, echo, grep]
    # graph.graph_running_status = GraphRunningStatus.READY

    #graph.save()

    # graph = Graph('5a28e0640310e9847ce041f0')
    # print graph.nodes[0].title
