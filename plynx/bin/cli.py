from __future__ import print_function
import argparse
from collections import namedtuple
import plynx
from plynx.utils.config import get_config
from plynx.service import run_master, run_worker
from plynx.utils.logs import set_logging_level


Arg = namedtuple(
    'Arg',
    ['flags', 'help', 'action', 'default', 'nargs', 'type']
)
Arg.__new__.__defaults__ = (None, None, None, None, None, None)

_config = get_config()


def master(args):
    set_logging_level(args.pop('verbose', 0))
    run_master(**args)


def worker(args):
    set_logging_level(args.pop('verbose', 0))
    run_worker(**args)


def version(args):
    print('PLynx version: {}'.format(plynx.__version__))


class CLIFactory(object):
    ARGS = {
        # Shared
        'verbose': Arg(
            ('-v', '--verbose'),
            help='Set logging output more verbose',
            action='count',
            default=0,
            ),
        'host': Arg(
            ('-H', '--host'),
            help='Host Master',
            default=_config.master.host,
            type=str,
            ),
        'port': Arg(
            ("-P", "--port"),
            default=_config.master.port,
            type=int,
            help="Port of Master"),

        # Worker
        'worker_id': Arg(
            ('--worker-id',),
            default='',
            help='Any string identificator',
            type=str,
            ),
    }

    SUBPARSERS = (
        {
            'func': master,
            'help': 'Run Master',
            'args': ('verbose', 'host', 'port'),
        }, {
            'func': worker,
            'help': 'Run Worker',
            'args': ('verbose', 'host', 'port', 'worker_id'),
        }, {
            'func': version,
            'help': "Show the version",
            'args': tuple(),
        }
    )

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
                    for f in arg._fields if f != 'flags' and getattr(arg, f)
                }
                sp.add_argument(*arg.flags, **kwargs)
            sp.set_defaults(func=sub['func'], args=sub['args'])

        return parser


def get_parser():
    return CLIFactory.get_parser()
