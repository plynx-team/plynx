# PLynx

[![Website shields.io](https://img.shields.io/circleci/project/github/khaxis/plynx.svg)](https://circleci.com/gh/khaxis/plynx)
[![Website shields.io](https://img.shields.io/github/license/khaxis/plynx.svg)](https://github.com/khaxis/plynx)
[![Website shields.io](https://img.shields.io/pypi/pyversions/plynx.svg)](https://github.com/khaxis/plynx)


Website and demo: [plynx.com](https://plynx.com).

Docs: [docs](https://plynx.readthedocs.io/en/latest/overview.html).

PLynx is a domain agnostic platform for managing reproducible experiments and data-oriented workflows.

## Features

### Distributed computation

All of the computation is distributed across multiple workers. You can conduct multiple experiments simultaneously. Intermediate results will be stored in the cloud and reused. No need to start your experiment from scratch.

![Distributed computation](ui/public/architecture.png?raw=true "Distributed computation")

### Graph Editor

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


## Requirements

PLynx is a modular framework. Backend and Master, Worker and command line tool are written in `python`.

User Interface is based on `React` framework.

PLynx is using `MongoDB` as a primary metadata storage. In order to meet diverse data storage requirements, PLynx is using `boto` library as an abstractions. It supports multiple data storages such as `AWS S3`, `Google Cloud Storage` and traditional filesystems.

In order to reduce complexity we recommend to install `docker` framework.


## Get started

### Usage

Make sure you install docker. [Get started with Docker](https://www.docker.com/get-started)

**tl;dr**
```
git clone https://github.com/khaxis/plynx.git   # Clone the repo

cd plynx

make up                                         # to start production services
```

Then go to [http://localhost:3001](http://localhost:3001)

By default it will start the following services:

 * MongoDB instance
 * PLynx User Interface
 * Backend
 * Master
 * Several workers (5 by default)

Run `make down` to stop the services.

### Other `make` commands:

- `make build` - build all docker images.
- `make run_tests` - build docker images and run the tests.
- `make up` - run the services locally.
- `make down` - shut down services.
- `make dev` - run developer version of PLynx.

## PLynx API

Web User Interface is not the only way to create Graphs. Some of the experiments are easier to create using PLynx API:

```
#!/usr/bin/env python
# “WDBC: compare regressors” example
from collections import namedtuple
from plynx import Operation, File, Graph, Client

# define the training parameters
TrainDescriptor = namedtuple('TrainDescriptor', ['method', 'parameters'])
train_descriptors = [
    TrainDescriptor(method='GradientBoostingRegressor', parameters='100'),
    TrainDescriptor(method='MLPRegressor', parameters='100 10'),
    TrainDescriptor(method='MLPRegressor', parameters='100 8'),
    TrainDescriptor(method='MLPRegressor', parameters='80 10')
]

##########################################
# Build Plynx elements
##########################################

# Operation is a metaclass that declares the interface to an existing operation
# in the Plynx database
Split = Operation(
    id='5ae6b0123136050000d8711a',
    title='Split Train Test',
    inputs=['sample.py', 'data'],
    params=['rate', 'seed'],
    outputs=['train', 'test']
)

TrainRegression = Operation(
    id='5ae6b023d26111000027a613',
    title='Train regression',
    inputs=['train.py', 'data'],
    params=['regressor', 'hidden-layer-sizes'],
    outputs=['model']
)

Predict = Operation(
    id='5ae6b02f0164d80000afd938',
    title='Predict',
    inputs=['predict.py', 'data', 'model'],
    outputs=['prediction']
)

Compare = Operation(
    id='5aeaa49c16b8b50000abca48',
    title='Compare regressors',
    inputs=['build_roc.py', 'predictions'],
    outputs=['plot.png']
)

# define Files
wdbc_dataset = File(id='5ad42a2cfad58d1cc6c9f7b5')
sample_py = File(id='5ad42da1fad58d1cc6c9f7c4')
train_py = File(id='5aeaa42bfad58d7d05d632db')
predict_py = File(id='5aeaa455fad58d7d05d632e0')
build_plot_py = File(id='5aeaa483fad58d7d05d632e5')


##########################################
# Build pipeline
##########################################

# first split the dataset
split_block = Split(
    sample.py=sample_py.outputs.out,
    data=wdbc_dataset.outputs.out,
    rate=0.7
)

# run training algorithms with specified parameters
predictions = []
for descriptor in train_descriptors:
    train = TrainRegression(
        train_py=train_py.outputs.out
        data=split_block.outputs.train,
        regressor=descriptor.method,
        hidden_layer_sizes=descriptor.parameters
    )

    predict = Predict(
        predict_py=predict_py.outputs.out,
        data=split_block.outputs.test,
        model=train.outputs.model
    )

    predictions.append(predict.outputs.prediction)

# join 'predictions' in the report file
compare_models = Compare(
    build_roc_py=build_plot_py.outputs.out,
    predictions=predictions
)

# build the Graph
graph = Graph(
    Client(),
    title='WDBC: compare regressors',
    description='Wisconsin Diagnostic Breast Cancer',
    targets=[compare_models]
)

##########################################
# Run pipeline
##########################################

# Approve the Graph and wait until it finishes
graph.approve().wait()

```

### Config

All of the parameters can be set in command line when the services are called. For example:
```
$ plynx master --help
usage: plynx master [-h] [-v] [--internal-master-host INTERNAL_MASTER_HOST]
                    [-P PORT] [--db-host DB_HOST] [--db-port DB_PORT]
                    [--db-user DB_USER] [--db-password DB_PASSWORD]

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Set logging output more verbose
  --internal-master-host INTERNAL_MASTER_HOST
                        Internal Master host
  -P PORT, --port PORT  Master port
  --db-host DB_HOST     Database host
  --db-port DB_PORT     Database port
  --db-user DB_USER     Database username
  --db-password DB_PASSWORD
                        Database password
```

Yet it is almost always more convenient to store the config in a separate file.

PLynx config is located at Env variable `PLYNX_CONFIG_PATH`. If the variable is not defined, PLynx will use a file `config.yaml` in the local directory.

Here is an example of a `config.yaml`:
```
mongodb:
  user:
  password:
  host: 'mongodb'
  port: 27017

master:
  internal_host: '0.0.0.0'
  host: 'master'
  port: 17011

worker:
  user:

storage:
  scheme: file
  prefix: /data/resources/

auth:
  secret_key: SECRET_KEY

web:
  host: '0.0.0.0'
  port: 5000
  endpoint: http://localhost:3001
  debug: true

demo:
  graph_ids: []

```

## External links
- [PLynx.com](https://plynx.com) demo and main page.
- [github](https://github.com/khaxis/plynx) page.
- [Medium article](https://medium.com/@khaxis/organizing-data-driven-experiments-with-plynx-a3cc3301b981)
