# Подготовка виртуальной машины

## Склонируйте репозиторий

Склонируйте репозиторий проекта:

```
git clone https://github.com/yandex-praktikum/mle-project-sprint-4-v001.git
```

## Активируйте виртуальное окружение

Используйте то же самое виртуальное окружение, что и созданное для работы с уроками. Если его не существует, то его следует создать.

Создать новое виртуальное окружение можно командой:

```
python3 -m venv env_recsys_start
```

После его инициализации следующей командой

```
. env_recsys_start/bin/activate
```

установите в него необходимые Python-пакеты следующей командой

```
pip install -r requirements.txt
```

### Скачайте файлы с данными

Для начала работы понадобится три файла с данными:
- [tracks.parquet](https://storage.yandexcloud.net/mle-data/ym/tracks.parquet)
- [catalog_names.parquet](https://storage.yandexcloud.net/mle-data/ym/catalog_names.parquet)
- [interactions.parquet](https://storage.yandexcloud.net/mle-data/ym/interactions.parquet)
 
Скачайте их в директорию локального репозитория. Для удобства вы можете воспользоваться командой wget:

```
wget https://storage.yandexcloud.net/mle-data/ym/tracks.parquet

wget https://storage.yandexcloud.net/mle-data/ym/catalog_names.parquet

wget https://storage.yandexcloud.net/mle-data/ym/interactions.parquet
```

## Запустите Jupyter Lab

Запустите Jupyter Lab в командной строке

```
jupyter lab --ip=0.0.0.0 --no-browser
```

# Расчёт рекомендаций

Код для выполнения офлайн-части проекта находится в файле `recommendations.ipynb`.

После этапа 3 в каталоге `recsys/recommendations/` должны быть файлы:
- `top_popular.parquet`
- `personal_als.parquet`
- `similar.parquet`
- `recommendations.parquet`

И в `recsys/data/`:
- `items.parquet`
- `events.parquet`

Если файлов нет локально, скачайте их из персонального S3-бакета (пути те же, что в ноутбуке).

# Сервис рекомендаций (этап 4)

Код микросервисов находится в каталоге `app/`:

| Файл | Порт | Назначение |
|------|------|------------|
| `app/events_service.py` | 8020 |  |
| `app/features_service.py` | 8010 | Feature Store (`similar.parquet`) |
| `app/recommendations_service.py` | 8000 | Офлайн/онлайн/blended рекомендации |

Точки входа в корне репозитория (для совместимости с заданием):
- `recommendations_service.py`
- `test_service.py`

## Стратегия смешивания online и offline

1. **Offline** (`/recommendations_offline`): персональные рекомендации из `recommendations.parquet`; если пользователя нет — `top_popular.parquet`.
2. **Online** (`/recommendations_online`): берём последние 3 события из Event Store, для каждого запрашиваем похожие треки в Feature Store, сортируем по `score`, удаляем дубликаты.
3. **Blended** (`/recommendations`): чередуем online и offline (`online[0], offline[0], online[1], offline[1], ...`), добавляем хвосты более длинного списка, снова dedup, обрезаем до `k`.

Так свежая онлайн-история попадает в выдачу раньше, а офлайн-профиль дополняет список.

## Запуск сервисов

Активируйте venv и установите зависимости (см. выше). Запускайте команды **из корня репозитория**.

### Вариант 1 — скрипт (рекомендуется)

Сервисы стартуют **последовательно** (сначала Feature Store, затем Recommendation Store), чтобы не перегружать RAM при загрузке parquet. Первый запуск может занять несколько минут; скрипт ждёт `/health` на каждом порту (до 10 минут).

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_services.ps1
```

Linux/macOS:

```bash
bash scripts/start_services.sh
```

Остановка:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop_services.ps1
```

```bash
bash scripts/stop_services.sh
```

### Вариант 2 — вручную (3 терминала)

```bash
uvicorn app.events_service:app --host 127.0.0.1 --port 8020
uvicorn app.features_service:app --host 127.0.0.1 --port 8010
uvicorn app.recommendations_service:app --host 127.0.0.1 --port 8000
```

# Тестирование сервиса

Скрипт тестов: `app/test_service.py` (обёртка в корне: `test_service.py`).

Три сценария:
1. пользователь без персональных рекомендаций (`user_id=999999999`);
2. пользователь с персональными рекомендациями, без онлайн-истории (`user_id=4`);
3. тот же пользователь после записи онлайн-событий через Event Store.

Запуск (сервисы должны быть подняты):

```bash
python test_service.py > test_service.log
```

Проверка лога:

```bash
type test_service.log    # Windows
cat test_service.log     # Linux
```

Документация API после запуска:
- http://127.0.0.1:8000/docs
- http://127.0.0.1:8010/docs
- http://127.0.0.1:8020/docs
