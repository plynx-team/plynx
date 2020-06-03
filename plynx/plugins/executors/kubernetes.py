from subprocess import Popen
import os
import uuid
import shutil
import string
import random
import logging
import kubernetes
from plynx.constants import JobReturnStatus, ParameterTypes
from plynx.db.node import Parameter, Output
import plynx.plugins.executors.local as local
from plynx.plugins.resources.common import FILE_KIND

NAMESPACE = 'plynx-worker'

KUBECTL_RETURN_CODES = {
    137: 'Pod was not found: plese check `_timeout` parameter and/or `k8s_worker` logs',
}


def gen_rand(length=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


def gen_rand_name():
    return '{}-{}'.format('job', gen_rand())


def _extend_default_node_in_place(node):
    node.parameters.extend(
        [
            Parameter.from_dict({
                'name': '_image',
                'parameter_type': ParameterTypes.STR,
                'value': 'alpine:3.7',
                'mutable_type': False,
                'publicable': True,
                'removable': False,
                }
            ),
        ]
    )

    node.logs.extend(
        [
            Output({
                'name': 'k8s_worker',
                'file_type': FILE_KIND,
            }),
        ]
    )


class KubernetesStatusPhase:
    PENDING = 'Pending'
    RUNNING = 'Running'
    SUCCEEDED = 'Succeeded'
    FAILED = 'Failed'
    UNKNOWN = 'Unknown'


def get_param_dict(node):
    res = {}
    for parameter in node.parameters:
        res[parameter.name] = parameter.value
    return res


_api_instance = None


def get_api_instance():
    global _api_instance
    if _api_instance:
        return _api_instance
    kubernetes.config.load_kube_config()
    configuration = kubernetes.client.Configuration()
    _api_instance = kubernetes.client.CoreV1Api(kubernetes.client.ApiClient(configuration))
    return _api_instance


def wait_and_check_return_status(sp):
    returncode = sp.wait()

    if returncode == 0:
        return
    if returncode in KUBECTL_RETURN_CODES:
        raise Exception(KUBECTL_RETURN_CODES[returncode])
    raise Exception('Error: unexpected return code `{}`. Please check the logs for details.'.format(returncode))


def create_kubernetes_body(node_param_dict, job_name, workdir):
    container_image = node_param_dict['_image']
    ENV_LIST = []

    body = kubernetes.client.V1Pod(api_version="v1", kind="Pod")
    body.metadata = kubernetes.client.V1ObjectMeta(namespace=NAMESPACE, name=job_name)
    body.status = kubernetes.client.V1PodStatus()

    # Now we start with the Template...
    template = kubernetes.client.V1PodTemplate()
    template.template = kubernetes.client.V1PodTemplateSpec()

    container = kubernetes.client.V1Container(
        name=job_name,
        image=container_image,
        env=ENV_LIST,
        # command=['sleep', str(node_param_dict.get('_timeout', 600))],
        command=['sleep', '10'],
    )
    template.template.spec = kubernetes.client.V1PodSpec(
        containers=[container],
        restart_policy='Never',
        )
    # And finaly we can create our V1JobSpec!
    body.spec = kubernetes.client.V1PodSpec(
        containers=[container],
        restart_policy='Never',
        )

    return body


class BashJinja2(local.BashJinja2):
    @classmethod
    def get_default_node(cls, is_workflow):
        node = super().get_default_node(is_workflow)
        _extend_default_node_in_place(node)

        node.parameters.extend(
            [
                Parameter.from_dict({
                    'name': '_image_command',
                    'parameter_type': ParameterTypes.STR,
                    'value': 'bash',
                    'mutable_type': False,
                    'publicable': True,
                    'removable': False,
                    }
                ),
            ]
        )
        return node

    def exec_script(self, script_location, command='bash'):
        res = JobReturnStatus.FAILED

        try:
            param_dict = get_param_dict(self.node)
            job_name = gen_rand_name()
            body = create_kubernetes_body(param_dict, job_name, self.workdir)
            api_response = get_api_instance().create_namespaced_pod(NAMESPACE, body, pretty=True)
            logging.info(api_response)

            stream = kubernetes.watch.Watch().stream(
                func=get_api_instance().list_namespaced_pod,
                namespace=NAMESPACE,
                field_selector="metadata.name={}".format(job_name)
                )
            second_time_running = False
            with open(self.logs['stdout'], 'wb', buffering=0) as stdout_file, open(self.logs['stderr'], 'wb', buffering=0) as stderr_file:
                for event in stream:
                    phase = event["object"].status.phase
                    with open(self.logs['k8s_worker'], 'a+') as k8s_worker_log_file:
                        k8s_worker_log_file.write(
                            'Pod `{}` in `{}` status\n'.format(job_name, phase)
                            )
                        if phase == KubernetesStatusPhase.PENDING:
                            continue
                        elif phase == KubernetesStatusPhase.RUNNING:
                            if second_time_running:
                                continue
                            second_time_running = True
                            k8s_worker_log_file.write('Uploading artifacts...\n')
                            sp = Popen(
                                [
                                    'kubectl', 'cp',
                                    '--namespace', NAMESPACE,
                                    self.workdir, '{}:{}'.format(job_name, self.workdir)
                                ],
                                stdout=k8s_worker_log_file,
                                stderr=k8s_worker_log_file,
                                cwd=self.workdir
                            )
                            wait_and_check_return_status(sp)

                            k8s_worker_log_file.write('Running script...\n')
                            sp = Popen(
                                [
                                    'kubectl', 'exec',
                                    '--namespace', NAMESPACE,
                                    '-it', job_name,
                                    param_dict.get('_image_command', command), script_location
                                ],
                                stdout=stdout_file,
                                stderr=stderr_file,
                                cwd=self.workdir
                            )
                            wait_and_check_return_status(sp)

                            # Hack: absolute path does not work with `kubectl cp`
                            # solution: download to a local `tmp_dir` directory and move it to `workdir`
                            tmp_dir = str(uuid.uuid1())
                            os.mkdir(tmp_dir)
                            k8s_worker_log_file.write('Downloading artifacts...\n')
                            for output_name, filename in self.output_to_filename.items():
                                k8s_worker_log_file.write('Downloading `{}`...\n'.format(output_name))
                                local_filename = os.path.join(tmp_dir, os.path.basename(filename))
                                sp = Popen(
                                    [
                                        'kubectl', 'cp',
                                        '--namespace', NAMESPACE,
                                        '{}:{}'.format(job_name, filename), local_filename,
                                    ],
                                    stdout=k8s_worker_log_file,
                                    stderr=k8s_worker_log_file,
                                )
                                wait_and_check_return_status(sp)

                                if os.path.exists(filename):
                                    if os.path.isfile(filename):
                                        os.remove(filename)
                                    else:
                                        shutil.rmtree(filename)
                                shutil.move(local_filename, filename)
                            os.rmdir(tmp_dir)

                            sp = Popen(
                                [
                                    'kubectl', 'delete', 'pod',
                                    '--namespace', NAMESPACE,
                                    job_name
                                ],
                                stdout=k8s_worker_log_file,
                                stderr=k8s_worker_log_file,
                                cwd=self.workdir
                            )
                            wait_and_check_return_status(sp)
                            res = JobReturnStatus.SUCCESS
                        elif phase in (KubernetesStatusPhase.SUCCEEDED, KubernetesStatusPhase.FAILED):
                            if res == JobReturnStatus.SUCCESS:
                                break
                            k8s_worker_log_file.write('Removing pod `{}`\n'.format(job_name))
                            sp = Popen(
                                [
                                    'kubectl', 'delete', 'pod',
                                    '--namespace', NAMESPACE,
                                    job_name
                                ],
                                stdout=k8s_worker_log_file,
                                stderr=k8s_worker_log_file,
                                cwd=self.workdir
                            )
                            wait_and_check_return_status(sp)
                            raise Exception("Kubernetes pod failed")
                        elif phase == KubernetesStatusPhase.UNKNOWN:
                            raise Exception("Kubernetes pod is unknown")
                        else:
                            raise Exception("Unknown Kubernetes pod phase: `{}`".format(phase))

        except Exception as e:
            res = JobReturnStatus.FAILED
            logging.exception("Job failed")
            with open(self.logs['k8s_worker'], 'a+') as k8s_worker_log_file:
                k8s_worker_log_file.write(self._make_debug_text("JOB FAILED"))
                k8s_worker_log_file.write(str(e))

        return res


class PythonNode(local.PythonNode):
    @classmethod
    def get_default_node(cls, is_workflow):
        node = super().get_default_node(is_workflow)
        _extend_default_node_in_place(node)
        return node
