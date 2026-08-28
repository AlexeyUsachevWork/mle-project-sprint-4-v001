import logging
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI

from app.paths import PERSONAL_RECS_PATH, TOP_POPULAR_PATH, check_artifacts
from app.recommendations import Recommendations

logger = logging.getLogger("uvicorn.error")

rec_store = Recommendations()

# URL вспомогательных сервисов (Event Store и Feature Store)
EVENTS_STORE_URL = "http://127.0.0.1:8020"
FEATURES_STORE_URL = "http://127.0.0.1:8010"

# Сколько последних онлайн-событий учитывать при построении online-рекомендаций
ONLINE_EVENTS_K = 3

HTTP_HEADERS = {"Content-type": "application/json", "Accept": "text/plain"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для инициализации сервиса рекомендаций.

    Args:
        app: FastAPI-приложение

    Returns:
        Generator: генератор контекста
    """
    missing = check_artifacts()
    if missing:
        raise FileNotFoundError(
            "Не найдены файлы рекомендаций. Сначала выполните этап 3 или "
            f"скачайте parquet в recsys/recommendations/. Отсутствуют: {missing}"
        )

    # Персональные (после ранжирования) и дефолтные (top popular) офлайн-рекомендации
    rec_store.load(
        "personal",
        str(PERSONAL_RECS_PATH),
        columns=["user_id", "item_id", "rank"],
    )
    rec_store.load(
        "default",
        str(TOP_POPULAR_PATH),
        columns=["item_id", "n_listens", "score"],
    )
    logger.info("Recommendation service ready")
    yield


app = FastAPI(title="recommendations", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    """
    Готовность сервиса: parquet загружены в lifespan.
    """
    return {"status": "ok"}


def dedup_ids(ids: list[int]) -> list[int]:
    """
    Убирает дубликаты, сохраняя порядок первого вхождения.

    Args:
        ids: список идентификаторов треков

    Returns:
        list[int]: список идентификаторов треков без дубликатов
    """
    seen: set[int] = set()
    result: list[int] = []
    for item_id in ids:
        if item_id not in seen:
            seen.add(item_id)
            result.append(item_id)
    return result


@app.post("/recommendations_offline")
async def recommendations_offline(user_id: int, k: int = 100) -> dict:
    """
    Офлайн-рекомендации: personal или top popular для cold user.

    Args:
        user_id: идентификатор пользователя
        k: количество рекомендаций

    Returns:
        dict: словарь с рекомендациями
    """
    return {"recs": rec_store.get(user_id=user_id, k=k)}


@app.post("/recommendations_online")
async def recommendations_online(user_id: int, k: int = 100) -> dict:
    """
    Онлайн-рекомендации по последним событиям пользователя:
    Event Store -> похожие треки из Feature Store -> сортировка по score.

    Args:
        user_id: идентификатор пользователя
        k: количество рекомендаций

    Returns:
        dict: словарь с рекомендациями
    """
    params = {"user_id": user_id, "k": ONLINE_EVENTS_K}
    resp = requests.post(
        f"{EVENTS_STORE_URL}/get",
        headers=HTTP_HEADERS,
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    events = resp.json().get("events", [])

    items: list[int] = []
    scores: list[float] = []
    for item_id in events:
        sim_resp = requests.post(
            f"{FEATURES_STORE_URL}/similar_items",
            headers=HTTP_HEADERS,
            params={"item_id": item_id, "k": k},
            timeout=10,
        )
        sim_resp.raise_for_status()
        payload = sim_resp.json()
        items.extend(payload.get("item_id_2", []))
        scores.extend(payload.get("score", []))

    if not items:
        return {"recs": []}

    combined = sorted(zip(items, scores), key=lambda x: x[1], reverse=True)
    ranked_items = [item_id for item_id, _ in combined]
    return {"recs": dedup_ids(ranked_items)[:k]}


@app.post("/recommendations")
async def recommendations(user_id: int, k: int = 100) -> dict:
    """
    Итоговые рекомендации: смешивание online и offline.
    Стратегия описана в README (чередование списков + dedup).

    Args:
        user_id: идентификатор пользователя
        k: количество рекомендаций

    Returns:
        dict: словарь с рекомендациями
    """
    recs_offline = (await recommendations_offline(user_id, k))["recs"]
    recs_online = (await recommendations_online(user_id, k))["recs"]

    blended: list[int] = []
    min_length = min(len(recs_offline), len(recs_online))

    # Чередуем: сначала online (свежая история), затем offline (профиль)
    for i in range(min_length):
        blended.append(recs_online[i])
        blended.append(recs_offline[i])

    blended.extend(recs_online[min_length:])
    blended.extend(recs_offline[min_length:])

    return {"recs": dedup_ids(blended)[:k]}
