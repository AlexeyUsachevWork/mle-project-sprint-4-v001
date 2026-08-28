"""Загрузка артефактов рекомендаций из S3, если их нет локально."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.paths import (
    PERSONAL_RECS_PATH,
    RECS_DIR,
    SIMILAR_ITEMS_PATH,
    TOP_POPULAR_PATH,
    check_artifacts,
)

# Локальный путь -> ключ в S3 (как при upload в recommendations.ipynb)
ARTIFACTS: list[tuple[Path, str]] = [
    (PERSONAL_RECS_PATH, "recsys/recommendations/recommendations.parquet"),
    (TOP_POPULAR_PATH, "recsys/recommendations/top_popular.parquet"),
    (SIMILAR_ITEMS_PATH, "recsys/recommendations/similar.parquet"),
]

ENV_FILE = Path(__file__).resolve().parent.parent / ".env.local"


def load_env_file(path: Path | str = ENV_FILE) -> None:
    """
    Простой парсер KEY=VALUE без зависимости от python-dotenv.

    Args:
        path: путь к файлу .env.local
    """
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _get_s3_client():
    """
    Создаёт boto3-клиент для Yandex Object Storage.

    Returns:
        boto3.client: клиент для работы с S3
    """
    load_env_file()
    required = ("S3_BUCKET_NAME", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
    missing_env = [name for name in required if not os.environ.get(name)]
    if missing_env:
        raise RuntimeError(
            "Для загрузки из S3 заполните .env.local или переменные окружения: "
            + ", ".join(missing_env)
        )

    endpoint = os.environ.get("MLFLOW_S3_ENDPOINT_URL", "https://storage.yandexcloud.net")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )


def download_file(s3_key: str, local_path: Path) -> None:
    """
    Скачивает один файл из S3 во временный файл, затем атомарно переименовывает.

    Args:
        s3_key: ключ объекта в бакете
        local_path: локальный путь назначения
    """
    client = _get_s3_client()
    bucket = os.environ["S3_BUCKET_NAME"]

    local_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = local_path.with_suffix(local_path.suffix + ".tmp")

    print(f"download s3://{bucket}/{s3_key} -> {local_path}")
    try:
        client.download_file(bucket, s3_key, str(tmp_path))
    except ClientError as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            raise FileNotFoundError(
                f"Объект не найден в S3: s3://{bucket}/{s3_key}"
            ) from exc
        raise

    tmp_path.replace(local_path)
    print("ok")


def ensure_artifacts() -> list[str]:
    """
    Проверяет артефакты этапа 3 и скачивает отсутствующие из S3.

    Returns:
        list[str]: пути к скачанным файлам (пустой список — всё уже было локально)
    """
    missing_before = check_artifacts()
    if not missing_before:
        return []

    print(f"missing locally ({len(missing_before)}):", *missing_before, sep="\n  ")

    downloaded: list[str] = []
    for local_path, s3_key in ARTIFACTS:
        if local_path.exists():
            continue
        download_file(s3_key, local_path)
        downloaded.append(str(local_path))

    missing_after = check_artifacts()
    if missing_after:
        raise FileNotFoundError(
            "После загрузки из S3 всё ещё отсутствуют файлы:\n  "
            + "\n  ".join(missing_after)
        )

    return downloaded


def main() -> int:
    try:
        downloaded = ensure_artifacts()
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if downloaded:
        print(f"downloaded {len(downloaded)} file(s)")
    else:
        print("artifacts ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
