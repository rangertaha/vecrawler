# vecrawler — common dev & ops tasks.
# Run `make` or `make help` to list available targets.

COMPOSE := docker compose -f infra/docker-compose.yml
MANAGE  := python manage.py

# Crawler slug/name for `make crawl` (override: `make crawl c=my-site`).
c ?=

.DEFAULT_GOAL := help

.PHONY: help install migrate superuser run metadata crawl \
        build up down logs ps crawler clean

help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

## ---- Local (host) ---------------------------------------------------------

install: ## Install Python dependencies
	pip install -r requirements.txt

migrate: ## Apply database migrations
	$(MANAGE) migrate

superuser: ## Create an admin superuser
	$(MANAGE) createsuperuser

run: ## Run the Django admin/site (http://127.0.0.1:8000)
	$(MANAGE) runserver

metadata: ## Seed web-metadata extraction templates
	$(MANAGE) createmetadata

crawl: ## Run a crawl: make crawl c=<slug-or-name>
	@test -n "$(c)" || { echo "usage: make crawl c=<slug-or-name>"; exit 1; }
	$(MANAGE) runcrawler $(c)

## ---- Docker (infra/docker-compose.yml) ------------------------------------

build: ## Build the site and crawler images
	$(COMPOSE) build

up: ## Start redis, splash and the site (detached)
	$(COMPOSE) up -d redis splash site

down: ## Stop and remove all stack containers
	$(COMPOSE) down

logs: ## Tail logs from the running stack
	$(COMPOSE) logs -f

ps: ## Show stack container status
	$(COMPOSE) ps

crawler: ## Run a crawl in a container: make crawler c=<slug-or-name>
	@test -n "$(c)" || { echo "usage: make crawler c=<slug-or-name>"; exit 1; }
	$(COMPOSE) run --rm crawler runcrawler $(c)

## ---- Housekeeping ---------------------------------------------------------

clean: ## Remove Python caches and crawl artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf httpcache
