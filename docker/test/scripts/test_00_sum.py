#!/usr/bin/env python
import os
import json
import requests
import argparse
from bson.objectid import ObjectId
from plynx import Node, File, Graph, Client

BASE_FILE = 'base_file.json'
SEQ_FILE = 'seq_100.csv'
NODES_FILE = 'nodes.json'

SUCCESS_RESPONSE = 'SUCCESS'


class RespondError(RuntimeError):
    pass


def make_object_id():
    return str(ObjectId())


def get_access_token(endpoint):
    r = requests.post('{}/demo'.format(endpoint))
    if r.ok:
        return r.json()['access_token']
    raise RespondError('Unable to create a demo user')


def upload_file(endpoint, access_token, data_path, filename):
    object_id = make_object_id()
    with open(filename, 'r') as f:
        files = {'data': f}
        r = requests.post(
            '{}/resource'.format(endpoint),
            files=files,
            auth=(access_token, ''))
    if r.ok:
        response = r.json()
        assert response['status'] == SUCCESS_RESPONSE
    else:
        raise RespondError('Unable to upload a file')
    resource_id = response['resource_id']

    with open(os.path.join(data_path, BASE_FILE), 'r') as f:
        base_file = json.load(f)

    base_file['_id'] = object_id
    base_file['title'] = 'test file'
    base_file['description'] = 'descr'
    base_file['outputs'][0]['resource_id'] = resource_id

    r = requests.post(
        '{}/nodes'.format(endpoint),
        json={
            'body': { 
                'node': base_file,
                'action': 'SAVE'
            }
        },
        auth=(access_token, ''),
      )
    
    if r.ok:
        response = r.json()
        assert response['status'] == SUCCESS_RESPONSE
        return object_id
    raise RespondError('Unable to create a node')


def create_operations(endpoint, access_token, nodes_filename):
    title_to_node_id = {}
    with open(nodes_filename, 'r') as f:
        data = json.load(f)
    for node in data:
        node['_id'] = make_object_id()
        r = requests.post(
            '{}/nodes'.format(endpoint),
            json={
                'body': { 
                    'node': node,
                    'action': 'APPROVE'
                }
            },
            auth=(access_token, ''),
          )
        
        if r.ok:
            response = r.json()
            assert response['status'] == SUCCESS_RESPONSE, "Not expected `status`: `{}`".format(response['status'])
            title_to_node_id[node['title']] = node['_id']
        else:
            raise RespondError('Unable to create a node')

    return title_to_node_id


def run_graph(access_token, file_id, operations):
    f = File(id=file_id)

    Grep = Node(
        id=operations['Grep'],
        inputs=['input'],
        outputs=['output'],
        params=['template']
    )

    Sum = Node(
        id=operations['Sum'],
        inputs=['input'],
        outputs=['output']
    )

    res = Sum(
        input=[Sum(
            input=Grep(
                input=f.outputs.out,
                template="^{}".format(number)
                ).outputs.output
            ).outputs.output for number in range(1,10)]
    )

    graph = Graph(
        Client(access_token),
        title='Hello I am tittle',
        description='Desc',
        targets=[res]
    )

    graph.approve().wait()


def main(endpoint, data_path):
    access_token = get_access_token(endpoint)
    file_id = upload_file(endpoint, access_token, data_path, os.path.join(data_path, SEQ_FILE))
    operations = create_operations(endpoint, access_token, os.path.join(data_path, NODES_FILE))

    run_graph(access_token, file_id, operations)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run test')
    parser.add_argument('-e', '--endpoint', help='Endpoint of the backend')
    parser.add_argument('-d', '--data-path', help='Path to test data')
    args = parser.parse_args()

    main(**vars(args))
