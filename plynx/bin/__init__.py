#!/usr/bin/env python
from plynx.bin.cli import CLIFactory


def main():
    parser = CLIFactory.get_parser()
    args = parser.parse_args()
    kwargs = {
        k: v
        for k, v in vars(args).items() if k in args.args
    }
    CLIFactory.parse_global_config_parameters(kwargs)
    args.func(kwargs)
