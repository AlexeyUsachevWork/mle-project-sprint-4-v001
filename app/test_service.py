"""
Тестирование микросервиса рекомендаций.

Три сценария:
1. Пользователь без персональных рекомендаций (cold start).
2. Пользователь с персональными рекомендациями, но без онлайн-истории.
3. Пользователь с персональными рекомендациями и онлайн-историей.

Перед запуском должны быть подняты сервисы:
  events (:8020), features (:8010), recommendations (:8000).
"""

from __future__ import annotations

import sys

import requests

RECOMMENDATIONS_URL = "http://127.0.0.1:8000"
EVENTS_STORE_URL = "http://127.0.0.1:8020"

HEADERS = {"Content-type": "application/json", "Accept": "text/plain"}

# Зафиксированные id для воспроизводимости проверки ревьюером
COLD_USER_ID = 999_999_999
WARM_USER_ID = 4
# item_id из similar.parquet — для генерации осмысленных online-событий
ONLINE_EVENT_ITEM_IDS = [26, 38, 135]


def post_recommendations(endpoint: str, user_id: int, k: int = 10) -> list[int]:
    resp = requests.post(
        f"{RECOMMENDATIONS_URL}{endpoint}",
        headers=HEADERS,
        params={"user_id": user_id, "k": k},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["recs"]


def put_event(user_id: int, item_id: int) -> None:
    resp = requests.post(
        f"{EVENTS_STORE_URL}/put",
        headers=HEADERS,
        params={"user_id": user_id, "item_id": item_id},
        timeout=10,
    )
    resp.raise_for_status()


def print_scenario(title: str, user_id: int, offline: list, online: list, blended: list) -> None:
    print("=" * 72)
    print(title)
    print(f"user_id={user_id}, k=10")
    print(f"offline ({len(offline)}): {offline}")
    print(f"online  ({len(online)}): {online}")
    print(f"blended ({len(blended)}): {blended}")
    print()


def scenario_cold_user() -> None:
    """Нет персональных рекомендаций -> должен сработать top popular (offline)."""
    user_id = COLD_USER_ID
    offline = post_recommendations("/recommendations_offline", user_id)
    online = post_recommendations("/recommendations_online", user_id)
    blended = post_recommendations("/recommendations", user_id)

    print_scenario(
        "Сценарий 1: пользователь БЕЗ персональных рекомендаций",
        user_id,
        offline,
        online,
        blended,
    )


def scenario_warm_without_online_history() -> None:
    """Есть personal offline, но online-история пустая."""
    user_id = WARM_USER_ID
    offline = post_recommendations("/recommendations_offline", user_id)
    online = post_recommendations("/recommendations_online", user_id)
    blended = post_recommendations("/recommendations", user_id)

    print_scenario(
        "Сценарий 2: персональные рекомендации, БЕЗ онлайн-истории",
        user_id,
        offline,
        online,
        blended,
    )


def scenario_warm_with_online_history() -> None:
    """Есть personal offline + онлайн-события -> online/blended меняются."""
    user_id = WARM_USER_ID

    # Записываем онлайн-события после сценария 2: история учитывается в online/blended
    for item_id in ONLINE_EVENT_ITEM_IDS:
        put_event(user_id, item_id)
        print(f"put event: user_id={user_id}, item_id={item_id}")

    offline = post_recommendations("/recommendations_offline", user_id)
    online = post_recommendations("/recommendations_online", user_id)
    blended = post_recommendations("/recommendations", user_id)

    print_scenario(
        "Сценарий 3: персональные рекомендации + онлайн-история",
        user_id,
        offline,
        online,
        blended,
    )


def main() -> int:
    print("Тестирование recommendation service")
    print(f"recommendations: {RECOMMENDATIONS_URL}")
    print(f"events store:    {EVENTS_STORE_URL}")
    print()

    try:
        scenario_cold_user()
        scenario_warm_without_online_history()
        scenario_warm_with_online_history()
    except requests.RequestException as exc:
        print("ОШИБКА: не удалось вызвать сервис. Проверьте, что все сервисы запущены.")
        print(exc)
        return 1

    print("Все сценарии выполнены успешно.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
