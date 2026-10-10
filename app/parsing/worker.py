"""One-document parser subprocess entry point.

This subprocess adds a wall-clock boundary and optional POSIX resource limits.
It is not a container/OS sandbox and must not be treated as one.
"""
from __future__ import annotations

import argparse
import json
import sys


def _write_response(payload: dict[str, object], exit_code: int = 0) -> None:
    sys.stdout.buffer.write(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    sys.stdout.buffer.flush()
    raise SystemExit(exit_code)


def _set_limit(resource_module, resource_name: int, soft: int, hard: int) -> None:
    try:
        current_soft, current_hard = resource_module.getrlimit(resource_name)
        limit_infinity = resource_module.RLIM_INFINITY
        target_hard = hard if current_hard == limit_infinity else min(hard, current_hard)
        target_soft = soft if current_soft == limit_infinity else min(soft, current_soft)
        target_soft = min(target_soft, target_hard)
        resource_module.setrlimit(resource_name, (target_soft, target_hard))
    except (OSError, ValueError):
        # The parent enforces a wall-clock timeout on every platform.
        # Unsupported or restricted resource limits should not expose raw errors.
        return


def _apply_resource_limits(cpu_seconds: int, memory_mb: int) -> None:
    try:
        import resource
    except ImportError:
        return

    if hasattr(resource, "RLIMIT_CORE"):
        _set_limit(resource, resource.RLIMIT_CORE, 0, 0)
    if hasattr(resource, "RLIMIT_CPU"):
        _set_limit(resource, resource.RLIMIT_CPU, cpu_seconds, cpu_seconds + 2)
    if hasattr(resource, "RLIMIT_AS"):
        memory_bytes = memory_mb * 1024 * 1024
        _set_limit(resource, resource.RLIMIT_AS, memory_bytes, memory_bytes)
    if hasattr(resource, "RLIMIT_NOFILE"):
        _set_limit(resource, resource.RLIMIT_NOFILE, 64, 64)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filename", required=True)
    parser.add_argument("--max-size-bytes", type=int, required=True)
    parser.add_argument("--cpu-seconds", type=int, required=True)
    parser.add_argument("--memory-mb", type=int, required=True)
    args = parser.parse_args()

    _apply_resource_limits(args.cpu_seconds, args.memory_mb)

    from app.parsing.safety import DocumentParseError, DocumentValidationError

    try:
        from app.parsing.dispatcher import parse_document

        content = sys.stdin.buffer.read(args.max_size_bytes + 1)
        document = parse_document(
            args.filename,
            content,
            max_size_bytes=args.max_size_bytes,
        )
        _write_response({"ok": True, "document": document.model_dump(mode="json")})
    except DocumentValidationError as exc:
        _write_response(
            {
                "ok": False,
                "kind": "validation",
                "code": exc.code,
                "message": exc.message,
            }
        )
    except DocumentParseError as exc:
        _write_response({"ok": False, "kind": "parse", "message": str(exc)})
    except Exception:
        _write_response({"ok": False, "kind": "internal"}, exit_code=0)


if __name__ == "__main__":
    main()
