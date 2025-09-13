# avsafe_descriptors/io/json_io.py
from __future__ import annotations

import io
import os
import json
import gzip
import tempfile
from pathlib import Path
from typing import Iterable, Iterator, Callable, Optional, Union, TextIO, Any, Literal

PathLike = Union[str, os.PathLike[str]]
OnError = Literal["raise", "skip"]

__all__ = [
    "write_jsonl",
    "append_jsonl",
    "read_jsonl",
    "iter_jsonl",
]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_replace(tmp_path: Path, final_path: Path) -> None:
    # Make replacement as atomic as the OS allows
    os.replace(tmp_path, final_path)


def _open_for_write_atomic(
    path: Path,
    *,
    gzip_enabled: bool,
    encoding: str = "utf-8",
    newline: str = "\n",
) -> tuple[TextIO, Path]:
    """
    Create a temp file next to 'path' and return (fp, tmp_path).
    Caller must close fp and call _atomic_replace(tmp_path, path).
    """
    _ensure_parent(path)
    suffix = ".tmp.gz" if gzip_enabled else ".tmp"
    tmp = tempfile.NamedTemporaryFile(
        mode="wb" if gzip_enabled else "w",
        delete=False,
        dir=str(path.parent),
        prefix=path.name + ".",
        suffix=suffix,
    )
    tmp_path = Path(tmp.name)

    if gzip_enabled:
        # Wrap the binary temp file with gzip text wrapper
        gz = gzip.GzipFile(fileobj=tmp, mode="wb")
        # Encode text through TextIOWrapper to control newline & encoding
        text_fp = io.TextIOWrapper(gz, encoding=encoding, newline=newline)
        return text_fp, tmp_path
    else:
        # tmp is already a text fp in this branch
        # but NamedTemporaryFile(...) returned a file handle; ensure newline/encoding by reopening
        tmp.close()
        text_fp = open(tmp_path, "w", encoding=encoding, newline=newline)
        return text_fp, tmp_path


def _should_gzip(path: Path, gzip_flag: Optional[bool]) -> bool:
    if gzip_flag is not None:
        return bool(gzip_flag)
    # Auto-detect by extension if not specified
    return path.suffix.lower() == ".gz"


def write_jsonl(
    path: PathLike,
    records: Iterable[dict[str, Any]],
    *,
    append: bool = False,
    atomic: bool = True,
    gzip_enabled: Optional[bool] = None,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
) -> int:
    """
    Write an iterable of dict records to a JSON Lines (NDJSON) file.

    - If append=True, appends to the existing file (non-atomic).
    - If atomic=True (default), writes to a temp file and replaces the target in one step.
    - gzip_enabled: True to force gzip, False to force plain text, None (default) to infer from '.gz' extension.

    Returns the number of records written.
    """
    target = Path(path)
    gz = _should_gzip(target, gzip_enabled)

    if append:
        # Appending can't be atomic; open appropriately
        if gz:
            fp: TextIO
            # 'at' is not supported by gzip.GzipFile; we open binary append then wrap
            # To keep it simple and robust, read-append-recompress is overkill.
            # Instead, we throw if append+gzip to avoid corrupting archives.
            raise ValueError("append=True is not supported for gzip files; write a new .gz instead.")
        _ensure_parent(target)
        with open(target, "a", encoding="utf-8", newline="\n") as f:
            count = 0
            for rec in records:
                if not isinstance(rec, dict):
                    raise TypeError(f"Each record must be dict, got {type(rec)!r}")
                f.write(json.dumps(rec, ensure_ascii=ensure_ascii, sort_keys=sort_keys))
                f.write("\n")
                count += 1
        return count

    if not atomic:
        # Non-atomic, overwrite
        if gz:
            with gzip.open(target, "wt", encoding="utf-8", newline="\n") as f:
                count = 0
                for rec in records:
                    if not isinstance(rec, dict):
                        raise TypeError(f"Each record must be dict, got {type(rec)!r}")
                    f.write(json.dumps(rec, ensure_ascii=ensure_ascii, sort_keys=sort_keys))
                    f.write("\n")
                    count += 1
                return count
        else:
            _ensure_parent(target)
            with open(target, "w", encoding="utf-8", newline="\n") as f:
                count = 0
                for rec in records:
                    if not isinstance(rec, dict):
                        raise TypeError(f"Each record must be dict, got {type(rec)!r}")
                    f.write(json.dumps(rec, ensure_ascii=ensure_ascii, sort_keys=sort_keys))
                    f.write("\n")
                    count += 1
                return count

    # Atomic path
    fp, tmp_path = _open_for_write_atomic(target, gzip_enabled=gz, encoding="utf-8", newline="\n")
    try:
        count = 0
        for rec in records:
            if not isinstance(rec, dict):
                raise TypeError(f"Each record must be dict, got {type(rec)!r}")
            fp.write(json.dumps(rec, ensure_ascii=ensure_ascii, sort_keys=sort_keys))
            fp.write("\n")
            count += 1
        fp.flush()
        # Ensure bytes hit disk (temp file descriptor may be nested)
        try:
            os.fsync(fp.buffer.fileno())  # type: ignore[attr-defined]
        except Exception:
            try:
                os.fsync(fp.fileno())  # for plain text
            except Exception:
                pass
    finally:
        fp.close()

    _atomic_replace(tmp_path, target)
    return count


def append_jsonl(
    path: PathLike,
    records: Iterable[dict[str, Any]],
    *,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
) -> int:
    """
    Convenience wrapper for appending JSONL to a plain-text file.
    (Gzip append isn’t supported reliably; write a new file instead.)
    """
    return write_jsonl(
        path,
        records,
        append=True,
        atomic=False,
        gzip_enabled=False,
        ensure_ascii=ensure_ascii,
        sort_keys=sort_keys,
    )


def _open_maybe_gzip(path: Path, encoding: str = "utf-8") -> TextIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding=encoding)
    return open(path, "r", encoding=encoding)


def read_jsonl(
    path: PathLike,
    *,
    on_error: OnError = "raise",
    validate: Optional[Callable[[dict[str, Any]], None]] = None,
) -> Iterator[dict[str, Any]]:
    """
    Stream records from a JSON Lines file (.jsonl or .jsonl.gz).
    - on_error: "raise" (default) or "skip" to skip malformed lines
    - validate: optional callable(record) -> None (raise to reject a record)
    """
    p = Path(path)
    with _open_maybe_gzip(p) as f:
        yield from iter_jsonl(f, on_error=on_error, validate=validate)


def iter_jsonl(
    fp: TextIO,
    *,
    on_error: OnError = "raise",
    validate: Optional[Callable[[dict[str, Any]], None]] = None,
) -> Iterator[dict[str, Any]]:
    """
    Iterate JSONL records from an already-open text file-like object.
    Skips blank lines and comment lines beginning with '#'.
    """
    line_no = 0
    for raw in fp:
        line_no += 1
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise TypeError(f"Line {line_no}: JSON value must be an object (dict), got {type(obj)!r}")
            if validate is not None:
                validate(obj)
            yield obj
        except Exception as e:
            if on_error == "skip":
                # Optionally, you could log this; keeping silent by design here.
                continue
            raise
