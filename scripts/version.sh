#!/bin/bash

function plynx-version() {
  python -c "import plynx.bin; plynx.bin.main()" version
}
