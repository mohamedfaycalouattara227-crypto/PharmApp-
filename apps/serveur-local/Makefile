.DEFAULT_GOAL := help
PY  ?= python
PIP ?= $(PY) -m pip

.PHONY: help install install-dev migrate run worker beat shell test test-cov lint format security audit clean docker-up docker-down

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "\033[36m%-18s\033[0m %s\n",$$1,$$2}'

install: ## Installer les dépendances de production
	$(PIP) install -r requirements.txt

install-dev: ## Installer prod + dev + hooks
	$(PIP) install -r requirements.txt -r requirements-dev.txt
	pre-commit install

migrate: ## Appliquer les migrations
	$(PY) manage.py migrate --noinput

run: ## Lancer le serveur de développement
	$(PY) manage.py runserver 0.0.0.0:8000

worker: ## Lancer un worker Celery
	celery -A pharmapp worker -l info

beat: ## Lancer Celery beat
	celery -A pharmapp beat -l info

shell: ## Shell Django
	$(PY) manage.py shell

test: ## Exécuter la suite de tests
	pytest -x -q

test-cov: ## Tests avec couverture (>= 85 % requis)
	pytest --cov=. --cov-report=term-missing --cov-report=html --cov-fail-under=85

lint: ## Lint (ruff + flake8 + mypy)
	ruff check .
	flake8 .
	mypy --ignore-missing-imports gestion infrastructure api pharmapp

format: ## Formatage (black + isort)
	black .
	isort .

security: ## Audit de sécurité (bandit + pip-audit)
	bandit -q -r gestion infrastructure api pharmapp -x tests
	pip-audit --strict
	$(PY) manage.py check --deploy --fail-level WARNING

audit: security ## Alias

clean: ## Nettoyer les fichiers générés
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage rapports/couverture staticfiles build dist *.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

docker-up: ## Démarrer la stack Docker
	docker compose up -d --build

docker-down: ## Arrêter la stack Docker
	docker compose down
