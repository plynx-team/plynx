#!/bin/bash

function plynx_version() {
  python -c "import plynx.bin; plynx.bin.main()" version
}
