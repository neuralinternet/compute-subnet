#!/bin/bash
python3 -m pip install pre-commit
pre-commit install --install-hooks
pre-commit install -t commit-msg
pre-commit install -t post-checkout
pre-commit install -t pre-commit
pre-commit install -t pre-push
