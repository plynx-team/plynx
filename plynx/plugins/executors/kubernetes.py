from subprocess import Popen
import os
import time
import uuid
import shutil
import string
import random
import logging
import collections
import kubernetes
from enum import Enum
from plynx.constants import NodeRunningStatus, ParameterTypes
from plynx.db.node import Parameter, Output
import plynx.plugins.executors.local as local
from plynx.plugins.resources.common import FILE_KIND

NAMESPACE = 'plynx-worker'
SCHEDULING_RETRY = 30

KUBECTL_RETURN_CODES = {
    137: 'Pod was not found: plese check `_timeout` parameter and/or `k8s_worker` logs',
}

KeyValue = collections.namedtuple('KeyValue', ['name', 'default', 'type'])


class KeyConstants(Enum):
    IMAGE = KeyValue('_image', 'alpine:3.7', ParameterTypes.STR)
    IMAGE_COMMAND = KeyValue('_image_command', 'sh', ParameterTypes.STR)
    CPU = KeyValue('_cpu', '100m', ParameterTypes.STR)
    MEMORY = KeyValue('_memory', '1024Mi', ParameterTypes.STR)
    GPU = KeyValue('_gpu', 0, ParameterTypes.INT)
    SCHEDULING_RETRY = KeyValue('_scheduling_retry', 30, ParameterTypes.INT)


def gen_rand(length=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


def gen_rand_name():
    return '{}-{}'.format('job', gen_rand())


def _extend_default_node_in_place(node):
    for param in KeyConstants:
        node.parameters.append(
            Parameter.from_dict({
                'name': param.value.name,
                'parameter_type': param.value.type,
                'value': param.value.default,
                'mutable_type': False,
                'publicable': True,
                'removable': False,
                }
            )
        )

    node.logs.extend(
        [
            Output({
                'name': 'k8s_worker',
                'file_type': FILE_KIND,
            }),
        ]
    )


def _extract_param_value(node_param_dict, e):
    return node_param_dict.get(e.value.name, e.value.default)


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
    container_image = _extract_param_value(node_param_dict, KeyConstants.IMAGE)
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
        command=['sleep', str(node_param_dict.get('_timeout', 600) * 60)],
        resources=kubernetes.client.V1ResourceRequirements(
            requests={
                'memory': _extract_param_value(node_param_dict, KeyConstants.MEMORY),
                'cpu': _extract_param_value(node_param_dict, KeyConstants.CPU),
                'nvidia.com/gpu': _extract_param_value(node_param_dict, KeyConstants.GPU),
            },
            limits={
                'memory': _extract_param_value(node_param_dict, KeyConstants.MEMORY),
                'cpu': _extract_param_value(node_param_dict, KeyConstants.CPU),
                'nvidia.com/gpu': _extract_param_value(node_param_dict, KeyConstants.GPU),
            },
        ),
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


def delete_pod(job_name, log_stream):
    logging.info("Deleting pod")
    sp = Popen(
        [
            'kubectl', 'delete', 'pod',
            '--namespace', NAMESPACE,
            '--grace-period=0',
            job_name
        ],
        stdout=log_stream,
        stderr=log_stream,
    )
    wait_and_check_return_status(sp)


def _init(self):
    self.job_name = None


def _exec_script(self, script_location):
    self._node_running_status = NodeRunningStatus.FAILED

    try:
        param_dict = get_param_dict(self.node)
        self.job_name = gen_rand_name()
        body = create_kubernetes_body(param_dict, self.job_name, self.workdir)
        api_response = get_api_instance().create_namespaced_pod(NAMESPACE, body, pretty=True)
        logging.info(api_response)

        # append running script to worker log
        with open(script_location, 'r') as sf, open(self.logs['worker'], 'a') as wf:
            wf.write(self._make_debug_text("Running script:"))
            wf.write(sf.read())
            wf.write('\n')
            wf.write(self._make_debug_text("End script"))

        stream = kubernetes.watch.Watch().stream(
            func=get_api_instance().list_namespaced_pod,
            namespace=NAMESPACE,
            field_selector="metadata.name={}".format(self.job_name)
            )
        second_time_running = False
        with open(self.logs['stdout'], 'wb', buffering=0) as stdout_file, open(self.logs['stderr'], 'wb', buffering=0) as stderr_file:
            for event in stream:
                phase = event["object"].status.phase
                with open(self.logs['k8s_worker'], 'a+') as k8s_worker_log_file:
                    k8s_worker_log_file.write(
                        'Pod `{}` in `{}` status\n'.format(self.job_name, phase)
                        )
                    if phase == KubernetesStatusPhase.PENDING:
                        # for some reason pod sometimes gets back to this state
                        if second_time_running:
                            break
                        if not event['object'].status.conditions:
                            continue
                        for condition in event['object'].status.conditions:
                            if condition.reason == 'Unschedulable':
                                scheduled = False
                                for ii in range(param_dict.get('_scheduling_retry', SCHEDULING_RETRY)):
                                    time.sleep(1)
                                    pod_list = get_api_instance().list_namespaced_pod(
                                        namespace=NAMESPACE,
                                        field_selector="metadata.name={}".format(self.job_name)
                                    )
                                    k8s_worker_log_file.write(
                                        'Retry scheduling #{}\n'.format(ii)
                                        )
                                    if len(pod_list.items) != 1:
                                        raise Exception('Unexpected number of pods: {}'.format(len(pod_list.items)))
                                    if pod_list.items[0].status.phase == KubernetesStatusPhase.PENDING:
                                        continue
                                    scheduled = True
                                    break
                                if not scheduled:
                                    raise Exception(condition.message)
                    elif phase == KubernetesStatusPhase.RUNNING:
                        if second_time_running:
                            continue
                        second_time_running = True
                        k8s_worker_log_file.write('Uploading artifacts...\n')
                        sp = Popen(
                            [
                                'kubectl', 'cp',
                                '--namespace', NAMESPACE,
                                self.workdir, '{}:{}'.format(self.job_name, self.workdir)
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
                                '-it', self.job_name,
                                '--',
                                _extract_param_value(param_dict, KeyConstants.IMAGE_COMMAND), script_location
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
                                    '{}:{}'.format(self.job_name, filename), local_filename,
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

                        delete_pod(self.job_name, k8s_worker_log_file)
                        self._node_running_status = NodeRunningStatus.SUCCESS
                    elif phase in (KubernetesStatusPhase.SUCCEEDED, KubernetesStatusPhase.FAILED):
                        if self._node_running_status == NodeRunningStatus.SUCCESS:
                            break
                        k8s_worker_log_file.write('Removing pod `{}`\n'.format(self.job_name))
                        delete_pod(self.job_name, k8s_worker_log_file)
                        raise Exception("Kubernetes pod failed")
                    elif phase == KubernetesStatusPhase.UNKNOWN:
                        raise Exception("Kubernetes pod is unknown")
                    else:
                        raise Exception("Unknown Kubernetes pod phase: `{}`".format(phase))

    except Exception as e:
        self._node_running_status = NodeRunningStatus.FAILED
        logging.exception("Job failed")
        with open(self.logs['k8s_worker'], 'a+') as k8s_worker_log_file:
            k8s_worker_log_file.write(self._make_debug_text("JOB FAILED"))
            k8s_worker_log_file.write(str(e))

    return self._node_running_status


def _kill(self):
    if not self.job_name:
        return

    self._node_running_status = NodeRunningStatus.CANCELED
    delete_pod(self.job_name, None)


class BashJinja2(local.BashJinja2):
    def __init__(self, node=None):
        super(BashJinja2, self).__init__(node)
        _init(self)

    @classmethod
    def get_default_node(cls, is_workflow):
        node = super().get_default_node(is_workflow)
        node.title = 'New bash k8s script'

        _extend_default_node_in_place(node)

        return node

    def exec_script(self, script_location):
        return _exec_script(self, script_location)

    def kill(self):
        return _kill(self)


class PythonNode(local.PythonNode):
    def __init__(self, node=None):
        super(PythonNode, self).__init__(node)
        _init(self)

    @classmethod
    def get_default_node(cls, is_workflow):
        node = super().get_default_node(is_workflow)
        node.title = 'New python k8s script'

        _extend_default_node_in_place(node)

        param = list(filter(lambda p: p.name == '_cmd', node.parameters))[0]
        param.value.mode = 'python'
        param.value.value = 'print("hello world")'

        param = list(filter(lambda p: p.name == KeyConstants.IMAGE_COMMAND.value.name, node.parameters))[0]
        param.value = 'python'

        return node

    def exec_script(self, script_location):
        return _exec_script(self, script_location)

    def kill(self):
        return _kill(self)
