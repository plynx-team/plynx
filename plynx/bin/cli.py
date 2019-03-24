from __future__ import print_function
import argparse
from collections import namedtuple
from plynx import __version__
from plynx.utils.config import get_config, set_parameter
from plynx.service import run_master, run_worker, run_local, run_users, run_cache
from plynx.web import run_backend
from plynx.utils.logs import set_logging_level


Arg = namedtuple(
    'Arg',
    ['flags', 'help', 'action', 'default', 'nargs', 'type', 'levels']
)
Arg.__new__.__defaults__ = (None, None, None, None, None, None)

_config = get_config()


def backend(args):
    set_logging_level(args.pop('verbose'))
    run_backend(**args)


def cache(args):
    set_logging_level(args.pop('verbose'))
    run_cache(**args)


def local(args):
    set_logging_level(args.get('verbose'))
    run_local(**args)


def master(args):
    set_logging_level(args.pop('verbose'))
    run_master(**args)


def users(args):
    run_users(**args)


def version(args):
    print(__version__)


def worker(args):
    set_logging_level(args.pop('verbose'))
    run_worker(**args)


class CLIFactory(object):
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

        # Master
        'master_host': Arg(
            ('-H', '--host'),
            help='Master host',
            default=_config.master.host,
            type=str,
            levels=['master', 'host'],
            ),
        'internal_master_host': Arg(
            ("--internal-master-host",),
            help="Internal Master host",
            default=_config.master.internal_host,
            type=str,
            levels=['master', 'internal_host'],
            ),
        'master_port': Arg(
            ("-P", "--port"),
            help="Master port",
            default=_config.master.port,
            type=int,
            levels=['master', 'port'],
            ),

        # Worker
        'worker_id': Arg(
            ('--worker-id',),
            help='Any string identificator',
            default='',
            type=str,
            ),

        # Local
        'num_workers': Arg(
            ('-n', '--num-workers'),
            help='Number of workers',
            default=3,
            type=int,
            ),
        'ignore_containers': Arg(
            ('--ignore-containers',),
            help='Do not instantiate docker containers',
            action='store_true'
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
            help='Secret Key (used in auth). If not given, a single user mode will be used.',
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
    }

    SUBPARSERS = (
        {
            'func': master,
            'help': 'Run Master',
            'args': ('verbose', 'internal_master_host', 'master_port', 'db_host', 'db_port', 'db_user', 'db_password'),
        }, {
            'func': worker,
            'help': 'Run Worker',
            'args': ('verbose', 'master_host', 'master_port', 'worker_id',
                     'storage_scheme', 'storage_prefix', 'credential_path'),
        }, {
            'func': backend,
            'help': 'Run backend server',
            'args': ('verbose', 'secret_key', 'endpoint',
                     'db_host', 'db_port', 'db_user', 'db_password',
                     'storage_scheme', 'storage_prefix', 'credential_path'),
        }, {
            'func': local,
            'help': 'Run local cluster. It consists of the database server, PLynx UI, backend, master and several workers',
            'args': ('verbose', 'num_workers', 'ignore_containers',
                     'internal_master_host', 'master_host', 'master_port', 'secret_key', 'endpoint',
                     'db_host', 'db_port', 'db_user', 'db_password',
                     'storage_scheme', 'storage_prefix', 'credential_path'),
        }, {
            'func': version,
            'help': "Show the version",
            'args': tuple(),
        }, {
            'func': users,
            'help': "Users cli utils",
            'args': ('mode', 'username', 'password'),
        }, {
            'func': cache,
            'help': "Cache cli utils",
            'args': ('verbose', 'mode', 'start_datetime', 'end_datetime', 'yes'),
        },
    )

    @classmethod
    def parse_global_config_parameters(cls, args):
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
                    for f in arg._fields if f not in ['flags', 'levels'] and getattr(arg, f) is not None
                }
                sp.add_argument(*arg.flags, **kwargs)
            sp.set_defaults(func=sub['func'], args=sub['args'])

        return parser


def get_parser():
    return CLIFactory.get_parser()
