import argparse
import hashlib
import importlib
from pathlib import Path


DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Vendor a local embedding model for offline use.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, default=Path("backend/data/models"))
    args = parser.parse_args()

    module = importlib.import_module("fastembed")
    module.TextEmbedding(model_name=args.model, cache_dir=str(args.out))

    checksums = args.out / "SHA256SUMS"
    lines = [
        f"{sha256_file(path)}  {path.relative_to(args.out).as_posix()}"
        for path in sorted(args.out.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"vendored {args.model} to {args.out}")
    print(f"set EMBEDDING_MODEL={args.model} and ENABLE_EMBEDDINGS=true")


if __name__ == "__main__":
    main()
