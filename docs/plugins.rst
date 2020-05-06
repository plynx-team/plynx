
.. _plynx-plugins:

===========================
Plugins
===========================

PLynx offers a generic interface for working with custom infrastructure and services.
Different organizations have different stacks and different needs.
Using PLynx plugins can be a way for companies to customize their PLynx installation to reflect their ecosystem.

Plugins can be used as an easy way to write, share and activate new sets of features.

There’s also a need for a set of more complex applications to interact with different flavors of data and backend infrastructure.
Essentially PLynx is a graph editor with computational backend provided by plugins and configuration.

Examples:

- Inputs and Outputs might have explicitly different types. They can be simple files or references to S3 / Big Query table / HDFS path etc.
- Users have an option to customize pre or post-processing as well as preview options.
- Operations can be execute commands in multiple languages or in custom environments.
- Some applications require executing Operations one by one, others transform DAGs into AWS Step functions or Argo utilizing 3rd party backend.
- Catalog and categorization of Operations can be supported bu Hubs.
- ...


.. _plynx-plugins-executors:

Executors
===========================

Executors are the mechanism by which job instances get run.

PLynx has support for various executors.
Some of them execute a single job such as python or bash script.
Others are working with DAG structure.

PLynx can be customized by additional executors.


.. code-block:: python

    import plynx.base.executor


    class CustomExecutor(plynx.base.executor.BaseExecutor):
        """ Custom Executor.

        Args:
            node_dict (dict)

        """

        def __init__(self, node_dict):
            super(DAG, self).__init__(node_dict)

            # Initialization

        @classmethod
        def get_default_node(cls, is_workflow):
            """
            You may modify a node by additional parameters.
            """
            node = super().get_default_node(is_workflow)

            # customize your default node here

            return node

        def run(self):
            """
            Worker will execute this function.
            """

        def kill(self):
            """
            Worker will call this function if parent executor or a user canceled the process.
            """

        def validate(self):
            """
            Validate Node.
            """



.. _plynx-plugins-resources:

Resources
===========================

PLynx explicitly define artifacts: Inputs, Outputs, and Logs.
The mechanism to handle custom artifacts is supported by Resource plugins.

.. code-block:: python

    import plynx.base.resource


    class CustomResource(plynx.base.resource.BaseResource):
        @staticmethod
        def prepare_input(filename, preview):
            """
            Prepare resource before execution.
            """
            if preview:
                return {NodeResources.INPUT: filename}
            # Customize preprocessing here
            return {NodeResources.INPUT: filename}

        @staticmethod
        def prepare_output(filename, preview):
            """
            Prepare output resource before execution.

            For example create a directory or an empty file.
            """
            if preview:
                return {NodeResources.OUTPUT: filename}
            # Customize preprocessing here
            return {NodeResources.OUTPUT: filename}

        @staticmethod
        def postprocess_output(filename):
            """
            Process output after execution.

            For example compress a file or compute extra statistics.
            """
            return filename

        @classmethod
        def preview(cls, preview_object):
            """
            Redefine preview function.

            For example display text content or <img>
            """

            return '<pre>{}</pre>'.format(content)


.. _plynx-plugins-hubs:

Hubs
===========================

Hubs let users to organize Operations in the editor and use additional sources.


.. code-block:: python

    import plynx.base.hub


    class CustomHub(plynx.base.hub.BaseHub):
        def __init__(self, **argv):
            super(CollectionHub, self).__init__()

            # use arguments to customize the hub

        def search(self, query):
            """
            Customize search.
            """
