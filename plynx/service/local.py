import sys
import subprocess
import logging
import webbrowser
import time
from collections import namedtuple

DockerDescriptor = namedtuple('DockerDescriptor', ['image', 'ports'])

DOCKER_CONTAINERS = [
    DockerDescriptor(
        image='khaxis/plynx:ui',
        ports={3000: 3000},
    ),
]


# TODO more elegant solution?
def _get_container_by_tag(client, tag):
    for container in client.containers.list():
        if tag in container.image.attrs['RepoTags']:
            return container
    return None


def _kill_containers_by_tag(client, tags):
    for container in client.containers.list():
        if container.image.attrs['RepoTags'][0] in tags:
            logging.info('Stopping {}...'.format(container))
            container.stop()
            logging.info('Done')


def _run_docker(client):
    for descriptor in DOCKER_CONTAINERS:
        container = _get_container_by_tag(client, descriptor.image)
        if container:
            logging.info("Found running docker container: {}".format(container))
        else:
            container = client.containers.run(detach=True, **vars(descriptor))
            logging.info("Created new container: {}".format(container))


def run_local(num_workers, verbose):
    try:
        import docker   # noqa
    except ImportError:
        logging.critical("Docker SDK fro python must be installed. "
                         "Please visit https://docker-py.readthedocs.io/en/stable/ for instructions")
        pass

    client = docker.from_env()
    assert num_workers > 0, 'There must be one or more Workers'

    try:
        _run_docker(client)

        verbose_flags = ['-v'] * verbose

        processes = [
            ['plynx', 'backend'] + verbose_flags,
            ['plynx', 'master'] + verbose_flags,
        ]
        processes.extend([['plynx', 'worker'] + verbose_flags] * num_workers)

        procs = [subprocess.Popen(process) for process in processes]

        time.sleep(5)
        URL = 'http://localhost:3000'
        print('PLynx is running at: {}'.format(URL))
        webbrowser.open_new_tab(URL)
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        pass
    finally:
        _kill_containers_by_tag(client, [descriptor.image for descriptor in DOCKER_CONTAINERS])
