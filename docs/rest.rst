
.. warning::

   API docs are outdated. Please contact us for details.

.. _plynx-rest:

========
REST API
========


The PLynx REST API allows you to perform most of the actions with Graphs, Operations and Files.
The API is hosted under the ``/plynx/api/v0`` route on the PLynx server.
For example, to list latest Graphs on backend server hosted at ``http://localhost:5000``, make GET request: ``http://localhost:5000/plynx/api/v0/graphs``.

.. contents:: Table of Contents
    :local:
    :depth: 1

===========================


.. _plynx-rest-get-token:

Authentication
======================

User session should start with this endpoint.
If a user if is verified, response will contain access and refresh tokens.

+------------------------+-------------+
| Endpoint               | HTTP Method |
+========================+=============+
| ``plynx/api/v0/token`` | ``GET``     |
+------------------------+-------------+

Response Structure
------------------

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



.. _plynx-rest-get-graphs:

List multiple Graphs
====================


+--------------------------------+-------------+
| Endpoint                       | HTTP Method |
+================================+=============+
| ``plynx/api/v0/search_graphs`` | ``POST``    |
+--------------------------------+-------------+
Get a list of Graphs. You can specify search parameters as a request body, for example:

.. code-block:: json

  {
     "per_page": 20,
     "offset": 0,
     "search":"author:default "
  }


Request Structure
-----------------



+----------------+------------------------+---------------+------------------------------------------------------------------------------------+
| Parameter name | Type                   | Default value | Description                                                                        |
+================+========================+===============+====================================================================================+
| search         | ``STRING``             | ``""``        | Search string. See :ref:`plynx-internal-search-string` for more details.           |
+----------------+------------------------+---------------+------------------------------------------------------------------------------------+
| per_page       | ``INTEGER``            | ``20``        | Number of instances returned by the query.                                         |
+----------------+------------------------+---------------+------------------------------------------------------------------------------------+
| offset         | ``INTEGER``            | ``0``         | Number of instances to skip.                                                       |
+----------------+------------------------+---------------+------------------------------------------------------------------------------------+
| status         | ``STRING`` or ``LIST`` | ``[]``        | List of statuses. See :ref:`plynx-internal-graph_running_status` for more details. |
+----------------+------------------------+---------------+------------------------------------------------------------------------------------+




Response Structure
------------------

+-------------+-----------------------------------------+----------------------------------------------------------------------+
| Field Name  | Type                                    | Description                                                          |
+=============+=========================================+======================================================================+
| items       | An array of :ref:`plynx-internal-graph` | All experiments.                                                     |
+-------------+-----------------------------------------+----------------------------------------------------------------------+
| total_count | ``INTEGER``                             | Total number of graphs that meet the query.                          |
+-------------+-----------------------------------------+----------------------------------------------------------------------+
| status      | ``STRING``                              | Status of the query. One of the following: ``success`` or ``failed`` |
+-------------+-----------------------------------------+----------------------------------------------------------------------+




Example
----------------

.. code-block:: bash

    curl -X POST \
        'http://localhost:5000/plynx/api/v0/search_graphs' \
        -u default: -H "Content-Type: application/json" \
        -d '{"per_page":1, "search":"author:default"}'




.. _plynx-rest-get-graph:

Get single Graph
====================


+------------------------------------+-------------+
| Endpoint                           | HTTP Method |
+====================================+=============+
| ``plynx/api/v0/graphs/{graph_id}`` | ``GET``     |
+------------------------------------+-------------+


Get a single Graph in :ref:`plynx-internal-graph` format.

Parameter ``graph_id`` is required.

When ``graph_id == "new"`` (i.e. ``curl 'http://localhost:5000/plynx/api/v0/graphs/new' -u default:``) PLynx backend will generate a default empty Graph.
Please note this new Graph will not be saved in the database. Use POST request instead :ref:`plynx-rest-post_graph:`



Response Structure
------------------

+----------------+--------------------------------------+----------------------------------------------------------------------+
| Field Name     | Type                                 | Description                                                          |
+================+======================================+======================================================================+
| data           | :ref:`plynx-internal-graph`          | Graph object.                                                        |
+----------------+--------------------------------------+----------------------------------------------------------------------+
| resources_dict | :ref:`plynx-internal-resources_dict` | Dictionary of available resources types that come as plugins.        |
+----------------+--------------------------------------+----------------------------------------------------------------------+
| status         | ``STRING``                           | Status of the query. One of the following: ``success`` or ``failed`` |
+----------------+--------------------------------------+----------------------------------------------------------------------+



Example
----------------

.. code-block:: bash

    curl 'http://localhost:5000/plynx/api/v0/graphs/5d1b8469705c1865e288a664' -u default:




.. _plynx-rest-post_graph:

Post Graph
====================


+-------------------------+-------------+
| Endpoint                | HTTP Method |
+=========================+=============+
| ``plynx/api/v0/graphs`` | ``POST``    |
+-------------------------+-------------+




This endpoint covers multiple actions with a Graph, such as saving, approving, generating code, etc.
A single request can contain a sequence of actions that will be applied in the same order.

Note that some of the actions that require a change in the database, are not always permitted.
For example when the user is not the original author of the Graph. In this case the Graph is considered as ``read only``.

Data
-----------------

+----------------+-----------------------------+-----------------------------------------------------------------------------+
| Parameter name | Type                        | Description                                                                 |
+================+=============================+=============================================================================+
| graph          | :ref:`plynx-internal-graph` | Graph object.                                                               |
+----------------+-----------------------------+-----------------------------------------------------------------------------+
| action         | ``LIST`` of ``STRING``      | List of actions. See :ref:`plynx-rest-post_graph_actions` for more details. |
+----------------+-----------------------------+-----------------------------------------------------------------------------+




.. _plynx-rest-post_graph_actions:

Actions
-----------------

+---------------+-----------------------------------------------------------------------------------+------------------------------------+--------------------------+
| Action Name   | Description                                                                       | Permission limitations             | Extra fields in response |
+===============+===================================================================================+====================================+==========================+
| SAVE          | Save the graph. If the Graph with the same Id does not exist, it will be created. | Author must match the current user |                          |
+---------------+-----------------------------------------------------------------------------------+------------------------------------+--------------------------+
| APPROVE       | Save the graph and execute it if it passes validation.                            | Author must match the current user | ``validation_error``     |
+---------------+-----------------------------------------------------------------------------------+------------------------------------+--------------------------+
| VALIDATE      | Check if the Graph passes validation, i.e. cycles detected, invalid inputs, etc.  | Any User                           | ``validation_error``     |
+---------------+-----------------------------------------------------------------------------------+------------------------------------+--------------------------+
| REARRANGE     | Rearrange Nodes based on topology of the Graph.                                   | Any User                           |                          |
+---------------+-----------------------------------------------------------------------------------+------------------------------------+--------------------------+
| UPGRADE_NODES | Replace outdated nodes with new versions                                          | Any User                           | ``upgraded_nodes_count`` |
+---------------+-----------------------------------------------------------------------------------+------------------------------------+--------------------------+
| CANCEL        | Cancel currently running Graph.                                                   | Author must match the current user |                          |
+---------------+-----------------------------------------------------------------------------------+------------------------------------+--------------------------+
| GENERATE_CODE | Generate python API code that can recreate the same graph.                        | Any User                           | ``code``                 |
+---------------+-----------------------------------------------------------------------------------+------------------------------------+--------------------------+
| CLONE         | Clone the graph and save it.                                                      | Any User                           | ``new_graph_id``         |
+---------------+-----------------------------------------------------------------------------------+------------------------------------+--------------------------+

Response Structure
------------------

+------------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| Field Name                   | Type                                               | Description                                                                                   |
+==============================+====================================================+===============================================================================================+
| graph                        | :ref:`plynx-internal-graph`                        | Graph object.                                                                                 |
+------------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| url                          | ``STRING``                                         | URL.                                                                                          |
+------------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| message                      | ``STRING``                                         | Dictionary of available resources types that come as plugins.                                 |
+------------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| status                       | ``STRING``                                         | Status of the query. One of the following: ``success`` or ``failed`` or ``validation_failed`` |
+------------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| validation_error (extra)     | An array of :ref:`plynx-internal-validation_error` | If errors found on validation step.                                                           |
+------------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| upgraded_nodes_count (extra) | ``INTEGER``                                        | Dictionary of available resources types that come as plugins.                                 |
+------------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| code (extra)                 | ``STRING``                                         | Resulting code                                                                                |
+------------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+




.. _plynx-rest-post_graph_single_action:

Single action endpoints
========================================

Similarly to :ref:`plynx-rest-post_graph_actions`, you can perform actions with existing Graphs.
These POST-requests do not require json data. Backend will use existing Graph instead.

+--------------------------------------------------+-------------+------+
| Endpoint                                         | HTTP Method | Data |
+==================================================+=============+======+
| ``plynx/api/v0/graphs/{graph_id}/approve``       | ``POST``    | None |
+--------------------------------------------------+-------------+------+
| ``plynx/api/v0/graphs/{graph_id}/validate``      | ``POST``    | None |
+--------------------------------------------------+-------------+------+
| ``plynx/api/v0/graphs/{graph_id}/rearrange``     | ``POST``    | None |
+--------------------------------------------------+-------------+------+
| ``plynx/api/v0/graphs/{graph_id}/upgrade_nodes`` | ``POST``    | None |
+--------------------------------------------------+-------------+------+
| ``plynx/api/v0/graphs/{graph_id}/cancel``        | ``POST``    | None |
+--------------------------------------------------+-------------+------+
| ``plynx/api/v0/graphs/{graph_id}/generate_code`` | ``POST``    | None |
+--------------------------------------------------+-------------+------+
| ``plynx/api/v0/graphs/{graph_id}/clone``         | ``POST``    | None |
+--------------------------------------------------+-------------+------+

Additional PATCH endpoint is available to update the Graph.

+-------------------------------------------+-------------+----------------+
| Endpoint                                  | HTTP Method | Data           |
+===========================================+=============+================+
| ``plynx/api/v0/graphs/{graph_id}/update`` | ``PATCH``   | JSON, required |
+-------------------------------------------+-------------+----------------+

Example
----------------

.. code-block:: bash

    # Clone existing Graph
    curl -X POST \
        'http://localhost:5000/plynx/api/v0/graphs/5d1b8469705c1865e288a664/clone' \
        -u default:
    # {"status": "SUCCESS", "message": "Actions completed with Graph(_id=`5d1b8469705c1865e288a664`)", "graph": {"_id": "5d291e57713b286094d4ad85", "title": "hello world", "description": "Description", "graph_running_status": "CREATED", "author": "5d0686aa52691468eaef391c", "nodes": [{"_id": "5d27e3bd0f432b5e3693314c", "title": "Sum", "description": "Sum values", "base_node_name": "python", "parent_node": "5d27b8dd50e56dbbce063449", "successor_node": null, "inputs": [{"name": "input", "file_types": ["file"], "values": [], "min_count": 1, "max_count": -1}], "outputs": [{"name": "output", "file_type": "file", "resource_id": null}], "parameters": [{"name": "cmd", "parameter_type": "code", "value": {"value": "s = 0\nfor filename in input[\"input\"]:\n    with open(filename) as fi:\n        s += sum([int(line) for line in fi])\nwith open(output[\"output\"], \"w\") as fo:\n    fo.write(\"{}\\n\".format(s))\n", "mode": "python"}, "mutable_type": false, "removable": false, "publicable": false, "widget": null}, {"name": "cacheable", "parameter_type": "bool", "value": true, "mutable_type": false, "removable": false, "publicable": false, "widget": null}], "logs": [{"name": "stderr", "file_type": "file", "resource_id": null}, {"name": "stdout", "file_type": "file", "resource_id": null}, {"name": "worker", "file_type": "file", "resource_id": null}], "node_running_status": "CREATED", "node_status": "READY", "cache_url": "", "x": 190, "y": 143, "author": "5d0686aa52691468eaef391c", "starred": false}]}, "url": "http://localhost:3001/graphs/5d291e57713b286094d4ad85", "new_graph_id": "5d291e57713b286094d4ad85"}

    # Change Title and Description
    # Note "new_graph_id": "5d291e57713b286094d4ad85"
    curl -X PATCH \
        'http://localhost:5000/plynx/api/v0/graphs/5d1b8469705c1865e288a664/update' \
        -u default: -H "Content-Type: application/json" \
        -d '{"title": "Custom title", "description":"Custom Description"}'

    # Execute the Graph:
    curl -X POST \
        'http://localhost:5000/plynx/api/v0/graphs/5d1b8469705c1865e288a664/approve' \
        -u default:






.. _plynx-rest-get_nodes:

List multiple Nodes
====================

Note Files and Operations internally are represented as Nodes.

+-------------------------------+-------------+
| Endpoint                      | HTTP Method |
+===============================+=============+
| ``plynx/api/v0/search_nodes`` | ``POST``    |
+-------------------------------+-------------+



Get a list of Nodes. You can specify search parameters as a request body, for example:

.. code-block:: json

  {
     "per_page": 20,
     "offset": 0,
     "search":"author:default "
  }


Request Structure
-----------------



+-----------------+---------------------------------------------+---------------+---------------------------------------------------------------------------+
| Parameter name  | Type                                        | Default value | Description                                                               |
+=================+=============================================+===============+===========================================================================+
| search          | ``STRING``                                  | ``""``        | Search string. See :ref:`plynx-internal-search-string` for more details.  |
+-----------------+---------------------------------------------+---------------+---------------------------------------------------------------------------+
| per_page        | ``INTEGER``                                 | ``20``        | Number of instances returned by the query.                                |
+-----------------+---------------------------------------------+---------------+---------------------------------------------------------------------------+
| offset          | ``INTEGER``                                 | ``0``         | Number of instances to skip.                                              |
+-----------------+---------------------------------------------+---------------+---------------------------------------------------------------------------+
| status          | ``STRING`` or ``LIST``                      | ``[]``        | List of statuses. See :ref:`plynx-internal-node_status` for more details. |
+-----------------+---------------------------------------------+---------------+---------------------------------------------------------------------------+
| base_node_names | ``LIST`` of :ref:`plynx-internal-base_node` | ``[]``        | List of base nodes. See :ref:`plynx-internal-base_node` for more details. |
+-----------------+---------------------------------------------+---------------+---------------------------------------------------------------------------+




Response Structure
------------------

+----------------+--------------------------------------------------+----------------------------------------------------------------------+
| Field Name     | Type                                             | Description                                                          |
+================+==================================================+======================================================================+
| items          | An array of :ref:`plynx-internal-node`           | Nodes (Operations and Files)                                         |
+----------------+--------------------------------------------------+----------------------------------------------------------------------+
| resources_dict | An array of :ref:`plynx-internal-resources_dict` | List of resources available in the platform.                         |
+----------------+--------------------------------------------------+----------------------------------------------------------------------+
| total_count    | ``INTEGER``                                      | Total number of nodes that meet the query.                           |
+----------------+--------------------------------------------------+----------------------------------------------------------------------+
| status         | ``STRING``                                       | Status of the query. One of the following: ``success`` or ``failed`` |
+----------------+--------------------------------------------------+----------------------------------------------------------------------+




Example
----------------

.. code-block:: bash

    curl -X POST \
        'http://localhost:5000/plynx/api/v0/search_nodes' \
        -u default: -H "Content-Type: application/json" \
        -d '{"per_page":1, "search":"author:default"}'



.. _plynx-rest-get_node:

Get single Node
====================


+----------------------------------+-------------+
| Endpoint                         | HTTP Method |
+==================================+=============+
| ``plynx/api/v0/nodes/{node_id}`` | ``GET``     |
+----------------------------------+-------------+




Get a single Graph in :ref:`plynx-internal-node` format.

There are special cases when `node_id` is `base_node_name`, i.e. ``curl 'http://localhost:5000/plynx/api/v0/nodes/python'`` or ``curl 'http://localhost:5000/plynx/api/v0/nodes/bash_jinja2'``.
Backend will generate a default Operation.


Response Structure
------------------

+----------------+--------------------------------------+----------------------------------------------------------------------+
| Field Name     | Type                                 | Description                                                          |
+================+======================================+======================================================================+
| data           | :ref:`plynx-internal-node`           | Node object.                                                         |
+----------------+--------------------------------------+----------------------------------------------------------------------+
| resources_dict | :ref:`plynx-internal-resources_dict` | Dictionary of available resources types that come as plugins.        |
+----------------+--------------------------------------+----------------------------------------------------------------------+
| status         | ``STRING``                           | Status of the query. One of the following: ``success`` or ``failed`` |
+----------------+--------------------------------------+----------------------------------------------------------------------+






Example
----------------

.. code-block:: bash

    curl 'http://localhost:5000/plynx/api/v0/nodes/5d27b8dd50e56dbbce063449' -u default:



.. _plynx-rest-post_node:

Post Node
====================


+------------------------+-------------+
| Endpoint               | HTTP Method |
+========================+=============+
| ``plynx/api/v0/nodes`` | ``POST``    |
+------------------------+-------------+


This endpoint covers multiple actions with a Node, such as saving, approving, deprecating, etc.

Note that some of the actions that require a change in the database, are not always permitted.
For example when the user is not the original author of the Node. In this case the Node is considered as ``read only``.

Data
-----------------

+----------------+----------------------------+----------------------------------------------------------------------------+
| Parameter name | Type                       | Description                                                                |
+================+============================+============================================================================+
| node           | :ref:`plynx-internal-node` | Node object.                                                               |
+----------------+----------------------------+----------------------------------------------------------------------------+
| action         | ``STRING``                 | List of actions. See :ref:`plynx-rest-post_node_actions` for more details. |
+----------------+----------------------------+----------------------------------------------------------------------------+




.. _plynx-rest-post_node_actions:

Actions
-----------------

+---------------------+---------------------------------------------------------------------------------+------------------------------------+--------------------------+
| Action Name         | Description                                                                     | Permission limitations             | Extra fields in response |
+=====================+=================================================================================+====================================+==========================+
| SAVE                | Save the Node. If the Node with the same Id does not exist, it will be created. | Author must match the current user |                          |
+---------------------+---------------------------------------------------------------------------------+------------------------------------+--------------------------+
| APPROVE             | Save the Node and make accessible in Graphs if it passes validation.            | Author must match the current user | ``validation_error``     |
+---------------------+---------------------------------------------------------------------------------+------------------------------------+--------------------------+
| VALIDATE            | Check if the Node passes validation, i.e. incorrect parameter values.           | Any User                           | ``validation_error``     |
+---------------------+---------------------------------------------------------------------------------+------------------------------------+--------------------------+
| DEPRECATE           | Deprecate the Node. User will still be able to use it.                          | Author must match the current user |                          |
+---------------------+---------------------------------------------------------------------------------+------------------------------------+--------------------------+
| MANDATORY_DEPRECATE | Deprecate the Node mandatory. Users will no longer be able to use it.           | Author must match the current user | ``validation_error``     |
+---------------------+---------------------------------------------------------------------------------+------------------------------------+--------------------------+
| PREVIEW_CMD         | Preview exec script.                                                            | Any User                           | ``validation_error``     |
+---------------------+---------------------------------------------------------------------------------+------------------------------------+--------------------------+




Response Structure
------------------

+--------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| Field Name               | Type                                               | Description                                                                                   |
+==========================+====================================================+===============================================================================================+
| node                     | :ref:`plynx-internal-node`                         | Node object.                                                                                  |
+--------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| url                      | ``STRING``                                         | URL.                                                                                          |
+--------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| message                  | ``STRING``                                         | Extended status.                                                                              |
+--------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| status                   | ``STRING``                                         | Status of the query. One of the following: ``success`` or ``failed`` or ``validation_failed`` |
+--------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| validation_error (extra) | An array of :ref:`plynx-internal-validation_error` | If errors found on validation step.                                                           |
+--------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+
| preview_text (extra)     | ``STRING``                                         | Resulting code.                                                                               |
+--------------------------+----------------------------------------------------+-----------------------------------------------------------------------------------------------+




.. _plynx-rest-upload_file:

Upload File
====================

This endpoint will create a new Node with type `File`.
If you work with large files it is recommended to use an external file storage and Operation that downloads the file (i.e. S3).

+------------------------------+---------------------+-----------------+
| Endpoint                     | HTTP Method         | Data            |
+==============================+=====================+=================+
| ``plynx/api/v0/upload_file`` | ``POST`` or ``PUT`` | Forms, required |
+------------------------------+---------------------+-----------------+



+-------------+-----------------------------------------+
| Form        | Description                             |
+=============+=========================================+
| data        | Binary data of the file.                |
+-------------+-----------------------------------------+
| title       | Title of the file                       |
+-------------+-----------------------------------------+
| description | Description of the file                 |
+-------------+-----------------------------------------+
| file_type   | Type, i.e. `file`, `csv`, `image`, etc. |
+-------------+-----------------------------------------+



Example
----------------

.. code-block:: bash

    curl \
        -X POST \
        'http://localhost:5000/plynx/api/v0/upload_file' \
        -u default: \
        -H "Content-Type: multipart/form-data" \
        -F data=@/tmp/a.csv \
        -F title=report \
        -F description=2019 \
        -F file_type=csv




.. _plynx-rest-graph_node_operations:

Modify existing Graphs
==========================

+-------------------------------------------------------------+-------------+------------------------------------------------------------+
| Endpoint                                                    | HTTP Method | Data                                                       |
+=============================================================+=============+============================================================+
| ``plynx/api/v0/graphs/{graph_id}/nodes/list_nodes``         | ``GET``     | `None`                                                     |
+-------------------------------------------------------------+-------------+------------------------------------------------------------+
| ``plynx/api/v0/graphs/{graph_id}/nodes/insert_node``        | ``POST``    | `node_id: required.`                                       |
|                                                             |             |                                                            |
|                                                             |             | `x: optional.` Default: 0.                                 |
|                                                             |             |                                                            |
|                                                             |             | `y: optional.` Default: 0.                                 |
+-------------------------------------------------------------+-------------+------------------------------------------------------------+
| ``plynx/api/v0/graphs/{graph_id}/nodes/remove_node``        | ``POST``    | `node_id: required.`                                       |
+-------------------------------------------------------------+-------------+------------------------------------------------------------+
| ``plynx/api/v0/graphs/{graph_id}/nodes/create_link``        | ``POST``    | `from: required. Type: Object.` Output node description.   |
|                                                             |             |                                                            |
|                                                             |             | `from.node_id: required.`                                  |
|                                                             |             |                                                            |
|                                                             |             | `from.resource: required.` Name of the Output              |
|                                                             |             |                                                            |
|                                                             |             | `to: required. Type: Object.` Input node description.      |
|                                                             |             |                                                            |
|                                                             |             | `to.node_id: required.`                                    |
|                                                             |             |                                                            |
|                                                             |             | `to.resource: required.` Name of the Input                 |
+-------------------------------------------------------------+-------------+------------------------------------------------------------+
| ``plynx/api/v0/graphs/{graph_id}/nodes/remove_link``        | ``POST``    | `from: required. Type: Object.` Output node description.   |
|                                                             |             |                                                            |
|                                                             |             | `from.node_id: required.`                                  |
|                                                             |             |                                                            |
|                                                             |             | `from.resource: required.` Name of the Output              |
|                                                             |             |                                                            |
|                                                             |             | `to: required. Type: Object.` Input node description.      |
|                                                             |             |                                                            |
|                                                             |             | `to.node_id: required.`                                    |
|                                                             |             |                                                            |
|                                                             |             | `to.resource: required.` Name of the Input                 |
+-------------------------------------------------------------+-------------+------------------------------------------------------------+
| ``plynx/api/v0/graphs/{graph_id}/nodes/change_parameter``   | ``POST``    | `node_id: required.`                                       |
|                                                             |             |                                                            |
|                                                             |             | `parameter_name: required.`                                |
|                                                             |             |                                                            |
|                                                             |             | `parameter_value: required.`                               |
+-------------------------------------------------------------+-------------+------------------------------------------------------------+



Example
----------------

.. code-block:: bash

    curl -X POST 'http://localhost:5000/plynx/api/v0/graphs/5d292406713b286094d4ad87/nodes/insert_node' \
        -u default: -H "Content-Type: application/json" \
        -d '{"node_id": "5d2d4b1dc36682386f559eae", "x": 100, "y": 100}'

    curl -X POST 'http://localhost:5000/plynx/api/v0/graphs/5d292406713b286094d4ad87/nodes/remove_node' \
        -u default: -H "Content-Type: application/json" \
        -d '{"node_id": "5d27e3bd0f432b5e3693314c"}'

    curl -X POST 'http://localhost:5000/plynx/api/v0/graphs/5d292406713b286094d4ad87/nodes/create_link' \
        -u default: -H "Content-Type: application/json" \
        -d '{"from": {"node_id": "5d2fbdf3373d3b7ce6e69043", "resource": "out"}, "to": {"node_id": "5d3081ea99d54c7b6b8ff56b", "resource": "input"}}'

    curl -X POST 'http://localhost:5000/plynx/api/v0/graphs/5d292406713b286094d4ad87/nodes/change_parameter' \
        -u default: -H "Content-Type: application/json" \
        -d '{"node_id": "5d30b7eb88fb6a42caf0c565", "parameter_name": "template", "parameter_value": "abc"}'




.. _plynx-rest-get_resource:

Working with a single Resource
=====================================

This endpoint is a proxy between the client and internal PLynx resources.

*WARNING: try to avoid calling this endpoint without "preview" argument set to True.*
Currently PLynx supports multiple data storages and is not optimized for a particular one.
It will be fixed in the future versions, exposing additional endpoints.

+------------------------------------------+-------------+
| Endpoint                                 | HTTP Method |
+==========================================+=============+
| ``plynx/api/v0/resources/{resource_id}`` | ``GET``     |
+------------------------------------------+-------------+
Additional arguments to the endpoint:

+---------------+-------------+----------------------------------------------------------------------------+
| Argument      | Type        | Description                                                                |
+===============+=============+============================================================================+
| ``preview``   | ``BOOLEAN`` | Preview flag (default: `false`)                                            |
+---------------+-------------+----------------------------------------------------------------------------+
| ``file_type`` | ``STRING``  | One of the plugins. See :ref:`plynx-internal-file-types` for more details. |
+---------------+-------------+----------------------------------------------------------------------------+



.. _plynx-rest-get_master_state:

Get state of the Master
=====================================

When Master is running, it periodically syncs its state with PLynx database.
Use this endpoint to access it.
See See :ref:`plynx-internal-master_state`.

+-------------------------------+-------------+
| Endpoint                      | HTTP Method |
+===============================+=============+
| ``plynx/api/v0/master_state`` | ``GET``     |
+-------------------------------+-------------+



Example
----------------

.. code-block:: bash

    curl 'http://localhost:5000/plynx/api/v0/master_state' -u default:
