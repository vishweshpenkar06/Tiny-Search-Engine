from dataclasses import dataclass
import os
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


@dataclass(frozen=True)
class Config:
    debug: bool
    host: str
    port: int
    data_dir: Path
    upload_dir: Path
    db_path: Path
    model_dir: Path
    max_content_length: int
    max_file_size: int
    max_files: int
    max_query_length: int
    admin_username: str | None
    admin_password_hash: str | None
    public_origin: str | None
    rate_limit_per_minute: int
    embeddings_enabled: bool
    crawler_enabled: bool
    crawler_allowed_domains: tuple[str, ...]
    bm25_k1: float
    bm25_b: float
    rrf_k: int

    @property
    def auth_enabled(self) -> bool:
        return bool(self.admin_username and self.admin_password_hash)


def load_config() -> Config:
    data_dir = Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parent / "data"))).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = Path(os.getenv("UPLOAD_DIR", str(data_dir / "uploads"))).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    db_path = Path(os.getenv("INDEX_PATH", str(data_dir / "index.db"))).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    model_dir = Path(os.getenv("MODEL_DIR", str(data_dir / "models"))).resolve()
    model_dir.mkdir(parents=True, exist_ok=True)
    domains = tuple(
        item.strip().lower()
        for item in os.getenv("CRAWLER_ALLOWED_DOMAINS", "").split(",")
        if item.strip()
    )
    return Config(
        debug=_env_bool("DEBUG", False),
        host=os.getenv("HOST", "127.0.0.1"),
        port=_env_int("PORT", 5000),
        data_dir=data_dir,
        upload_dir=upload_dir,
        db_path=db_path,
        model_dir=model_dir,
        max_content_length=_env_int("MAX_CONTENT_LENGTH", 50 * 1024 * 1024),
        max_file_size=_env_int("MAX_FILE_SIZE", 10 * 1024 * 1024),
        max_files=_env_int("MAX_FILES", 100),
        max_query_length=_env_int("MAX_QUERY_LENGTH", 500),
        admin_username=os.getenv("ADMIN_USERNAME") or None,
        admin_password_hash=os.getenv("ADMIN_PASSWORD_HASH") or None,
        public_origin=os.getenv("PUBLIC_ORIGIN") or None,
        rate_limit_per_minute=_env_int("RATE_LIMIT_RPM", 120),
        embeddings_enabled=_env_bool("ENABLE_EMBEDDINGS", False),
        crawler_enabled=_env_bool("ENABLE_CRAWLER", False),
        crawler_allowed_domains=domains,
        bm25_k1=_env_float("BM25_K1", 1.2),
        bm25_b=_env_float("BM25_B", 0.75),
        rrf_k=_env_int("RRF_K", 60),
    )
