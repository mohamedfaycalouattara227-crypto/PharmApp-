.DEFAULT_GOAL := aide
SHELL := /bin/bash
VERSION := $(shell tr -d '[:space:]' < VERSION)

.PHONY: aide demarrer arreter logs installer hooks test test-serveur test-client lint securite gouvernance verifier etat ci

aide: ## Afficher cette aide
	@echo "PharmApp v$(VERSION) — cibles disponibles :"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n",$$1,$$2}'

demarrer: ## Démarrer TOUT l'environnement (base, cache, API, worker, poste client)
	@test -f .env || (cp .env.exemple .env && echo "→ .env créé depuis .env.exemple")
	PHARMAPP_VERSION=$(VERSION) docker compose -f infra/docker-compose.yml up -d --build
	@echo "Serveur local : http://localhost:8000/api/v1/version/"
	@echo "Poste client  : http://localhost:3000"

arreter: ## Arrêter l'environnement
	docker compose -f infra/docker-compose.yml down

logs: ## Suivre les journaux
	docker compose -f infra/docker-compose.yml logs -f --tail=100

hooks: ## Activer les hooks Git du dépôt
	bash outils/installer_hooks.sh

test-serveur: ## Tests du serveur local
	cd apps/serveur-local && pytest -q

test-client: ## Tests du poste client
	cd apps/poste-client && npm run test

test: test-serveur test-client ## Toute la suite de tests

lint: ## Lint et typage
	cd apps/serveur-local && ruff check . && mypy --ignore-missing-imports gestion infrastructure api pharmapp
	cd apps/poste-client && npm run typecheck

securite: ## Analyse de sécurité
	cd apps/serveur-local && bandit -q -r gestion infrastructure api pharmapp -x tests && pip-audit --strict

gouvernance: ## Contrôles de gouvernance (versions uniques, documents de statut)
	python3 outils/verifier_version.py
	python3 outils/verifier_documents_statut.py

etat: ## Régénérer docs/ETAT_DU_PROJET.md
	python3 outils/generer_etat_projet.py

verifier: gouvernance lint test ## Tout vérifier localement avant de pousser
ci: verifier securite ## Équivalent local de la chaîne CI
