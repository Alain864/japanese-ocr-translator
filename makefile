.PHONY: help build up down run test clean logs shell

help:
	@echo "Japanese OCR Translator - Available Commands"
	@echo "============================================="
	@echo "make build       - Build Docker image"
	@echo "make up          - Start services"
	@echo "make down        - Stop services"
	@echo "make run PDF=<path> - Process a PDF file"
	@echo "make test        - Run tests"
	@echo "make clean       - Clean output files"
	@echo "make logs        - View container logs"
	@echo "make shell       - Open shell in container"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

run:
	@if [ -z "$(PDF)" ]; then \
		echo "Usage: make run PDF=data/input/yourfile.pdf"; \
	else \
		docker-compose run --rm app python src/main.py $(PDF); \
	fi

test:
	docker-compose run --rm app pytest tests/ -v

clean:
	rm -rf data/output/*
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

logs:
	docker-compose logs -f

shell:
	docker-compose run --rm app bash