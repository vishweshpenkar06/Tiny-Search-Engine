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

    sentence_transformers = importlib.import_module("sentence_transformers")
    sentence_transformer = sentence_transformers.SentenceTransformer

    target = args.out / args.model.replace("/", "__")
    target.mkdir(parents=True, exist_ok=True)
    model = sentence_transformer(args.model, cache_folder=str(target))
    model.save(str(target))

    checksums = target / "SHA256SUMS"
    lines = [
        f"{sha256_file(path)}  {path.relative_to(target).as_posix()}"
        for path in sorted(target.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"vendored {args.model} to {target}")
    print(f"set EMBEDDING_MODEL={target.name} and ENABLE_EMBEDDINGS=true")


if __name__ == "__main__":
    main()
