from __future__ import division
from collections import deque, defaultdict
from plynx.db import DBObject, DBObjectField, Node, ValidationError
from plynx.utils.common import to_object_id, ObjectId
from plynx.constants import GraphRunningStatus, ValidationTargetType, ValidationCode, ParameterTypes, NodeRunningStatus


class Graph(DBObject):
    """Basic graph with db interface."""

    FIELDS = {
        '_id': DBObjectField(
            type=ObjectId,
            default=ObjectId,
            is_list=False,
            ),
        'title': DBObjectField(
            type=str,
            default='Title',
            is_list=False,
            ),
        'description': DBObjectField(
            type=str,
            default='Description',
            is_list=False,
            ),
        'graph_running_status': DBObjectField(
            type=str,
            default=GraphRunningStatus.CREATED,
            is_list=False,
            ),
        'author': DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
        'public': DBObjectField(
            type=bool,
            default=False,
            is_list=False,
            ),
        'nodes': DBObjectField(
            type=Node,
            default=list,
            is_list=True,
            ),
    }

    DB_COLLECTION = 'graphs'

    def cancel(self):
        """Cancel the graph."""
        self.graph_running_status = GraphRunningStatus.CANCELED
        for node in self.nodes:
            if node.node_running_status in [NodeRunningStatus.RUNNING, NodeRunningStatus.IN_QUEUE]:
                node.node_running_status = NodeRunningStatus.CANCELED
        self.save(force=True)

    def get_validation_error(self):
        """Validate Graph.

        Return:
            (ValidationError)   Validation error if found; else None
        """
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
        """Use heuristic to rearange nodes."""
        HEADER_HEIGHT = 23
        DESCRIPTION_HEIGHT = 20
        FOOTER_HEIGHT = 10
        BORDERS_HEIGHT = 2
        ITEM_HEIGHT = 20
        SPACE_HEIGHT = 50
        LEFT_PADDING = 30
        TOP_PADDING = 80
        LEVEL_WIDTH = 252
        SPECIAL_PARAMETER_HEIGHT = 20
        SPECIAL_PARAMETER_TYPES = [ParameterTypes.CODE]
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
                special_parameters_count = sum(
                    1 if parameter.parameter_type in SPECIAL_PARAMETER_TYPES and parameter.widget else 0
                    for parameter in node.parameters
                )
                node_height = sum([
                    min_node_height,
                    ITEM_HEIGHT * max(len(node.inputs), len(node.outputs)),
                    special_parameters_count * SPECIAL_PARAMETER_HEIGHT
                ])
                row_heights[index] = max(row_heights[index], node_height)

        cum_heights = [0]
        for index in range(len(row_heights)):
            cum_heights.append(cum_heights[-1] + row_heights[index] + SPACE_HEIGHT)

        max_height = max(cum_heights)

        for level in range(max_level, -1, -1):
            level_node_ids = level_to_node_ids[level]
            level_height = cum_heights[len(level_node_ids)]
            level_padding = (max_height - level_height) // 2
            for index, node_id in enumerate(level_node_ids):
                node = node_id_to_node[node_id]
                node.x = LEFT_PADDING + (max_level - level) * LEVEL_WIDTH
                node.y = TOP_PADDING + level_padding + cum_heights[index]

    def __str__(self):
        return 'Graph(_id="{}", nodes={})'.format(self._id, [str(b) for b in self.nodes])

    def __repr__(self):
        return 'Graph(_id="{}", title="{}", nodes={})'.format(self._id, self.title, str(self.nodes))
