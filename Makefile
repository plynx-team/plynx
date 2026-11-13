THIS_FILE := $(lastword $(MAKEFILE_LIST))
DOCKER_COMPOSE := $(shell command -v docker-compose >/dev/null 2>&1 && echo "docker-compose" || echo "docker compose")
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
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_DEV_FILE) up --abort-on-container-exit --scale workers=5 --scale frontend=0 --scale test=1

run_frontend:
	cd ./ui && npm start

up:
	mkdir -p ./data/resources
	python3 -m webbrowser "http://localhost:3001/"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up --scale workers=1

up_local_service:
	python3 -m webbrowser "http://localhost:3001/"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) up --scale workers=0 --scale test=0

up_local_worker:
	./scripts/run_local_worker.sh

dev:
	mkdir -p ./data/resources
	PLYNX_IMAGES="backend ui_dev" ./scripts/build_images.sh
	python3 -m webbrowser "http://localhost:3001/"
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_DEV_FILE) up --abort-on-container-exit --scale api=1 --scale test=0 --scale frontend=1 --scale workers=2

build_package:
	python3 -m build

pytest:
	python3 -m pytest
