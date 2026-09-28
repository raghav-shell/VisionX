"""``visionsentinel`` command-line entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable

from .. import __version__
from ..core.airgap import pin_offline_environment
from ..core.errors import UnsafeInputError, VisionSentinelError
from . import commands

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_UNSAFE = 3
EXIT_INTERNAL = 70


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="visionsentinel",
        description="VisionSentinel — air-gapped computer-vision integrity and assurance.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run 'visionsentinel <command> --help' for command options.",
    )
    parser.add_argument("--version", action="version", version=f"visionsentinel {__version__}")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="increase log verbosity")
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    commands.register_all(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    pin_offline_environment()
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING - 10 * min(args.verbose, 2),
                        format="%(levelname)s %(name)s: %(message)s")
    handler: Callable[[argparse.Namespace], int] | None = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return EXIT_USAGE
    try:
        return int(handler(args) or 0)
    except UnsafeInputError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        if exc.hint:
            print(f"hint: {exc.hint}", file=sys.stderr)
        return EXIT_UNSAFE
    except VisionSentinelError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if exc.hint:
            print(f"hint: {exc.hint}", file=sys.stderr)
        return EXIT_USAGE
    except FileNotFoundError as exc:
        print(f"error: file not found: {exc.filename or exc}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - last-resort operator message
        logging.getLogger("visionsentinel").debug("unhandled error", exc_info=True)
        print(f"internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("hint: re-run with -vv for a traceback", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
