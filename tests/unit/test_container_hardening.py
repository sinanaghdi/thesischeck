"""Ensure the checked-in Docker demo profile keeps its expected runtime boundaries."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_compose_profile_has_local_only_and_constrained_runtime() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    web = compose["services"]["web"]
    edge = compose["services"]["edge"]

    assert web.get("ports", []) == []
    assert edge["ports"] == ["127.0.0.1:8000:8080"]
    assert edge["read_only"] is True
    assert edge["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in edge["security_opt"]
    assert edge["pids_limit"] == 64
    assert edge["mem_limit"] == "128m"
    assert edge["entrypoint"] == ["nginx", "-g", "daemon off;"]
    assert any(item.startswith("/run:") and "uid=101" in item for item in edge["tmpfs"])
    assert any(item.startswith("/var/cache/nginx:") and "uid=101" in item for item in edge["tmpfs"])
    assert web["read_only"] is True
    assert web["init"] is True
    assert web["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in web["security_opt"]
    assert web["pids_limit"] == 128
    assert web["mem_limit"] == "2g"
    assert float(web["cpus"]) == 2.0
    assert web["ulimits"]["nofile"] == {"soft": 256, "hard": 512}
    assert len(web["tmpfs"]) == 1
    assert all(flag in web["tmpfs"][0] for flag in ("noexec", "nosuid", "nodev", "size=192m"))
    assert web.get("volumes", []) == []


def test_image_runs_as_non_root_with_bounded_uvicorn_concurrency() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "RUN useradd --create-home --uid 10001 appuser" in dockerfile
    assert "\nUSER appuser\n" in dockerfile
    assert '"--limit-concurrency", "4"' in dockerfile


def test_example_environment_defaults_debug_off_and_limits_are_documented() -> None:
    environment = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "DEBUG=false" in environment
    assert "LLM_MODE=off" in environment
    assert "INSPECTION_RATE_LIMIT=20" in environment
    assert "PARSER_WORKER_CONCURRENCY=2" in environment
