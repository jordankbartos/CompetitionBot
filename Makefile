# PokerBot Makefile

.PHONY: build deploy destroy local up down secrets init-db test help

help:
	@echo "Available commands:"
	@echo "  make build      - Build Lambda packages using Docker"
	@echo "  make deploy     - Build and deploy infrastructure using Terraform"
	@echo "  make destroy    - Destroy infrastructure"
	@echo "  make local      - Run E2E local environment using Docker Compose"
	@echo "  make up         - Alias for make local"
	@echo "  make down       - Stop local environment"
	@echo "  make secrets    - Fetch production secrets for local development"
	@echo "  make init-db    - Initialize local DynamoDB table schema"
	@echo "  make test       - Run unit tests"
	@echo "  make lint       - Run pre-commit hooks on all files"
	@echo "  make install-hooks - Install pre-commit hooks"

build:
	bash scripts/build.sh

deploy: build
	bash scripts/deploy.sh

destroy:
	bash scripts/destroy.sh

local:
	docker-compose -f docker/docker-compose.yml up --build

up: local

down:
	docker-compose -f docker/docker-compose.yml down

secrets:
	bash scripts/fetch_secrets.sh

init-db:
	python3 scripts/init_local_db.py

test:
	PYTHONPATH=poker_worker:poker_handler python3 -m unittest discover tests

lint:
	pre-commit run --all-files

install-hooks:
	pre-commit install
