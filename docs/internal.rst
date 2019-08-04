
.. _plynx-internal:

========================
Internal data structures
========================

This section is meant for advanced users.
PLynx exposes Rest API for creating Graphs and Nodes and monitoring their states.
We will give you an overview of these objects below.

.. contents:: Table of Contents
    :local:
    :depth: 1

===========================


.. _plynx-internal-graph:

Graph
======================

Graph is a basic structure of experiments.
The Graph defines layout of Operations and Files and their dependancies.
See :ref:`intro-graph`.

+---------------+------------+----------------------------------------------------------------------+
| Field Name    | Type       | Description                                                          |
+===============+============+======================================================================+
| status        | ``STRING`` | Status of the query. One of the following: ``success`` or ``failed`` |
+---------------+------------+----------------------------------------------------------------------+
| message       | ``STRING`` | Extended status.                                                     |
+---------------+------------+----------------------------------------------------------------------+
| access_token  | ``STRING`` | Short-term token.                                                    |
+---------------+------------+----------------------------------------------------------------------+
| refresh_token | ``STRING`` | Long-term token.                                                     |
+---------------+------------+----------------------------------------------------------------------+
