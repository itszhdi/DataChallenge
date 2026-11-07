# CQA — бэкенд оценки качества диалогов

FastAPI-сервис для кейса Freedom «Conversation Quality Analytics». Он оценивает работу оператора контакт-центра по настраиваемому чек-листу через LLM (Gemini или локальная модель) и поддерживает апелляции и аналитику.

## Главный принцип: модель отвечает, код считает

- Модель только отвечает на вопросы чек-листа: `na`, `value`, `explanation`, `evidence_ids`, `checked_range`, `flags`.
- В БД хранятся **ответы**, а не баллы. Баллы, перераспределение N/A, секции и итог каждый раз заново считает `score_evaluation()` (`src/features/evaluation/scoring.py`, Decimal + ROUND_HALF_UP).
- Смена **веса** → новая версия чек-листа и пересчёт **без вызова модели**.
- Изменение **формулировки / шкалы / N/A / пояснения** или **новый** критерий → модель переоценивает **только эти критерии**, остальные ответы копируются.
- Решение по **апелляции** → пересчёт без модели. В карточке видны исходная (`original`) и финальная (`final`) оценка.

## Установка и запуск

```bash
cd backend
make install                 # uv sync
cp .env.example .env         # вписать DATASET_API_URL и LLM_API_KEY
make run                     # http://localhost:8000/api/health
make import-dev              # импорт DEV из API организаторов
make eval ID=p1-ru-001       # оценить один диалог
make batch DATASET=DEV       # пакетная оценка в фоне → job id
make job JOB=<id>            # прогресс
make test                    # тесты
make docker-up               # то же в Docker (SQLite в volume)
```

Swagger отключён намеренно. Запуск фронтенда описан в корневом `README.md`.

## .env

| Переменная | Назначение |
|---|---|
| `DATASET_API_URL` | Ссылка организаторов **без** `&group_id`. Бэкенд сам дописывает его строкой, чтобы не потерять подпись `sig` |
| `LLM_PROVIDER` | `gemini` или `openai` (LM Studio и любой OpenAI-совместимый сервер) |
| `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | Доступ к модели |
| `LLM_REASONING_EFFORT` | `low` для Gemini; пусто для моделей без reasoning |
| `LLM_MIN_INTERVAL_SEC` | Минимальная пауза между запросами (7 для бесплатного Gemini) |
| `LLM_CONCURRENCY`, `LLM_RETRIES` | Параллелизм и повторы при битом JSON или ошибке сети. При 429 отдельно: паузы 15/30/45… с, до 5 раз |
| `EXCLUDE_CHANNELS` | `["voice call"]`: реальные звонки не отправляются в бесплатный API (Google использует такие запросы для обучения) |
| `CQA_TARGET_SCORE` | Целевой индекс качества на дашборде, по умолчанию 85 |
| `LLM_PRICES` | `{"model": [$in, $out]}` за 1M токенов, чтобы посчитать стоимость одной оценки (токены пишутся в `meta` и в лог) |

Примеры для Gemini и LM Studio есть в `.env.example`.

## API (префикс `/api`)

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | Провайдер и модель |
| GET | `/datasets` | Загруженные наборы |
| POST | `/datasets/import` `{"group_id":"DEV"}` или `{"url":"https://..."}` | Импорт из API организаторов (по group_id или по полной ссылке) |
| POST | `/datasets/upload?dataset=` (multipart `file`) | Импорт из JSON-файла того же формата |
| GET | `/conversations?dataset=` | Список: язык, канал, последняя оценка, итог, грубые ошибки, открытые апелляции |
| GET | `/conversations/{id}` | Диалог (`index`, `offset_sec` у реплик) и история оценок |
| GET | `/checklists`, `/checklists/active`, `/checklists/{id}` | Версии чек-листа |
| POST | `/checklists` `{"data":{...},"comment":""}` | Новая активная версия + `diff` с предыдущей |
| PATCH | `/checklists/active/weights` `{"weights":{"c01_contact":30},"reapply_all":true}` | Новые веса + пересчёт без модели |
| POST | `/checklists/{id}/activate` | Сделать версию активной |
| POST | `/evaluate` `{"conversation_id":"..."}` | Оценить диалог, вернуть карточку |
| POST | `/evaluate/batch` `{"dataset":"DEV","conversation_ids":null,"mode":"evaluate"\|"reapply","only_missing":false}` | Пакетная обработка в фоне |
| GET | `/jobs/{id}` | Прогресс: `total`, `processed`, `done`, `failed`, `skipped` |
| GET | `/evaluations/{id}` | Карточка: `original`, `final`, `meta`, `appeals`, `conversation` |
| POST | `/evaluations/{id}/reapply` | Применить активный чек-лист (LLM только для изменённых критериев) |
| POST | `/evaluations/{id}/appeals` `{"criterion_id","comment"}` | Подать апелляцию |
| GET | `/appeals?status=open` | Очередь проверяющего: спорный критерий + фрагмент ±2 реплики |
| POST | `/appeals/{id}/resolve` `{"decision":"upheld"\|"changed","reason","value","na"}` | Решение → `original_total`, `final_total` |
| GET | `/analytics?dataset=` | Средний итог, разбивка по языкам/каналам/критериям, грубые ошибки, 5 худших |
| GET | `/analytics/dashboard?dataset=` | Сводка для супервайзера: KPI, критерии, сегменты, распределение итогов и строки диалогов для drill-down |
| GET | `/prompt/{conversation_id}` | Промпт и JSON-схема без вызова модели (отладка) |
| GET | `/export?dataset=&team_name=&model_mode=&model_name=` | JSON с финальными оценками (с учётом апелляций) |
| GET | `/audio/{conversation_id}` | Прокси записи звонка: достаёт mp3 со страницы организаторов, поддерживает Range (перемотка) |

### Сценарий защиты: заменить критерий
1. `GET /checklists/active` → изменить `rule`/`scale` критерия или добавить новый → `POST /checklists`. В ответе `diff.needs_llm` показывает, какие критерии уйдут в модель.
2. `POST /evaluate/batch {"dataset":"DEV","mode":"reapply"}`. Модель вызывается только по изменённым критериям.

### Контрольный набор организаторов
`POST /datasets/import {"group_id":"<новый>"}`, затем `POST /evaluate/batch {"dataset":"<новый>"}`.

## Формат критерия

```json
{"id": "c04_consult", "section": "safety", "title": "Корректная и полная консультация",
 "type": "binary | scale | flag", "weight": 20, "na_allowed": true,
 "na_condition": "Чат закончился до того, как клиент сформулировал запрос.",
 "rule": "...", "scale": [{"value": 20, "description": "..."}],
 "guidance": "пояснение для модели", "examples_pass": [], "examples_fail": [], "flag_types": []}
```

- `binary`: «Да» даёт полный вес, «Нет» — 0.
- `scale`: баллы = вес × ступень / верхняя ступень. Значение не из шкалы приводится к ближайшей ступени.
- `flag`: баллов не даёт, попадает в `gross_errors`.
- N/A исключает критерий, его вес перераспределяется на остальные, максимум всегда 100. Если применимых критериев нет, итог `null`.

Начальный чек-лист: `checklists/default_checklist.json`. Он записывается в БД при первом запуске.

## Структура

```
src/
  main.py, router.py, dependencies.py, db.py (весь SQL), config/settings.py
  llm/client.py                       # Gemini / OpenAI-совместимый, троттлинг, 429, токены
  features/
    datasets/       импорт API/файла
    conversations/  список и карточка диалога
    checklists/     версии, валидация, diff по отпечатку критерия
    evaluation/     timing, prompt, scoring, service (оценка, валидация, reapply), jobs
    appeals/        подача, очередь, решение
    analytics/      сводка и дашборд супервайзера
    audio/          прокси записей звонков
    export/         выгрузка результатов в JSON
```
