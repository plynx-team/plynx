import os
import subprocess
import logging
import webbrowser
import time
import tempfile
import yaml
from collections import namedtuple
import plynx
import plynx.utils.config as cfg

DockerDescriptor = namedtuple('DockerDescriptor', ['image', 'ports'])

DOCKER_CONTAINERS = [
    DockerDescriptor(
        image='mongo:3.6-jessie',
        ports={27017: 27017},
    ),
    DockerDescriptor(
        image='khaxis/plynx_{}:ui'.format(plynx.__version__),
        ports={3000: 3000},
    ),
]


# TODO more elegant solution?
def _get_container_by_tag(client, tag):
    for container in client.containers.list():
        if tag in container.image.attrs['RepoTags']:
            return container
    return None


def _kill_containers(containers):
    for container in containers:
        logging.info('Stopping {}...'.format(container))
        container.stop()
        logging.info('Done')


def _run_containers(client, containers):
    for descriptor in DOCKER_CONTAINERS:
        container = _get_container_by_tag(client, descriptor.image)
        if container:
            logging.info(
                'Found running docker container: `{}` {}'.format(
                    descriptor.image,
                    container,
                )
            )
        else:
            container = client.containers.run(detach=True, **vars(descriptor))
            logging.info('Created new container: `{}` {}'.format(
                descriptor.image,
                container,
                )
            )
        containers.append(container)


def run_local(num_workers, ignore_containers, verbose):
    assert num_workers > 0, 'There must be one or more Workers'

    try:
        with tempfile.NamedTemporaryFile('w', suffix='.yaml') as config_file:
            yaml.dump(cfg._config, config_file, default_flow_style=False)
            containers = []
            if not ignore_containers:
                try:
                    import docker   # noqa
                except ImportError:
                    logging.critical("Docker SDK fro python must be installed. "
                                     "Please visit https://docker-py.readthedocs.io/en/stable/ for instructions")
                    raise
                client = docker.from_env()
                _run_containers(client, containers)

            verbose_flags = ['-v'] * verbose

            processes = [
                ['plynx', 'backend'] + verbose_flags,
                ['plynx', 'master'] + verbose_flags,
            ]
            processes.extend([['plynx', 'worker'] + verbose_flags] * num_workers)

            # set up env variables
            plynx_env = os.environ.copy()
            plynx_env['PLYNX_CONFIG_PATH'] = config_file.name

            procs = [
                subprocess.Popen(process, env=plynx_env)
                for process in processes
            ]

            time.sleep(5)
            URL = 'http://localhost:3000'
            print('PLynx is running at: {}'.format(URL))
            webbrowser.open_new_tab(URL)
            for p in procs:
                p.wait()
    except KeyboardInterrupt:
        pass
    finally:
        _kill_containers(containers)
