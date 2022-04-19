# Plynx

![Plynx](docs/img/logo-black-font.png?style=centerme)

[![Website shields.io](https://img.shields.io/circleci/project/github/plynx-team/plynx.svg)](https://circleci.com/gh/plynx-team/plynx)
[![Website shields.io](https://img.shields.io/github/license/plynx-team/plynx.svg)](https://github.com/plynx-team/plynx)
[![Website shields.io](https://img.shields.io/pypi/pyversions/plynx.svg)](https://github.com/plynx-team/plynx)


Website and demo: [plynx.com](https://plynx.com).

Docs: [docs](https://plynx.readthedocs.io/en/latest/overview.html).

PLynx is a domain agnostic platform for managing reproducible experiments and data-oriented workflows.

## Features

### Workflow Editor

Interactive User Interface. You can clone successful experiment and reuse it or create one from scratch. PLynx manages history of the experiments and they can be reproduced.

![interactive graph editor](docs/img/interactive_graph_editor.png?raw=true "Interactive graph editor")

### Operations editor

Operations can be customized independently from the platform. Users can define their own Operations or reuse existing ones.

![online editor](docs/img/online_code_editor.png?raw=true "Online Code editor")

### Monitor progress

Track the progress of the experiment. Each of intermediate operations produce results that you can inspect.

![monitor progress](docs/img/monitor_progress.png?raw=true "Monitor Progress")

### Preview the results

View the results right in the browser.

![results preview](docs/img/results_preview.png?raw=true "Results preview")

### Scalable architecture

Execution Engine is based on scalable pub/sub model. Each Worker performs their jobs independently from each other and can publish subtasks back to the queue. Executers are plugins themselves and can support multiple scenarios from "compile to binary code" to "deploy and serve" to "run in a cluster using as many distributed workers as possible".

![Scalable architecture](docs/img/plynx-architecture.png?raw=true "Scalable architecture")

## Requirements

Plugins work on python3. User Interface is based on `React`. PLynx is using `MongoDB` as a primary metadata storage. In order to meet diverse data storage requirements, its own storage plugins to store the artifacts. It supports multiple data storages such as `AWS S3`, `Google Cloud Storage` and traditional filesystems.

In order to reduce complexity we recommend to install `docker` and run `make` command to start local cluster.


## Get started

### Usage

Make sure you install docker first. [Get started with Docker](https://www.docker.com/get-started)

**tl;dr**
```
git clone https://github.com/plynx-team/plynx.git   # Clone the repo

cd plynx

cp template_config.yaml config.yaml                 # Make a copy of a config
make up                                             # to start production services
```

Then go to [http://localhost:3001](http://localhost:3001)

By default it will start the following services:

 * MongoDB instance
 * PLynx User Interface
 * Backend
 * Several workers

### Other `make` commands:

- `make build` - build all docker images.
- `make run_tests` - build docker images and run the tests.
- `make up` - run the services locally.
- `make dev` - run developer version of PLynx.


### Config

Most of the parameters can be set in command line when the services are called. For example:
```
$ plynx exec --help
usage: -c exec [-h] [-v] -f FILENAME [--storage-prefix STORAGE_PREFIX]

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Set logging output more verbose
  -f FILENAME, --filename FILENAME
                        Path to file
  --storage-prefix STORAGE_PREFIX
                        Storage prefix
```

But we recommend to store the config in a separate file.

Plynx config location is can be set in env variable `PLYNX_CONFIG_PATH`. Default value is `./config.yaml`.


### Install PLynx with dev requirements

Run:
```
pip install -e .[all]

pre-commit install
```

## External links
- [PLynx.com](https://plynx.com) demo and main page.
- [github](https://github.com/plynx-team/plynx) page.
- [Organizing data science experiments with PLynx](https://medium.com/@khaxis/organizing-data-driven-experiments-with-plynx-a3cc3301b981)
