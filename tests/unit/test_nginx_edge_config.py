"""Guard the trusted HTTP edge request limits and non-buffered upload path."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_nginx_edge_limits_body_rate_connections_and_slow_clients() -> None:
    config = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")

    assert "listen 8080;" in config
    assert "client_max_body_size 31m;" in config
    assert "client_body_timeout 15s;" in config
    assert "send_timeout 65s;" in config
    assert "limit_req_zone $binary_remote_addr zone=inspection_per_ip:10m rate=10r/m;" in config
    assert "limit_conn_zone $binary_remote_addr zone=inspection_conn_per_ip:10m;" in config
    assert config.count("limit_req zone=inspection_per_ip burst=5 nodelay;") == 2
    assert config.count("limit_conn inspection_conn_per_ip 2;") == 2
    assert config.count("proxy_request_buffering off;") == 2
    assert config.count("proxy_read_timeout 60s;") == 3


def test_edge_uses_fixed_internal_upstream_not_user_supplied_destination() -> None:
    config = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")

    assert config.count("proxy_pass http://web:8000;") == 3
    assert "proxy_pass $arg_" not in config
    assert "proxy_pass http://" in config
    assert "X-Real-IP $remote_addr" in config
    assert "X-Forwarded-For $proxy_add_x_forwarded_for" in config
