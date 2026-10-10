"""Guard private parser Compose topology and resource settings."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_parser_service_has_no_host_port_and_internal_only_network() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    parser = services["parser"]
    web = services["web"]
    assert parser.get("ports", []) == []
    assert parser["networks"] == ["parser-private"]
    assert compose["networks"]["parser-private"]["internal"] is True
    assert "parser-private" in web["networks"]
    assert "edge-private" in web["networks"]
    edge = services["edge"]
    assert edge["networks"] == ["edge-private"]
    assert edge["volumes"] == ["./deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro"]
    assert web["environment"]["PARSER_BACKEND"] == "service"
    assert web["environment"]["PARSER_SERVICE_URL"] == "http://parser:8001"
    assert parser["environment"]["DEBUG"] == "false"


def test_parser_container_has_separate_restricted_environment_and_runtime() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    parser = compose["services"]["parser"]
    env = parser["environment"]
    assert "DATABASE_URL" not in env
    assert "JWT_SECRET" not in env
    assert "LLM_API_KEY" not in env
    assert "PARSER_SERVICE_TOKEN" in env
    assert parser["read_only"] is True
    assert parser["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in parser["security_opt"]
    assert parser["pids_limit"] == 96
    assert parser["mem_limit"] == "1536m"
    assert float(parser["cpus"]) == 1.0
    assert parser["healthcheck"]["retries"] == 5


def test_compose_requires_a_nonempty_internal_service_token() -> None:
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "${PARSER_SERVICE_TOKEN:?Set PARSER_SERVICE_TOKEN in .env}" in compose_text
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "PARSER_SERVICE_TOKEN=" in env_example
    assert "PARSER_SERVICE_TIMEOUT_SECONDS=45" in env_example
