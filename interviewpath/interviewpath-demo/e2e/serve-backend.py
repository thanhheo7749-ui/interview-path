"""Starts the API with a fixed fake extraction, so uploaded fixture documents yield known facts. Test use only."""
import json
import os
import sys

import uvicorn

from app.brain import fake_demo

fixture_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "extraction.json")
with open(fixture_path, encoding="utf-8") as handle:
    fixture = json.load(handle)
fake_demo.load_extraction_fixture(fixture["nodes"], fixture["edges"])
uvicorn.run("app.main:app", port=int(sys.argv[1]))
