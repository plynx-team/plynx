from collections import deque
from future.utils import lmap
import copy
import collections
import time
import logging
from plynx.api import InvalidTypeArgumentError, BaseNode, \
    InvalidUssageError, GraphFailed, _NodeRunningStatus, _GraphRunningStatus, \
    _GraphPostAction
from plynx.api import _get_obj, _save_graph


def update_recursive(d, u):
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            d[k] = update_recursive(d.get(k, {}), v)
        elif isinstance(v, list):
            for v_item in v:
                if 'name' in v_item:
                    for d_item in d[k]:
                        if 'name' in d_item and d_item['name'] == v_item['name']:
                            update_recursive(d_item, v_item)
                else:
                    d[k].append(v_item)
        else:
            d[k] = v if v else d[k]
    return d


def traverse_nodes(graph, targets):
    nodes = []
    visited_nodes = set()
    to_visit = deque(targets)
    while len(to_visit) > 0:
        node = to_visit.popleft()
        if node._id in visited_nodes:
            continue
        visited_nodes.add(node._id)
        nodes.append(node)
        for name, output_items in node.inputs.items():
            if output_items:
                for output_item in output_items:
                    if output_item.node._id in visited_nodes:
                        continue
                    to_visit.append(output_item.node)
    return nodes


class Graph(object):
    def __init__(self, client=None, title=None, description=None, targets=None):
        self.client = client
        self.title = title or ''
        self.description = description or ''
        self.targets = targets
        self._graph_dict = None
        if not isinstance(targets, list):
            self.targets = [targets]
        for target in self.targets:
            if not isinstance(target, BaseNode):
                raise InvalidTypeArgumentError('Target is expected to be an instance of {}, found `{}`'.format(BaseNode, type(target)))

    def _dictify(self):
        nodes = [node for node in traverse_nodes(self, self.targets)]
        plynx_nodes = {}
        for base_node_name, parent_node in set([(n.base_node_name, n.parent_node) for n in nodes]):
            obj = _get_obj('nodes', parent_node, self.client)
            plynx_nodes[parent_node] = obj

        res_nodes = []
        for node in nodes:
            node_dict = node._dictify()
            plynx_node = copy.deepcopy(plynx_nodes[node.parent_node])
            update_recursive(plynx_node, node_dict)
            res_nodes.append(plynx_node)

        graph = {
            'title': self.title,
            'description': self.description,
            'graph_running_status': _GraphRunningStatus.CREATED,
            'nodes': res_nodes
        }
        return graph

    def save(self):
        d = self._dictify()
        if self._graph_dict:
            d['_id'] = self._graph_dict['_id']
        self._graph_dict, url = _save_graph(graph=d, actions=[_GraphPostAction.AUTO_LAYOUT, _GraphPostAction.SAVE], client=self.client)
        logging.info('Graph successfully saved: {}'.format(url))
        return self

    def approve(self):
        d = self._dictify()
        if self._graph_dict:
            d['_id'] = self._graph_dict['_id']
        self._graph_dict, url = _save_graph(graph=d, actions=[_GraphPostAction.AUTO_LAYOUT, _GraphPostAction.APPROVE], client=self.client)
        logging.info('Graph successfully approved: {}'.format(url))
        return self

    def wait(self):
        if not self._graph_dict:
            raise InvalidUssageError("The graph neigher saved nor approved yet")
        if self._graph_dict["graph_running_status"].upper() == _GraphRunningStatus.CREATED:
            raise InvalidUssageError("The graph must be approved first")

        while True:
            graph = _get_obj('graphs', self._graph_dict["_id"], self.client)
            counter = collections.Counter(
                [
                    node['node_running_status'] for node in graph['nodes']
                ]
            )
            graph_running_status = graph['graph_running_status']
            numerator = counter.get(_NodeRunningStatus.SUCCESS, 0)
            denominator = sum(counter.values()) - counter.get(_NodeRunningStatus.STATIC, 0)
            if denominator > 0:
                progress = float(numerator) / denominator
            else:
                progress = 1.0
            node_running_statuss = lmap(
                lambda r: '{}: {}'.format(r[0], r[1]),
                counter.items()
            )

            logging.info('\t'.join(
                [
                    graph_running_status,
                    '{0:.0f}%'.format(progress * 100)
                ] + node_running_statuss))

            if graph_running_status.upper() not in [
                    _GraphRunningStatus.READY,
                    _GraphRunningStatus.RUNNING,
                    _GraphRunningStatus.SUCCESS]:
                raise GraphFailed('Graph finished with status `{}`'.format(graph_running_status))

            if graph_running_status.upper() == _GraphRunningStatus.SUCCESS:
                logging.info('Graph finished with status `{}`'.format(graph_running_status))
                break

            time.sleep(1)
        return self
