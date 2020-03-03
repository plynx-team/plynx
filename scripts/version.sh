#!/bin/bash

function plynx_version() {
  python -c "import plynx; print(plynx.__version__)"
}
