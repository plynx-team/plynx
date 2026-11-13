#!/usr/bin/env python
"""PLynx package setup."""
import os
import re

from setuptools import find_packages, setup


def parse_requirements(filename):
    """Load requirements from a requirements file."""
    with open(filename, encoding="utf-8") as req_file:
        return [
            line.strip()
            for line in req_file
            if line.strip() and not line.strip().startswith("#")
        ]


def get_version(package_init_path):
    """Read __version__ without importing the package at build time."""
    with open(package_init_path, encoding="utf-8") as init_file:
        match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_file.read(), re.MULTILINE)
        if not match:
            raise RuntimeError("Unable to find __version__ string.")
        return match.group(1)


DIR = os.path.dirname(os.path.abspath(__file__))
install_requires = parse_requirements(os.path.join(DIR, "requirements.txt"))

# Extra dependencies for storage and development
dev_reqs = parse_requirements(os.path.join(DIR, "requirements-dev.txt"))
gs = [
    "google-cloud-storage>=2.19.0",
]
s3 = [
    "boto3>=1.35.0",
]
ssh = [
    "paramiko>=3.5.0",
]
all_reqs = dev_reqs + gs + s3 + ssh

setup(
    name="plynx",
    version=get_version(os.path.join(DIR, "plynx", "__init__.py")),
    description="ML platform",
    long_description="Interactive, Scalable, Shareable and Reproducible ML experiments",
    url="https://plynx.com",
    author="Ivan Khomyakov",
    author_email="ivan@plynx.com",
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",

        "Environment :: Console",
        "Environment :: Web Environment",

        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",

        "License :: OSI Approved :: Apache Software License",

        "Operating System :: POSIX",

        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",

        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Scientific/Engineering :: Visualization",
    ],
    keywords="data science, machine learning, pipeline, workflow, experiments",
    packages=find_packages(exclude=["scripts", "docker", "tests", "tests.*"]),
    install_requires=install_requires,
    extras_require={
        "all": all_reqs,
        "dev": dev_reqs,
        "gs": gs,
        "s3": s3,
        "ssh": ssh,
    },
    package_data={},
    entry_points={
        "console_scripts": [
            "plynx=plynx.bin:main",
        ],
    },
    project_urls={
        "Demo": "https://plynx.com",
        "Source": "https://github.com/plynx-team/plynx",
    },
)
