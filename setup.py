#!/usr/bin/env python
import os
import plynx
from setuptools import setup, find_packages


def parse_requirements(filename):
    """ load requirements from a pip requirements file """
    lineiter = (line.strip() for line in open(filename))
    return [line for line in lineiter if line and not line.startswith("#")]


DIR = os.path.dirname(os.path.abspath(__file__))
install_requires = parse_requirements(os.path.join(DIR, 'requirements.txt'))

# Extra dependencies for storage
dev_reqs = parse_requirements(os.path.join(DIR, 'requirements-dev.txt'))
gs = [
    "google-cloud-storage>=1.13.0",
]
s3 = [
    "boto3>=1.9.62",
]
ssh = [
    "paramiko>=2.4.2",
]
all_reqs = dev_reqs + gs + s3 + ssh

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

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',

        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'Topic :: Scientific/Engineering :: Visualization',
    ],
    keywords='data science, machine learning, pipeline, workflow, experiments',
    packages=find_packages(exclude=['scripts', 'docker']),
    install_requires=install_requires,
    extras_require={
        'all': all_reqs,
        'dev': dev_reqs,
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
