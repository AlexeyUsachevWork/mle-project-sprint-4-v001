import logging
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI

from app.paths import SIMILAR_ITEMS_PATH

logger = logging.getLogger("uvicorn.error")


class SimilarItems:
    """
    Feature Store: похожие треки (i2i) из similar.parquet этапа 3.
    """

    def __init__(self) -> None:
        self._similar_items: pd.DataFrame | None = None


    def load(self, path: str, **kwargs) -> None:
        """
        Загружает похожие треки из similar.parquet.

        Args:
            path: путь к файлу с похожими треками
            kwargs: дополнительные параметры для чтения файла
        """
        logger.info("Loading similar items from %s", path)
        df = pd.read_parquet(path, **kwargs)
        # item_id_1 — якорный трек; индекс ускоряет .loc[item_id]
        self._similar_items = (
            df.set_index("item_id_1")
            .sort_values("score", ascending=False)
        )
        logger.info("Similar items loaded: %s rows", len(df))


    def get(self, item_id: int, k: int = 10) -> dict:
        """
        Возвращает top-k похожих треков для item_id.

        Args:
            item_id: идентификатор трека
            k: количество похожих треков
        """
        try:
            subset = self._similar_items.loc[item_id].head(k)
            if isinstance(subset, pd.Series):
                subset = subset.to_frame().T
            return subset[["item_id_2", "score"]].to_dict(orient="list")
        except KeyError:
            logger.warning("No similar items for item_id=%s", item_id)
            return {"item_id_2": [], "score": []}


sim_items_store = SimilarItems()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для инициализации сервиса похожих треков.

    Args:
        app: FastAPI-приложение

    Returns:
        Generator: генератор контекста
    """
    # При старте сервиса один раз загружаем i2i-таблицу в память
    sim_items_store.load(
        str(SIMILAR_ITEMS_PATH),
        columns=["item_id_1", "item_id_2", "score"],
    )
    logger.info("Feature store ready")
    yield


app = FastAPI(title="features", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    """
    Готовность Feature Store: endpoint доступен только после загрузки similar.parquet.
    """
    return {"status": "ok"}


@app.post("/similar_items")
async def similar_items(item_id: int, k: int = 10) -> dict:
    """
    Возвращает top-k похожих треков для item_id.

    Args:
        item_id: идентификатор трека
        k: количество похожих треков

    Returns:
        dict: словарь с похожими треками
    """
    return sim_items_store.get(item_id, k)
