THIS_FILE := $(lastword $(MAKEFILE_LIST))
DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE_DEV_FILE = ./docker-compose-dev.yml

build_backend:
	PLYNX_IMAGES="backend" ./scripts/build_images.sh

build_frontend:
	PLYNX_IMAGES="ui ui_dev" ./scripts/build_images.sh

build: build_backend build_frontend;

run_tests:
	scripts/run_tests.sh

run_integration_tests:
	@$(MAKE) -f $(THIS_FILE) build_backend
	docker-compose -f $(DOCKER_COMPOSE_DEV_FILE) up --abort-on-container-exit --scale workers=5 --scale frontend=0 --scale test=1

up:
	docker-compose -f $(DOCKER_COMPOSE_FILE) up -d --scale workers=5 --scale test=0
	python -m webbrowser "http://localhost:3001/"

down:
	docker-compose -f $(DOCKER_COMPOSE_FILE) down

dev:
	PLYNX_IMAGES="backend ui_dev" ./scripts/build_images.sh
	python -m webbrowser "http://localhost:3001/"
	docker-compose -f $(DOCKER_COMPOSE_DEV_FILE) up --abort-on-container-exit --scale api=1

build_package:
	python setup.py sdist
	python setup.py bdist_wheel
