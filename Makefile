THIS_FILE := $(lastword $(MAKEFILE_LIST))
ABSOLUTE_PATH := $(notdir $(THIS_FILE))
DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE_DEV_FILE = ./docker-compose-dev.yml

build_backend:
	PLYNX_IMAGES="backend" ./scripts/build_images.sh

build_frontend:
	PLYNX_IMAGES="ui ui_dev" ./scripts/build_images.sh

build: build_backend build_frontend;

run_tests:
	mkdir -p $(CURDIR)/data/resources
	@$(MAKE) -f $(THIS_FILE) build_backend
	docker-compose -f $(DOCKER_COMPOSE_DEV_FILE) up --abort-on-container-exit --scale workers=5 --scale frontend=0 --scale test=1

run_frontend:
	cd ./ui; DISABLE_ESLINT_PLUGIN=true npm start

up:
	mkdir -p ./data/resources
	python -m webbrowser "http://localhost:3001/"
	docker-compose -f $(DOCKER_COMPOSE_FILE) up --scale workers=1

up_local_service:
	python -m webbrowser "http://localhost:3001/"
	docker-compose -f $(DOCKER_COMPOSE_FILE) up --scale workers=0 --scale test=0

up_local_worker:
	./scripts/run_local_worker.sh

dev:
	mkdir -p ./data/resources
	PLYNX_IMAGES="backend ui_dev" ./scripts/build_images.sh
	python -m webbrowser "http://localhost:3001/"
	docker-compose -f $(DOCKER_COMPOSE_DEV_FILE) up --abort-on-container-exit --scale api=1 --scale test=0 --scale frontend=0 --scale workers=0

build_package:
	python setup.py sdist
	python setup.py bdist_wheel

pytest:
	python -m pytest
