"""Exercise upgrade input validation before the reusable VM job starts."""

import os
from pathlib import Path
import subprocess

import pytest
import yaml


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/upgrade-test.yml"
DOC = yaml.safe_load(WORKFLOW.read_text())
JOBS = DOC["jobs"]
VALIDATE = JOBS["validate"]["steps"][0]["run"]
OLD = "registry.example:5000/org/image@sha256:" + "a" * 64
NEW = "registry.example:5000/org/image@sha256:" + "b" * 64


def validate(previous, image=NEW):
    return subprocess.run(
        ["bash", "-e", "-c", VALIDATE],
        env={**os.environ, "PREVIOUS_IMAGE": previous, "IMAGE": image},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("previous", "image", "message"),
    [
        ("registry.example:5000/org/image:old", NEW, "pinned"),
        (NEW, NEW, "differ"),
        ("registry.example:5000/other/image@sha256:" + "a" * 64, NEW, "same repository"),
    ],
)
def test_invalid_previous_image_stops_before_boot(previous, image, message):
    result = validate(previous, image)
    assert result.returncode != 0
    assert "::error::" in result.stdout and message in result.stdout
    assert JOBS["upgrade-test"]["needs"] == "validate"


@pytest.mark.parametrize("previous", ["", OLD, OLD.replace("@", ":old@")])
def test_empty_or_valid_previous_image_is_accepted(previous):
    assert validate(previous).returncode == 0


def test_previous_image_is_exposed_and_forwarded():
    triggers = DOC[True]  # PyYAML interprets the YAML 1.1 key 'on' as True.
    for trigger in ("workflow_call", "workflow_dispatch"):
        assert "previous_image" in triggers[trigger]["inputs"]
    inputs = JOBS["upgrade-test"]["with"]
    assert inputs["image"] == "${{ inputs.previous_image || inputs.image }}"
    assert inputs["target-image"] == "${{ inputs.previous_image && inputs.image || '' }}"
    assert "needs.validate.result == 'failure'" in JOBS["report"]["outputs"]["result"]
