[
  {
    "_id": "5e66fc2df1e5b88d18f5c14f",
    "title": "Word2Vec 1",
    "_type": "Node",
    "description": "Find similar words",
    "kind": "basic-python-node-operation",
    "parent_node_id": null,
    "successor_node_id": null,
    "original_node_id": null,
    "inputs": [
      {
        "input_references": [
          {
            "node_id": "5e66fca5f1e5b88d18f5c23a",
            "output_id": "words"
          }
        ],
        "name": "positives",
        "file_type": "json",
        "values": [],
        "is_array": true,
        "min_count": 0
      },
      {
        "input_references": [
          {
            "node_id": "5e66fcc4f1e5b88d18f5c278",
            "output_id": "words"
          }
        ],
        "name": "negatives",
        "file_type": "json",
        "values": [],
        "is_array": true,
        "min_count": 0
      }
    ],
    "outputs": [
      {
        "name": "result",
        "file_type": "json",
        "values": [],
        "is_array": false,
        "min_count": 1
      }
    ],
    "parameters": [
      {
        "name": "_cmd",
        "parameter_type": "code",
        "value": {
          "value": "import json\nimport pickle\nimport os\n\n\ndef get_words(filenames):\n    res = []\n    for filename in filenames:\n        with open(filename) as f:\n            res.extend(json.load(f))\n    return res\n\npositive = get_words(inputs['positives'])\nnegative = get_words(inputs['negatives'])\n\nwith open(os.path.join('/models', params['model']), 'rb') as f:\n    model = pickle.load(f)\n\nres = model.most_similar(positive=positive, negative=negative)\n\nwith open(outputs['result'], 'w') as f:\n    json.dump(res, f)",
          "mode": "python"
        },
        "mutable_type": false,
        "removable": false,
        "publicable": false,
        "widget": null,
        "reference": null
      },
      {
        "name": "_cacheable",
        "parameter_type": "bool",
        "value": true,
        "mutable_type": false,
        "removable": false,
        "publicable": false,
        "widget": null,
        "reference": null
      },
      {
        "name": "_timeout",
        "parameter_type": "int",
        "value": 600,
        "mutable_type": false,
        "removable": false,
        "publicable": true,
        "widget": null,
        "reference": null
      },
      {
        "name": "model",
        "parameter_type": "enum",
        "value": {
          "values": [
            "glove-twitter-200",
            "glove-twitter-25"
          ],
          "index": "0"
        },
        "mutable_type": true,
        "removable": true,
        "publicable": true,
        "widget": "model",
        "reference": null
      }
    ],
    "logs": [
      {
        "name": "stderr",
        "file_type": "file",
        "values": [],
        "is_array": false,
        "min_count": 1
      },
      {
        "name": "stdout",
        "file_type": "file",
        "values": [],
        "is_array": false,
        "min_count": 1
      },
      {
        "name": "worker",
        "file_type": "file",
        "values": [],
        "is_array": false,
        "min_count": 1
      }
    ],
    "node_running_status": "CREATED",
    "node_status": "READY",
    "cache_url": "",
    "x": 282,
    "y": 142,
    "author": "5e5dd9c7653752f34e1e0be6",
    "starred": false
  },
  {
    "_id": "5e66fca5f1e5b88d18f5c33b",
    "title": "Words to list 1",
    "_type": "Node",
    "description": "Custom words",
    "kind": "basic-python-node-operation",
    "parent_node_id": null,
    "successor_node_id": null,
    "original_node_id": null,
    "inputs": [],
    "outputs": [
      {
        "name": "words",
        "file_type": "json",
        "values": [],
        "is_array": false,
        "min_count": 1
      }
    ],
    "parameters": [
      {
        "name": "_cmd",
        "parameter_type": "code",
        "value": {
          "value": "import json\n\nwith open(outputs['words'], 'w') as f:\n    json.dump(params['words'], f)",
          "mode": "python"
        },
        "mutable_type": false,
        "removable": false,
        "publicable": false,
        "widget": null,
        "reference": null
      },
      {
        "name": "_cacheable",
        "parameter_type": "bool",
        "value": true,
        "mutable_type": false,
        "removable": false,
        "publicable": false,
        "widget": null,
        "reference": null
      },
      {
        "name": "_timeout",
        "parameter_type": "int",
        "value": 600,
        "mutable_type": false,
        "removable": false,
        "publicable": true,
        "widget": null,
        "reference": null
      },
      {
        "name": "words",
        "parameter_type": "list_str",
        "value": [
          "king",
          "woman"
        ],
        "mutable_type": true,
        "removable": true,
        "publicable": true,
        "widget": "words",
        "reference": null
      }
    ],
    "logs": [
      {
        "name": "stderr",
        "file_type": "file",
        "values": [],
        "is_array": false,
        "min_count": 1
      },
      {
        "name": "stdout",
        "file_type": "file",
        "values": [],
        "is_array": false,
        "min_count": 1
      },
      {
        "name": "worker",
        "file_type": "file",
        "values": [],
        "is_array": false,
        "min_count": 1
      }
    ],
    "node_running_status": "CREATED",
    "node_status": "READY",
    "cache_url": "",
    "x": 30,
    "y": 80,
    "author": "5e5dd9c7653752f34e1e0be6",
    "starred": false
  },
  {
    "_id": "5e66fca5f1e5b88d18f5c43b",
    "title": "Words to list 2",
    "description": "Custom words",
    "kind": "_GROUP",
    "_type": "Group",
    "items": [
        {
          "_id": "5e66fca5f1e5b88d18f5c53b",
          "title": "Words to list 3",
          "description": "Custom words",
          "kind": "_GROUP",
          "_type": "Group",
          "items": [
              {"_id": "5e66fca5f1e5b88d18f5c23c","title": "Words to list 1","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
              {"_id": "5e66fca5f1e5b88d18f5c23d","title": "Words to list 2","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
              {"_id": "5e66fca5f1e5b88d18f5c23e","title": "Words to list 3","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
              {"_id": "5e66fca5f1e5b88d18f5c23f","title": "Words to list 4","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
              {"_id": "5e66fca5f1e5b88d18f5c24a","title": "Words to list 5","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
              {"_id": "5e66fca5f1e5b88d18f5c25a","title": "Words to list 6","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
              {"_id": "5e66fca5f1e5b88d18f5c26a","title": "Words to list 7","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
              {"_id": "5e66fca5f1e5b88d18f5c27a","title": "Words to list 8","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
              {"_id": "5e66fca5f1e5b88d18f5c28a","title": "Words to list 9","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
              {"_id": "5e66fca5f1e5b88d18f5c29a","title": "Words to list 10","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
              {"_id": "5e66fca5f1e5b88d18f5c2aa","title": "Words to list 11","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
              {"_id": "5e66fca5f1e5b88d18f5c2ba","title": "Words to list 12","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"}
          ],
          "author": "5e5dd9c7653752f34e1e0be6",
          "starred": false
        },
        {"_id": "5e66fca5f1e5b88d18f5c2ca","title": "Words to list a","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
        {"_id": "5e66fca5f1e5b88d18f5c2da","title": "Words to list b","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"},
        {"_id": "5e66fca5f1e5b88d18f5c2ea","title": "Words to list c","_type": "Node","description": "Custom words","kind": "basic-python-node-operation","parent_node_id": null,"successor_node_id": null,"original_node_id": null,"inputs": [],"outputs": [{"name": "words","file_type": "json","values": [],"is_array": false,"min_count": 1}],"parameters": [],"logs": [],"node_running_status": "CREATED","node_status": "READY","cache_url": "","author": "5e5dd9c7653752f34e1e0be6"}
    ],
    "author": "5e5dd9c7653752f34e1e0be6",
    "starred": false
  }
]
