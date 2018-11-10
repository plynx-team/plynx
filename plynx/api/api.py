import json
import requests
import logging
import time
from plynx.api import ApiActionError, _GraphPostStatus, _ValidationCode


def _get_obj(obj_path, obj_id, client):
    for it in range(3):
        response = requests.get(
            '{endpoint}/{path}/{id}'.format(
                endpoint=client.endpoint,
                path=obj_path,
                id=obj_id
                ),
            headers={"Content-Type": "application/json"},
            auth=(client.get_token(), '')
            )
        if response.ok:
            break
        if response.status_code == 401:
            client.update_token()
        time.sleep(1)

    if not response.ok:
        raise ApiActionError(response.content)
    content = json.loads(response.content)
    return content['data']


def _save_graph(graph, actions, client):
    for it in range(3):
        response = requests.post(
            '{endpoint}/{path}'.format(
                endpoint=client.endpoint,
                path='graphs'
                ),
            headers={"Content-Type": "application/json"},
            auth=(client.get_token(), ''),
            data=json.dumps({
                'body': {
                    'graph': graph,
                    'actions': actions
                    }
                })
            )
        if response.ok:
            break
        if response.status_code == 401:
            client.update_token()
        time.sleep(1)

    if not response.ok:
        raise ApiActionError(response.content)
    content = json.loads(response.content)
    if content['status'].upper() != _GraphPostStatus.SUCCESS:
        if content['status'].upper() == _GraphPostStatus.VALIDATION_FAILED:
            logging.error('Validation error:')
            _print_validation_error(content['validation_error'])
        raise ApiActionError(content['message'])
    return content['graph'], content['url']


def _get_access_token(refresh_token, client):
    response = requests.get(
        '{endpoint}/token'.format(
            endpoint=client.endpoint
            ),
        headers={"Content-Type": "application/json"},
        auth=(refresh_token, '')
        )
    content = json.loads(response.content)
    return content['access_token'] if response.ok else None


def _print_validation_error(validation_error):
    for child in validation_error['children']:
        validation_code = child['validation_code']
        if validation_code == _ValidationCode.IN_DEPENDENTS:
            _print_validation_error(child)
        elif validation_code == _ValidationCode.MISSING_INPUT:
            logging.error('Missing input: `{}`'.format(child['object_id']))
        elif validation_code == _ValidationCode.MISSING_PARAMETER:
            logging.error('Missing parameter: `{}`'.format(child['object_id']))
        else:
            logging.error('Unexpected Error')
