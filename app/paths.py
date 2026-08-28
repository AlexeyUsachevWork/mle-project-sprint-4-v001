"""Пути к артефактам офлайн-этапа относительно корня репозитория."""
from pathlib import Path

# Корень репозитория: app/ -> на уровень выше
ROOT = Path(__file__).resolve().parent.parent

RECS_DIR = ROOT / "recsys" / "recommendations"

PERSONAL_RECS_PATH = RECS_DIR / "recommendations.parquet"
TOP_POPULAR_PATH = RECS_DIR / "top_popular.parquet"
SIMILAR_ITEMS_PATH = RECS_DIR / "similar.parquet"


def check_artifacts() -> list[str]:
    """
    Возвращает список отсутствующих файлов (пустой список — всё на месте).

    Returns:
        list[str]: список отсутствующих файлов
    """
    missing = []
    for path in (PERSONAL_RECS_PATH, TOP_POPULAR_PATH, SIMILAR_ITEMS_PATH):
        if not path.exists():
            missing.append(str(path))
    return missing
