#!/usr/bin/env bash

set -e

poetry install
poetry run uvicorn example.main:app --reload