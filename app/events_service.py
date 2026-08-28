from fastapi import FastAPI

"""
Event Store: хранит последние онлайн-события пользователя (прослушивания).
Нужен для учёта истории при выдаче online/blended рекомендаций.
"""


class EventStore:
    def __init__(self, max_events_per_user: int = 10) -> None:
        self.events: dict[int, list[int]] = {}
        self.max_events_per_user = max_events_per_user

    def put(self, user_id: int, item_id: int) -> None:
        """
        Добавляет событие в начало списка (самые свежие — первыми).

        Args:
            user_id: идентификатор пользователя
            item_id: идентификатор трека

        Returns:
            None
        """
        user_events = self.events.get(user_id, [])
        self.events[user_id] = [item_id] + user_events[: self.max_events_per_user]


    def get(self, user_id: int, k: int) -> list[int]:
        """
        Возвращает k последних item_id пользователя.

        Args:
            user_id: идентификатор пользователя
            k: количество событий

        Returns:
            list[int]: список идентификаторов треков
        """
        return self.events.get(user_id, [])[:k]


events_store = EventStore(max_events_per_user=10)

app = FastAPI(title="events")


@app.get("/health")
async def health() -> dict:
    """
    Проверка готовности Event Store (для скриптов запуска).
    """
    return {"status": "ok"}


@app.post("/put")
async def put(user_id: int, item_id: int) -> dict:
    """
    Сохраняет онлайн-событие user_id + item_id.

    Args:
        user_id: идентификатор пользователя
        item_id: идентификатор трека

    Returns:
        dict: словарь с результатом
    """
    events_store.put(user_id, item_id)
    return {"result": "ok"}


@app.post("/get")
async def get(user_id: int, k: int = 10) -> dict:
    """
    Возвращает последние k событий пользователя.

    Args:
        user_id: идентификатор пользователя
        k: количество событий
    
    Returns:
        dict: словарь с результатом
    """
    return {"events": events_store.get(user_id, k)}
