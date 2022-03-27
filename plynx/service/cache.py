"""Main PLynx cache service and utils"""

import csv
import logging
import sys
from collections import namedtuple
from datetime import datetime
from typing import Optional

import dateutil.parser

from plynx.db.node_cache import NodeCache
from plynx.db.node_cache_manager import NodeCacheManager
from plynx.utils.common import query_yes_no

OutputListTuple = namedtuple('OutputListTuple', ['node_cache_id', 'insertion_date', 'resource_type', 'name', 'file_type', 'resource_id', 'protected'])

LIST_CACHE = 'list'
CLEAN_CACHE = 'clean'
MODES = [
    CLEAN_CACHE,
    LIST_CACHE,
]

node_cache_manager: NodeCacheManager = NodeCacheManager()


def run_list_cache(start_datetime: Optional[datetime], end_datetime: datetime):
    """Print all of the cache objects in a given time frame"""
    file_writer = csv.writer(sys.stdout)
    file_writer.writerow(OutputListTuple._fields)
    for node_cache_dict in node_cache_manager.get_list(start_datetime, end_datetime):   # pylint: disable=use-sequence-for-iteration
        node_cache = NodeCache.from_dict(node_cache_dict)
        for resource_type in {'outputs', 'logs'}:   # pylint: disable=use-sequence-for-iteration
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
                            protected=node_cache.protected,     # pylint: disable=no-member
                        )
                    )


def run_clean_cache(start_datetime: Optional[datetime], end_datetime: datetime, yes: bool):
    """Clean cache"""
    query = node_cache_manager.get_list(start_datetime, end_datetime, non_protected_only=True)
    query_count = query.count()
    if query_count == 0:
        logging.critical('No cached results to remove')
        return
    if not yes and not query_yes_no(f"Are you sure you want to remove `{query_count}` cached results?", default='no'):
        print('Canceled')
        return

    logging.info(f"Start removing `{query_count}` objects")
    for node_cache_dict in query:
        node_cache = NodeCache.from_dict(node_cache_dict)
        try:
            for resource_type in {'outputs', 'logs'}:   # pylint: disable=use-sequence-for-iteration
                for resource in getattr(node_cache, resource_type):
                    if resource.resource_id:
                        raise NotImplementedError()
                        # file_handler.remove(resource.resource_id)
        # TODO use more cache states, such as `attempted to remove`
        finally:
            node_cache.removed = True
            node_cache.save()
            logging.info(f"Removed files from `{node_cache}`")

    node_cache_manager.clean_up()
    logging.info(f"Removed `{query_count}` objects")


def run_cache(mode, start_datetime: str, end_datetime: str, yes: bool):
    """Cache CLI entrypoint"""
    if mode not in MODES:
        raise ValueError(f"`mode` must be one of `{MODES}`. Value `{mode}` is given")
    start_datetime_parsed = dateutil.parser.parse(start_datetime) if start_datetime else None
    end_datetime_parsed = dateutil.parser.parse(end_datetime) if end_datetime else datetime.now()
    if mode == LIST_CACHE:
        run_list_cache(start_datetime_parsed, end_datetime_parsed)
    elif mode == CLEAN_CACHE:
        run_clean_cache(start_datetime_parsed, end_datetime_parsed, yes)
