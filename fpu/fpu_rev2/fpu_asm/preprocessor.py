from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Optional, Union


class AssemblerError(Exception):
    """Base exception for microcode assembler errors with source provenance."""

    def __init__(
        self,
        message: str,
        file_path: Optional[Union[str, Path]] = None,
        line: Optional[int] = None,
        column: Optional[int] = None,
    ):
        self.message = message
        self.file_path = Path(file_path) if file_path is not None else None
        self.line = line
        self.column = column
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.file_path is not None and self.line is not None:
            col_str = f":{self.column}" if self.column is not None else ""
            return f"{self.file_path}:{self.line}{col_str}: {self.message}"
        if self.file_path is not None:
            return f"{self.file_path}: {self.message}"
        return self.message


class AssemblySyntaxError(AssemblerError):
    """Raised when syntax parsing fails."""

    pass


class IncludeError(AssemblerError):
    """Raised when an included file cannot be located or is malformed."""

    pass


class CircularIncludeError(IncludeError):
    """Raised when an include cycle is detected."""

    pass


class UndefinedSymbolError(AssemblerError, KeyError):
    """Raised when a referenced label or symbol is not defined."""

    pass


@dataclass(frozen=True)
class SourceLocation:
    """Provenance tracking for each line in the preprocessed microcode image."""

    file_path: Path
    line_number: int  # 1-based line number in original file


@dataclass
class PreprocessedSource:
    """Preprocessed microcode text with 1:1 line source mapping."""

    text: str
    source_map: List[SourceLocation]

    def get_location(self, line: int) -> SourceLocation:
        """Returns the original file and line for a 1-based line in text."""
        if 1 <= line <= len(self.source_map):
            return self.source_map[line - 1]
        if self.source_map:
            return self.source_map[-1]
        return SourceLocation(file_path=Path("<string>"), line_number=line)


class Preprocessor:
    """Textual preprocessor handling recursive .include directives with source mapping."""

    INCLUDE_PATTERN = re.compile(
        r"^\s*\.include\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s;]+))\s*(?:;.*)?$",
        re.IGNORECASE,
    )
    MALFORMED_INCLUDE_PATTERN = re.compile(r"^\s*\.include\b", re.IGNORECASE)

    def __init__(self, include_paths: Optional[List[Union[str, Path]]] = None):
        self.include_paths: List[Path] = [
            Path(p).resolve() for p in (include_paths or [])
        ]

    def process_file(self, file_path: Union[str, Path]) -> PreprocessedSource:
        """Preprocesses a file from disk."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise IncludeError(f"File not found: '{file_path}'", file_path=path)

        text = path.read_text(encoding="utf-8")
        return self._process_text(text, current_file=path)

    def process_string(
        self,
        source: str,
        base_dir: Optional[Union[str, Path]] = None,
        filename: str = "<string>",
    ) -> PreprocessedSource:
        """Preprocesses a raw string, resolving relative includes from base_dir."""
        base_path = Path(base_dir).resolve() if base_dir is not None else Path.cwd()
        current_file = base_path / filename
        return self._process_text(source, current_file=current_file)

    def _process_text(self, text: str, current_file: Path) -> PreprocessedSource:
        lines = text.splitlines()
        combined_lines: List[str] = []
        source_map: List[SourceLocation] = []
        include_stack: List[Path] = [current_file]

        self._process_lines(lines, current_file, include_stack, combined_lines, source_map)
        combined_text = "\n".join(combined_lines) + "\n" if combined_lines else "\n"
        return PreprocessedSource(text=combined_text, source_map=source_map)

    def _process_lines(
        self,
        lines: List[str],
        current_file: Path,
        include_stack: List[Path],
        combined_lines: List[str],
        source_map: List[SourceLocation],
    ) -> None:
        for line_idx, line in enumerate(lines, start=1):
            match = self.INCLUDE_PATTERN.match(line)
            if match:
                target_str = match.group(1) or match.group(2) or match.group(3)
                target_path = self._resolve_include_path(target_str, current_file, line_idx)

                if target_path in include_stack:
                    chain = " -> ".join([p.name for p in include_stack] + [target_path.name])
                    raise CircularIncludeError(
                        f"Circular include detected: {chain}",
                        file_path=current_file,
                        line=line_idx,
                    )

                target_text = target_path.read_text(encoding="utf-8")
                target_lines = target_text.splitlines()

                include_stack.append(target_path)
                try:
                    self._process_lines(
                        target_lines,
                        target_path,
                        include_stack,
                        combined_lines,
                        source_map,
                    )
                finally:
                    include_stack.pop()

            elif self.MALFORMED_INCLUDE_PATTERN.match(line):
                raise IncludeError(
                    f"Malformed .include directive: '{line.strip()}'",
                    file_path=current_file,
                    line=line_idx,
                )
            else:
                combined_lines.append(line)
                source_map.append(SourceLocation(file_path=current_file, line_number=line_idx))

    def _resolve_include_path(self, target_str: str, current_file: Path, line_idx: int) -> Path:
        # 1. Try relative to current file's parent directory
        candidate = (current_file.parent / target_str).resolve()
        if candidate.is_file():
            return candidate

        # 2. Try each configured search path
        for search_dir in self.include_paths:
            candidate = (search_dir / target_str).resolve()
            if candidate.is_file():
                return candidate

        raise IncludeError(
            f"Include file not found: '{target_str}'",
            file_path=current_file,
            line=line_idx,
        )
