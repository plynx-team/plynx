import os
import json
import uuid
from plynx.constants import NodeResources
from plynx.plugins.base import BaseResource
from plynx.utils.config import get_cloud_service_config


CLOUD_SERVICE_CONFIG = get_cloud_service_config()


class CloudStorage(BaseResource):
    NAME = 'cloud-storage'
    ALIAS = 'Cloud Storage'
    ICON = 'feathericons.hard-drive'
    COLOR = '#5ed1ff'

    @staticmethod
    def prepare_input(filename, preview):
        if preview:
            uniq_id = str(uuid.uuid1())
            cloud_filename = os.path.join(
                '{prefix}/{workdir}'.format(
                    prefix=CLOUD_SERVICE_CONFIG.prefix,
                    workdir=uniq_id,
                )
            )
        else:
            with open(filename) as f:
                cloud_filename = json.load(f)['path']
        return {
            NodeResources.INPUT: filename,
            NodeResources.CLOUD_INPUT: cloud_filename,
        }

    def prepare_output(filename, preview):
        uniq_id = str(uuid.uuid1())
        cloud_filename = os.path.join(
            '{prefix}/{workdir}'.format(
                prefix=CLOUD_SERVICE_CONFIG.prefix,
                workdir=uniq_id,
            )
        )
        if not preview:
            with open(filename, 'w') as f:
                json.dump({"path": cloud_filename}, f)

        return {
                NodeResources.OUTPUT: filename,
                NodeResources.CLOUD_OUTPUT: cloud_filename,
            }

    @classmethod
    def preview(cls, preview_object):
        path = json.load(preview_object.fp)['path']
        return '<a href={}>{}</a>'.format(
            ''.join([CLOUD_SERVICE_CONFIG.url_prefix, path.split('//')[1], CLOUD_SERVICE_CONFIG.url_postfix]),
            path
        )
