import logging

import pandas as pd

logger = logging.getLogger("uvicorn.error")


class Recommendations:
    """Хранилище офлайн-рекомендаций: персональные и дефолтные (top popular)."""

    def __init__(self) -> None:
        """
        Инициализирует хранилище офлайн-рекомендаций.
        """
        self._recs: dict[str, pd.DataFrame | None] = {"personal": None, "default": None}
        self._stats = {
            "request_personal_count": 0,
            "request_default_count": 0,
        }


    def load(self, rec_type: str, path: str, **kwargs) -> None:
        """
        Загружает parquet: personal (по user_id) или default (top popular).
        
        Args:
            rec_type: тип рекомендаций: personal (по user_id) или default (top popular)
            path: путь к файлу с рекомендациями
            kwargs: дополнительные параметры для чтения файла

        Returns:
            None
        """
        logger.info("Loading recommendations, type: %s, path: %s", rec_type, path)
        df = pd.read_parquet(path, **kwargs)
        if rec_type == "personal":
            # Индекс по user_id ускоряет выдачу персональных рекомендаций
            self._recs[rec_type] = df.set_index("user_id")
        else:
            self._recs[rec_type] = df
        logger.info("Loaded %s: %s rows", rec_type, len(df))


    def get(self, user_id: int, k: int = 100) -> list[int]:
        """
        Возвращает top-k item_id для пользователя.
        Если персональных нет — отдаёт дефолтный top popular (cold start).

        Args:
            user_id: идентификатор пользователя
            k: количество рекомендаций

        Returns:
            list[int]: список идентификаторов рекомендуемых треков
        """
        try:
            recs = self._recs["personal"].loc[user_id]
            if isinstance(recs, pd.Series):
                recs = recs.to_frame().T
            # rank задаёт порядок после CatBoost-ранжирования на этапе 3
            recs = recs.sort_values("rank")
            items = recs["item_id"].astype(int).tolist()[:k]
            self._stats["request_personal_count"] += 1
            return items
        except KeyError:
            default = self._recs["default"]
            items = default["item_id"].astype(int).tolist()[:k]
            self._stats["request_default_count"] += 1
            return items
        except Exception:
            logger.exception("Failed to get recommendations for user_id=%s", user_id)
            return []

    def stats(self) -> None:
        logger.info("Recommendation store stats:")
        for name, value in self._stats.items():
            logger.info("%s: %s", name, value)
