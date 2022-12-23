"""PLynx CLI parser"""
from __future__ import print_function

import argparse
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple, Type, Union

from plynx import __version__
from plynx.service.cache import run_cache
from plynx.service.execute import run_execute
from plynx.service.users import run_users
from plynx.service.worker import run_worker
from plynx.utils.config import get_config, set_parameter
from plynx.utils.logs import set_logging_level

_config = get_config()


@dataclass
class Arg:
    """Common argument tuple"""
    flags: Union[Tuple[str], Tuple[str, str]]
    help: str
    action: Optional[str] = None
    default: Optional[Any] = None
    type: Optional[Type] = None
    levels: Optional[List[str]] = None
    required: bool = False


def api(args):
    """Start web service."""
    # lazy load because web initializes too many variables
    from plynx.web.common import run_api  # noqa: E402  # pylint: disable=import-outside-toplevel
    set_logging_level(args.pop('verbose'))
    run_api(**args)


def cache(args):
    """Show cache options."""
    set_logging_level(args.pop('verbose'))
    run_cache(**args)


def worker(args):
    """Start worker service."""
    set_logging_level(args.pop('verbose'))
    run_worker(**args)


def users(args):
    """Show users options."""
    set_logging_level(args.pop('verbose'))
    run_users(**args)


def version(args):  # pylint: disable=unused-argument
    """Print PLynx version"""
    print(__version__)


def execute(args):
    """Execute Operation."""
    set_logging_level(args.pop('verbose'))
    run_execute(**args)


class CLIFactory:
    """The class that generates PLynx CLI parser"""
    ARGS = {
        # Shared
        'verbose': Arg(
            ('-v', '--verbose'),
            help='Set logging output more verbose',
            default=0,
            action='count',
            ),
        'mode': Arg(
            ('--mode',),
            help='Mode',
            type=str),

        # Worker
        'kinds': Arg(
            ("-e", "--kinds"),
            help="Kinds the worker is subscribed to",
            default=_config.worker.kinds,
            action='append',
            levels=['worker', 'kinds'],
            ),
        'api': Arg(
            ("--api", ),
            help="Base API URL",
            default=_config.worker.api,
            type=str,
            levels=['worker', 'api'],
            ),

        # MongoConfig
        'db_host': Arg(
            ('--db-host',),
            help='Database host',
            default=_config.db.host,
            type=str,
            levels=['mongodb', 'host'],
            ),
        'db_port': Arg(
            ('--db-port',),
            help='Database port',
            default=_config.db.port,
            type=str,
            levels=['mongodb', 'port'],
            ),
        'db_user': Arg(
            ('--db-user',),
            help='Database username',
            default=None,
            type=str,
            levels=['mongodb', 'user'],
            ),
        'db_password': Arg(
            ('--db-password',),
            help='Database password',
            default=None,
            type=str,
            levels=['mongodb', 'password'],
            ),

        # StorageConfig
        'storage_scheme': Arg(
            ('--storage-scheme',),
            help='Storage scheme',
            default=_config.storage.scheme,
            type=str,
            levels=['storage', 'scheme'],
            ),
        'storage_prefix': Arg(
            ('--storage-prefix',),
            help='Storage prefix',
            default=_config.storage.prefix,
            type=str,
            levels=['storage', 'prefix'],
            ),
        'credential_path': Arg(
            ('--credential-path',),
            help='Path to the credentials, i.e. $GOOGLE_APPLICATION_CREDENTIALS',
            default=_config.storage.credential_path,
            type=str,
            levels=['storage', 'credential_path'],
            ),

        # AuthConfig
        'secret_key': Arg(
            ('--secret-key',),
            help='Secret Key path (used in auth). If not given, a single user mode will be used.',
            default=None,
            type=str,
            levels=['auth', 'secret_key'],
            ),

        # WebConfig
        'endpoint': Arg(
            ('--endpoint',),
            help='Endpoint of api',
            default=_config.web.endpoint,
            type=str,
            levels=['web', 'endpoint'],
            ),

        # Users
        'username': Arg(
            ('--username',),
            help='Username of the user, required to create/delete a user',
            type=str),
        'password': Arg(
            ('--password',),
            help='Password of the user, required to create a user '
                 'without --use_random_password',
            type=str),

        # Cache
        'start_datetime': Arg(
            ("--start-datetime", ),
            "End limit time based operation",
            default=None,
            type=str,
            ),
        'end_datetime': Arg(
            ("--end-datetime", ),
            "End limit time based operation",
            default=None,
            type=str,
            ),
        'yes': Arg(
            ("-y", "--yes"),
            "Do not prompt to confirm reset. Use with care!",
            "store_true",
            default=False),

        # Execute
        'filename': Arg(
            ('-f', '--filename'),
            help='Path to file',
            required=True,
            type=str),
    }

    SUBPARSERS = (
        {
            'func': worker,
            'help': 'Run Worker',
            'args': ('verbose', 'db_host', 'db_port', 'db_user', 'db_password', 'kinds', 'api',
                     'storage_scheme', 'storage_prefix', 'credential_path'),
        }, {
            'func': api,
            'help': 'Run api server',
            'args': ('verbose', 'secret_key', 'endpoint',
                     'db_host', 'db_port', 'db_user', 'db_password',
                     'storage_scheme', 'storage_prefix', 'credential_path'),
        }, {
            'func': version,
            'help': "Show the version",
            'args': tuple(),
        }, {
            'func': users,
            'help': "Users cli utils",
            'args': ('verbose', 'mode', 'username', 'password', 'db_host'),
        }, {
            'func': cache,
            'help': "Cache cli utils",
            'args': ('verbose', 'mode', 'start_datetime', 'end_datetime', 'yes'),
        }, {
            'func': execute,
            'help': "Execute single node",
            'args': ('verbose', 'filename', 'storage_prefix'),
        },
    )

    @classmethod
    def parse_global_config_parameters(cls, args):
        """Parse parameters applied to all of the services."""
        remove = []
        for k, v in args.items():
            if cls.ARGS[k].levels:
                if v is not None:
                    # Do not set parameter if it is undefined
                    set_parameter(cls.ARGS[k].levels, v)
                remove.append(k)
        for k in remove:
            del args[k]

    @classmethod
    def get_parser(cls):
        """Generate CLI parser"""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(
            help='sub-command help', dest='subcommand')
        subparsers.required = True

        for sub in cls.SUBPARSERS:
            sp = subparsers.add_parser(sub['func'].__name__, help=sub['help'])
            for arg in sub['args']:
                arg = cls.ARGS[arg]
                kwargs = {
                    f: getattr(arg, f)
                    for f in arg.__dataclass_fields__ if f not in ['flags', 'levels'] and getattr(arg, f) is not None   # pylint: disable=no-member
                }
                sp.add_argument(*arg.flags, **kwargs)
            sp.set_defaults(func=sub['func'], args=sub['args'])

        return parser


def get_parser():
    """Generate CLI parser"""
    return CLIFactory.get_parser()
