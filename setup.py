#!/usr/bin/env python
import plynx
from setuptools import setup, find_packages

install_requires = [
    'cloudpickle>=2.0.0',
    'pymongo>=4.0.1',
    'pyyaml>=5.1.2',
    'passlib>=1.7.1',
    'itsdangerous>=0.24',
    'Flask>=1.0.2',
    'Flask-Cors>=3.0.3',
    'Flask-HTTPAuth>=3.2.3',
    'gevent>=21.12.0',
    'smart-open>=5.2.1',
    'requests>=2.18.4',
    'future>=0.17.1',
]

# Extra dependencies for storage
gs = [
    "google-cloud-storage>=1.13.0",
]
s3 = [
    "boto3>=1.9.62",
]
ssh = [
    "paramiko>=2.4.2",
]
all_remotes = gs + s3 + ssh

setup(
    name='plynx',
    version=plynx.__version__,
    description='ML platform',
    long_description='Interactive, Scalable, Shareable and Reproducible ML experiments',
    url='https://plynx.com',
    author='Ivan Khomyakov',
    author_email='ivan@plynx.com',
    classifiers=[
        'Development Status :: 4 - Beta',

        'Environment :: Console',
        'Environment :: Web Environment',

        'Intended Audience :: Developers',
        'Intended Audience :: Education',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',

        'License :: OSI Approved :: Apache Software License',

        'Operating System :: POSIX',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',

        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'Topic :: Scientific/Engineering :: Visualization',
    ],
    keywords='data science, machine learning, pipeline, workflow, experiments',
    packages=find_packages(exclude=['scripts', 'docker']),
    install_requires=install_requires,
    extras_require={
        'all': all_remotes,
        'gs': gs,
        's3': s3,
        'ssh': ssh,
    },
    package_data={},
    entry_points={
        'console_scripts': [
            'plynx=plynx.bin:main',
        ],
    },
    project_urls={
        'Demo': 'https://plynx.com',
        'Source': 'https://github.com/plynx-team/plynx',
    },
    # plynx.graph.base_nodes.collection uses reference to __file__
    zip_safe=False,
)
