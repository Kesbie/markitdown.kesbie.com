"""md2x — convert tài liệu sang Markdown, có web UI và CLI."""

from .core import ConversionResult, Converter, get_converter

__all__ = ["ConversionResult", "Converter", "get_converter", "main"]
__version__ = "0.1.0"


def main() -> int:
    from .cli import main as _main

    return _main()
