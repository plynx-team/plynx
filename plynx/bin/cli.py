from __future__ import print_function
import argparse
from collections import namedtuple
from plynx import __version__
from plynx.utils.config import get_config, set_parameter
from plynx.service import run_master, run_worker, run_local
from plynx.web import run_backend
from plynx.utils.logs import set_logging_level


Arg = namedtuple(
    'Arg',
    ['flags', 'help', 'action', 'default', 'nargs', 'type', 'levels']
)
Arg.__new__.__defaults__ = (None, None, None, None, None, None)

_config = get_config()


def master(args):
    set_logging_level(args.pop('verbose'))
    run_master(**args)


def worker(args):
    set_logging_level(args.pop('verbose'))
    run_worker(**args)


def local(args):
    set_logging_level(args.get('verbose'))
    run_local(**args)


def backend(args):
    set_logging_level(args.pop('verbose'))
    run_backend(**args)


def version(args):
    print(__version__)


class CLIFactory(object):
    ARGS = {
        # Shared
        'verbose': Arg(
            ('-v', '--verbose'),
            help='Set logging output more verbose',
            default=0,
            action='count',
            ),

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
        'storage_resources': Arg(
            ('--storage-resources',),
            help='Storage resources',
            default=_config.storage.resources,
            type=str,
            levels=['storage', 'resources'],
            ),
        'storage_stdout': Arg(
            ('--storage-stdout',),
            help='Storage stdout',
            default=_config.storage.stdout,
            type=str,
            levels=['storage', 'stdout'],
            ),
        'storage_stderr': Arg(
            ('--storage-stderr',),
            help='Storage stderr',
            default=_config.storage.stderr,
            type=str,
            levels=['storage', 'stderr'],
            ),
        'storage_worker': Arg(
            ('--storage-worker',),
            help='Storage worker',
            default=_config.storage.worker,
            type=str,
            levels=['storage', 'worker'],
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
                     'storage_scheme', 'storage_resources', 'storage_stdout', 'storage_stderr', 'storage_worker'),
        }, {
            'func': backend,
            'help': 'Run backend server',
            'args': ('verbose', 'secret_key', 'endpoint',
                     'db_host', 'db_port', 'db_user', 'db_password',
                     'storage_scheme', 'storage_resources', 'storage_stdout', 'storage_stderr', 'storage_worker'),
        }, {
            'func': local,
            'help': 'Run local cluster. It consists of the database server, PLynx UI, backend, master and several workers',
            'args': ('verbose', 'num_workers', 'ignore_containers',
                     'internal_master_host', 'master_host', 'master_port', 'secret_key', 'endpoint',
                     'db_host', 'db_port', 'db_user', 'db_password',
                     'storage_scheme', 'storage_resources', 'storage_stdout', 'storage_stderr', 'storage_worker'),
        }, {
            'func': version,
            'help': "Show the version",
            'args': tuple(),
        }
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
