import sys
import csv
import logging
from datetime import datetime
import dateutil.parser
from collections import namedtuple
from plynx.db import NodeCache, NodeCacheManager
from plynx.utils.common import query_yes_no
from plynx.utils import file_handler


OutputListTuple = namedtuple('OutputListTuple', ['node_cache_id', 'insertion_date', 'resource_type', 'name', 'file_type', 'resource_id', 'protected'])

LIST_CACHE = 'list'
CLEAN_CACHE = 'clean'
MODES = [
    CLEAN_CACHE,
    LIST_CACHE,
]

node_cache_manager = NodeCacheManager()


def run_list_cache(start_datetime, end_datetime):
    file_writer = csv.writer(sys.stdout)
    file_writer.writerow(OutputListTuple._fields)
    for node_cache_dict in node_cache_manager.get_list(start_datetime, end_datetime):
        node_cache = NodeCache.from_dict(node_cache_dict)
        for resource_type in {'outputs', 'logs'}:
            for resource in getattr(node_cache, resource_type):
                if resource.resource_id:
                    file_writer.writerow(
                        OutputListTuple(
                            node_cache_id=node_cache._id,
                            insertion_date=node_cache_dict['insertion_date'].isoformat(),
                            resource_type=resource_type,
                            name=resource.name,
                            file_type=resource.file_type,
                            resource_id=resource.resource_id,
                            protected=node_cache.protected
                        )
                    )


def run_clean_cache(start_datetime, end_datetime, yes):
    query = node_cache_manager.get_list(start_datetime, end_datetime, non_protected_only=True)
    query_count = query.count()
    if query_count == 0:
        logging.critical('No cached results to remove')
        return 0
    if not yes and not query_yes_no('Are you sure you want to remove `{}` cached results?'.format(query_count), default='no'):
        print('Canceled')
        return 0

    logging.info('Start removing `{}` objects'.format(query_count))
    for node_cache_dict in query:
        node_cache = NodeCache.from_dict(node_cache_dict)
        try:
            for resource_type in {'outputs', 'logs'}:
                for resource in getattr(node_cache, resource_type):
                    if resource.resource_id:
                        file_handler.remove(resource.resource_id)
        # TODO use more cache states, such as `attempted to remove`
        finally:
            node_cache.removed = True
            node_cache.save()
            logging.info('Removed files from `{}`'.format(node_cache))

    node_cache_manager.clean_up()
    logging.info('Removed `{}` objects'.format(query_count))
    return 0


def run_cache(mode, start_datetime, end_datetime, yes):
    if mode not in MODES:
        raise ValueError('`mode` must be one of `{values}`. Value `{mode}` is given'.format(
            values=MODES,
            mode=mode,
        ))
    start_datetime = dateutil.parser.parse(start_datetime) if start_datetime else None
    end_datetime = dateutil.parser.parse(end_datetime) if end_datetime else datetime.now()
    if mode == LIST_CACHE:
        return run_list_cache(start_datetime, end_datetime)
    elif mode == CLEAN_CACHE:
        return run_clean_cache(start_datetime, end_datetime, yes)
