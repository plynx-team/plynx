Get started
===========

Run local cluster
-----------------

Make sure you install docker first. `Get started with Docker <https://docs.docker.com/install>`_

**tl;dr**

.. code-block:: bash

    git clone https://github.com/khaxis/plynx.git   # Clone the repo

    cd plynx

    make up                                         # to start production services

Then go to http://localhost:3001

It will start the following services:

 * MongoDB instance
 * PLynx User Interface
 * API service
 * DAG worker
 * Several Python and Bash workers (5 by default)

Run :code:`make down` to stop the services.

Other `make` commands
---------------------

- :code:`make build` - build all docker images.
- :code:`make run_tests` - build docker images and run the tests.
- :code:`make up` - run the services locally.
- :code:`make down` - shut down services.
- :code:`make dev` - run developer version of PLynx.
