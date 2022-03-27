"""Resources that implement cloud abstractions"""

import json
import os
import uuid
from typing import Dict

from plynx.base import resource
from plynx.constants import NodeResources
from plynx.utils.config import get_cloud_service_config

CLOUD_SERVICE_CONFIG = get_cloud_service_config()


class CloudStorage(resource.BaseResource):
    """Storage Resource, i.e. S3 bucket"""
    @staticmethod
    def prepare_input(filename: str, preview: bool = False) -> Dict[str, str]:
        """Preprocess input"""
        if preview:
            uniq_id = str(uuid.uuid1())
            cloud_filename = os.path.join(
                CLOUD_SERVICE_CONFIG.prefix,
                uniq_id,
            )
        else:
            with open(filename, "r", encoding="utf8") as f:
                cloud_filename = json.load(f)['path']
        return {
            NodeResources.INPUT: filename,
            NodeResources.CLOUD_INPUT: cloud_filename,
        }

    @staticmethod
    def prepare_output(filename: str, preview: bool = False) -> Dict[str, str]:
        """Postprocess output"""
        uniq_id = str(uuid.uuid1())
        cloud_filename = os.path.join(
            CLOUD_SERVICE_CONFIG.prefix,
            uniq_id,
            )
        if not preview:
            with open(filename, 'w', encoding="utf8") as f:
                json.dump({"path": cloud_filename}, f)
        return {
                NodeResources.OUTPUT: filename,
                NodeResources.CLOUD_OUTPUT: cloud_filename,
            }

    @classmethod
    def preview(cls, preview_object: resource.PreviewObject) -> str:
        """Preview resource"""
        path = json.load(preview_object.fp)["path"]
        url = "".join([CLOUD_SERVICE_CONFIG.url_prefix, path.split("//")[1], CLOUD_SERVICE_CONFIG.url_postfix])
        return f"<a href={url}>{path}</a>"
