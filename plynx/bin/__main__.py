#!/usr/bin/env python
import os
from plynx.bin.cli import CLIFactory

if __name__ == '__main__':
    parser = CLIFactory.get_parser()
    args = parser.parse_args()
    args.func({
        k: v
        for k, v in vars(args).iteritems() if k in args.args
    })
