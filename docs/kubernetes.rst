
.. _plynx-kubernetes:

========================
Kubernetes deployment
========================

This section covers basic deployment to google cloud kubernetes service.

.. contents:: Table of Contents
    :local:
    :depth: 1

===========================


.. _plynx-kubernetes-create-cluster:

Step 0: Create a cluster
=========================

`Kubernetes on Google Cloud Quickstart <https://cloud.google.com/kubernetes-engine/docs/quickstart>`_


First we will need to set up `gcloud` utils.

.. code-block:: bash

    gcloud config set project [YOUR_PROJECT_ID]
    gcloud config set compute/zone [YOUR_ZONE]

Create cluster with a custom name.

.. code-block:: bash

    export CLUSTER_NAME=[CLUSTER_NAME]
    gcloud container clusters create ${CLUSTER_NAME}
    gcloud container clusters get-credentials ${CLUSTER_NAME}


Resize cluster (optional).

.. code-block:: bash

    # Optional
    gcloud container clusters resize ${CLUSTER_NAME} --node-pool default-pool --num-nodes 3


.. _plynx-kubernetes-create-service-account:

Step 1: Create service account credentials
==========================================

`Reference to Google Cloud docs <https://cloud.google.com/kubernetes-engine/docs/tutorials/authenticating-to-cloud-platform#step_3_create_service_account_credentials>`_

1. Create service account: *IAM & admin -> Service accounts -> Create Service Account*

2. Select custom username.

3. Add roles: *Storage Object Creator* and *Storage Object Viewer*

4. Create *json* key. It will download a file *plynx-\*.json*, i.e. */Users/username/Downloads/plynx-197007-2aeb7faedf34.json*

5. Create a new bucket

.. code-block:: bash

    # example YOUR_BUCKET_PATH=gs://plynx-test
    export BUCKET=[YOUR_BUCKET_PATH]
    gsutil mb ${BUCKET}


6. **IMPORTANT!** Add legacy permissions in Console User Interface.

    a. Go to *Storage -> [YOUR_BUCKET_PATH] -> Permissions*.
    b. In your User Account modify *Role(s)*: add *Storage Legacy Bucket Reader* and *Storage Legacy Bucket Writer*

7. Store credentials in kubernetes.

.. code-block:: bash

    kubectl create secret generic gs-key --from-file=key.json=[PATH_TO_KEY_JSON]

8. Configure env variable mapping

.. code-block:: bash

    kubectl create configmap storage-config --from-literal=storage-scheme=gs --from-literal=storage-prefix=${BUCKET}/resources/




.. _plynx-kubernetes-secret-key:

Step 2: Create secret key
===========================

Generate new secret key and write it to the file. Reuse the file in kubernetes secrets.

.. code-block:: bash

    openssl rand -base64 16 | tr -d '\n' > secret.txt
    kubectl create secret generic secret-key --from-file=secret.txt=./secret.txt




.. _plynx-kubernetes-create-mongodb-pod:

Step 3: Create MongoDB pod
===========================

Clone configuration files.

.. code-block:: bash

    git clone https://github.com/plynx-team/plynx.git
    cd plynx/kubernetes


To create the MongoDB pod, run these two commands:

.. code-block:: bash

    kubectl apply -f googlecloud_ssd.yaml

    kubectl apply -f mongo-statefulset.yaml




.. _plynx-kubernetes-plynx-pods:

Step 4: PLynx pods
==========================

Create PLynx pods and services.

.. code-block:: bash

    kubectl apply -f backend-service.yaml
    kubectl apply -f backend-deployment.yaml
    kubectl expose deployment backend --type=NodePort --name=backend-server

    kubectl apply -f frontend-deployment.yaml
    kubectl apply -f frontend-service.yaml

    kubectl apply -f router.yaml

    kubectl apply -f master-service.yaml
    kubectl apply -f master-deployment.yaml

    kubectl apply -f workers-deployment.yaml


.. _plynx-kubernetes-init-users:

Step 5: Init users
===========================

List of pods:

.. code-block:: bash

    kubectl get pods

    # NAME                        READY   STATUS    RESTARTS   AGE
    # backend-8665dc7967-7wlks    1/1     Running   0          9m49s
    # frontend-57857fc888-6gj57   1/1     Running   0          124m
    # master-7f686d64f6-6shbq     1/1     Running   0          122m
    # mongo-0                     2/2     Running   0          144m
    # worker-6d5fc66f55-5g7q2     1/1     Running   5          76m
    # worker-6d5fc66f55-5tsdf     1/1     Running   0          11m
    # worker-6d5fc66f55-9vjv8     1/1     Running   0          11m

ssh to master pod.

.. code-block:: bash

    kubectl exec -t -i master-7f686d64f6-6shbq bash


When connected, create a user.

.. code-block:: bash

    plynx users --mode create_user --db-host mongo --username foo --password woo


Step 6: Try PLynx
===========================

1. Go to *Kubernetes Engine -> Services and Ingress*
2. Select Ingress called *api-router*
3. Go to the page located at *Load balancer IP*.
4. Use username *foo* and password *woo*
