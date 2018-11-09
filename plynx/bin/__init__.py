#!/usr/bin/env python
import os
from plynx.bin.cli import CLIFactory


def main():
    parser = CLIFactory.get_parser()
    args = parser.parse_args()
    args.func({
        k: v
        for k, v in vars(args).iteritems() if k in args.args
    })
