
.. _plynx-overview:

===========================
Overview
===========================

.. image:: ./img/interactive_graph_editor.png
    :width: 700

PLynx is a high level domain agnostic orchestration and computation platform.
It is not constrained by a particular application and can be extended to custom data oriented workflows and experiments.

The platform abstracts users from the engineering and organizational complexities, such as data access, containerization, remote computation, automatic failover, progress monitoring, and other advanced computer science concepts.

The core principles of PLynx include:

- `Domain agnostic`. PLynx orchestrates multiple services with higher level APIs, such as various cloud services, version control repositories, databases and clusters.
- `Flexible experimentation`. Users are not limited by pre-defined experiment structure or approved operations. They are encouraged to reuse existing solutions, but if necessary they can introduce their solutions.
- `Reproducible experiments`. Results of each of the experiments are accessible and reusable. Past experiments and ideas can be reused anytime by anyone without technical challenges.
- `Parallel execution`. It is possible to conduct multiple experiments simultaneously.
- `Caching`. Results of previously executed Operations and subgraphs  will be reused.
- `Monitoring`. PLynx abstracts orchestration, visualization, workflow version control, sharing the results and others.


Demo
-------------------------
Demo is available at `https://plynx.com <https://plynx.com>`_.


Open source
-------------------------

PLynx is licensed under Apache 2.0.
Source code is available at `Github <https://github.com/plynx-team/plynx>`_.


Other links
-------------------------

Please refer to an article in `Medium <https://towardsdatascience.com/organizing-data-driven-experiments-with-plynx-a3cc3301b981>`_ about the goals of the project.
