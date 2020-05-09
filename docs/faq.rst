.. _plynx-faq:


Frequently Asked Questions
==========================

Who is it for?
--------------------------------------

PLynx has been developed mainly for Data Scientists and ML Engineers as a high level abstraction of data pipelines and infrastructure.
It is not limited by them and can be used by other technical and non-technical professionals, etc.

Modular architecture makes PLynx rather a graph editor that transforms graphs into executable code.


Can I run it without docker?
--------------------------------------

Yes you can, but this way is not recommended.

Docker is an extremely powerful platform that has become a de-facto standard in the industry.
Besides encapsulation, isolation and portability, it provides a more convenient way to control complex systems.

If you still want to run it without docker or have some other issues with deployment, please don't hesitate to contact us in `discord <https://discord.gg/ZC3wY2J>`_


How is it different from Airflow, Kubeflow and other platforms?
---------------------------------------------------------------

Here are some main differences and principles.

- PLynx follows the principle of rapid development: Try Fast Fail Fast. Highly reliable execution is not as important as flexibility and ability to try different experiments. Using reliable data pipelines in Data Science can bring incremental improvements, however there is usually far more to gain from other activities like integrating new data sources or using additional workflows.
- Each Operation has named *inputs* and *outputs*. It removes hidden logic and allows you to *reuse* existing Operations in new Workflows.
- The interface abstracts data scientists from the engineering and organizational complexities, such as data access, containerization, distributed processing, automatic failover, and other advanced computer science concepts.
- Plugins are very flexible and support multiple platforms and use cases.
- It encourages people to create their workflows in a more modular and parameterized way reusing existing solutions. This way they don’t reinvent existing solutions many times and can use advantages of cached results and distributed computation.
- No need to have a domain specialist run the entire pipeline. Non-specialist can rerun an existing one.
- Experiments in Graph format are very well interpretable. It can be used by non-experts, or by people from other teams.


Is it a no-code platform?
-------------------------------------------------------------

Not exactly. Users have ability to write their own Operations as well as use existing repositories.


How can I install additional packages?
-------------------------------------------------------------

**Option 1.** Build your new images (preferred)

- Create a new Dockerfile with your dependancies.
- Install `PyPI PLynx package <https://pypi.org/project/plynx/>`_
- Deploy your new image.

**Option 2.** Local build copy.

- Add dependancies to your `requirements.txt <https://github.com/plynx-team/plynx/blob/master/docker/backend/requirements.txt>`_
- Run ``make build`` to build new images.
- Run ``make up`` to start your local PLynx.

**Option 3.** Kubernetes Operation (not available now)

Currently work in queue. `Please upvote <https://github.com/plynx-team/plynx/issues/37>`_


How to contact us?
-------------------------------------------------------------

Please don't hesitate to join us in `discord <https://discord.gg/ZC3wY2J>`_.
