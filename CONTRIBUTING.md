# Contributing

First off, thanks for taking the time to contribute! :tada::+1:
We welcome community contributions to Plynx! :rocket:

This page describes how to develop/test your changes to Plynx locally and create Pull request. We will review your pull request as soon as possible.

The majority of the codebase is in Python and Javascript.
We are using PEP8 and ESLint respectively in order to keep the code style consistent.


## Setting up development environment

1. Please make sure you install docker first. [Get started with Docker](https://www.docker.com/get-started)
2. Fork and clone Plynx repo:
`$ git clone git@github.com:<username>/plynx.git`
3. Run the following command to start `development` environment: `$ make dev`

In the end you will have a local developer version of Plynx running on your machine.
Both front end and back end services will use `watchdog` so that any changes you make in your repository will be seen in the working service.
No need to rebuild your services running `make dev` unless you make a change in configuration.

## Submitting changes

1. Go to the [issue tracker](https://github.com/plynx-team/plynx/issues) and create a new issue.
2. Setup the development environment and prepare necessary changes.
3. Fork DVC and prepare necessary changes.
4. Add tests to your changes. You can skip this step if the effort to create tests for your change is unreasonable. Changes without tests are still going to be considered by us.
5. Run tests and make sure all of them pass: `$ make run_tests`
6. Submit a pull request, referencing any issues it addresses.

We will review your pull request as soon as possible.
Thank you for contributing!
Don't hesitate to contact us if you have any questions!
