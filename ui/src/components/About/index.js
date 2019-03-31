/* eslint max-len: 0 */
import React, { Component } from 'react';
import Highlight from 'react-syntax-highlight';

import './style.css';
import './python.css';

const pythonCode =
`#!/usr/bin/env python
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
# Build PLynx elements
##########################################

# Operation is a metaclass that declares the interface to an existing operation
# in the PLynx database
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

`;

export default class About extends Component {
  render() {
    return (
      <div className='About'>
        <div className='body'>
          <h1>
            About
          </h1>

          <p>PLynx is a domain agnostic platform for managing reproducible experiments and data-oriented workflows.</p>

          <h2>Core principles</h2>
          <ul>
            <li><strong>Flexibility: </strong>PLynx pipelines can be created and launched dynamically on the UI – no need to deploy code.</li>
            <li><strong>Scalability: </strong>PLynx is naturally distributed and horizontally scalable. With an arbitrary number of workers running in the cluster, the scheduler can find a worker for each task.</li>
            <li><strong>Reproducibility: </strong>Once you obtain your results, anyone can go back and reproduce them.</li>
          </ul>

          <h2>Architecture</h2>
          <img src='/architecture.png' alt="architecture" width="100%"/>

          <h3>UI</h3>
          <p>The PLynx UI make it easy to create, monitor, and troubleshoot your data pipelines. All of the components and Graphs can be defined in the UI.</p>

          <h3>API</h3>
          <p>While PLynx offers an excellent UI, PLynx API is the most common way of creating and running Graphs. Your pipeline can be defined in a python script.</p>
          <p>Yet PLynx is a PipeLine as a Service (PLaaS) platform. It means the pipelines are dynamic by their nature. The platform is separated from your data pipelines. An individual Graph can be altered to satisfy your business needs.</p>
          <p>The following python script builds the pipeline <b>&ldquo;WDBC: compare regressors&rdquo;</b> from the demo.</p>
          <Highlight lang={'python'} value={pythonCode} />

          <h3>Backend</h3>
          <p>The PLynx Backend is a RESTful web service. It has the same interface for UI and API.</p>

          <h3>Database</h3>
          <p>All of the data is stored in the database. It includes Graphs structures, Operations, and Files descriptions.</p>

          <h3>Master</h3>
          <p>The Master is a core element in pipeline orchestration. It automatically picks up unfinished graphs and determines which Operations need execution.</p>
          <p>A Scheduler will distribute computation across all active workers.</p>
          <p>If specified in Operations properties, the results of operations can be cached. In this case large bulks of the operations can reuse outputs computed before.</p>

          <h3>Workers</h3>
          <p>Workers are constantly collaborating with the Master. They always report their state and statuses of their jobs being executed.</p>
          <p>Different use cases might have different requirements to the Workers. Some of the operations might require certain GPU, or being closer to the cluster, or have extra libraries installed. The Master will make sure only the right Workers pick up the job.</p>

          <h3>Clusters of Workers</h3>
          <p>Some of the use cases will not require managing Workers directly and individually. In this case you might consider launching a single or multiple clusters.</p>
          <p>Workers can be run as Docker containers. It opens opportunities of using your own Kubernetes, or Mesos, or Swarm Clusters of Workers.</p>
          <p>Other use cases might consider launching a container on each request from the Master avoiding queues.</p>

        </div>
      </div>
    );
  }
}

// <p>PLynx offers an excellent UI that displays the states of the Operations, Files, and Graphs.</p>
