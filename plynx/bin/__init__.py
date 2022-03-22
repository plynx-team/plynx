#!/usr/bin/env python
"""PLynx CLI."""
from plynx.bin.cli import CLIFactory


def main():
    """Main PLynx CLI function."""
    parser = CLIFactory.get_parser()
    args = parser.parse_args()
    kwargs = {
        k: v
        for k, v in vars(args).items() if k in args.args
    }
    CLIFactory.parse_global_config_parameters(kwargs)
    args.func(kwargs)
