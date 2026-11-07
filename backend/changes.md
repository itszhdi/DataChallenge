# Изменения API для фронтенда

Этот файл — задание для отдельной доработки `frontend/`. Каждый блок можно отдать Claude Code целиком: «Внедри во frontend изменения из backend/changes.md, раздел N».

## 1. Внутренний id диалога = `НАБОР:исходный_id`

**Что изменилось в бэкенде**
- `GET /api/conversations`: поле `id` теперь имеет вид `DEV:p1-ru-001`. Новые поля: `source_id` (исходный id организаторов) и `seq` (порядок записи в наборе). Список отсортирован по `dataset, seq`.
- Все эндпоинты с `{conversation_id}` (`/conversations/{id}`, `/audio/{id}`, `/prompt/{id}`, `POST /evaluate`) принимают внутренний id. Исходный id тоже работает, если он встречается только в одном наборе.
- `GET /api/export`: `conversation_id` — исходный id, плюс новое поле `dataset`.
- `POST /api/datasets/import|upload`: в ответе новое поле `warnings` (вложения, неизвестные роли, пустые реплики, реплики без времени, пустые транскрипты, повторы id в файле).
- `POST /api/evaluate` возвращает **422**, если диалог нельзя оценить (пустой транскрипт или нет реплик оператора). В пакетной оценке такие диалоги попадают в `skipped`.
- В транскрипте могут встретиться: `speaker: "unknown"` вместе с `speaker_raw`, флаг `empty: true`, массив `attachments` (в `text` уже добавлен маркер `[вложение: …]`).

**Что сделать во фронте**
- Показывать пользователю `source_id`, а в запросах использовать `id`. Подставлять `id` в URL через `encodeURIComponent` (в нём есть `:`).
- После импорта показывать `warnings` (свернуть, если их больше 5).
- Обрабатывать 422 у «Оценить» как понятное сообщение, а не как ошибку бэкенда.
- В транскрипте отображать роль `unknown` как «неизвестная роль (speaker_raw)», пустые реплики — серым «(пусто)».

## 2. Пересчёт, порог и апелляции

**Что изменилось в бэкенде**
- В критерии появилось необязательное поле `uses_timing: bool`: критерий опирается на факты о времени (по умолчанию так только у `c06_flow`).
- Результат diff (`POST /api/checklists` → `diff`) получил поле `threshold_changed: bool`. Если порог `settings.first_response_threshold_sec` изменился, критерии с `uses_timing` попадают в `changed`/`needs_llm`.
- Изменение `title` критерия теперь считается изменением формулировки (`changed`, переспрашивается модель), а не `weight_only`.
- Апелляции переносятся на новую оценку при `reapply` и при повторном `POST /evaluate`:
  - открытые переезжают;
  - решённые копируются, если критерий не менялся;
  - если критерий менялся, создаётся новая **открытая** апелляция, к комментарию добавлена пометка «[Критерий изменён после решения … — пересмотрите апелляцию]».
- Ответ `POST /evaluations/{id}/reapply` → `reapply.appeals = {moved, copied, reopened}`.
- При повторной оценке `meta.previous_evaluation_id` указывает на предыдущую оценку. `parent_id` по-прежнему ставится только при переносе (reapply).

**Что сделать во фронте**
- В редакторе чек-листа: чекбокс «Использует время (порог первой реакции)» → `uses_timing`, поле «Порог первой реакции, сек» → `settings.first_response_threshold_sec`.
- В панели diff показывать «Порог изменён — переоценка: …», если `threshold_changed`.
- После reapply показать тост, если `reopened > 0`: «N апелляций переоткрыто — критерий изменён».
- В истории оценок можно подписывать «повторная оценка», если есть `meta.previous_evaluation_id`.

## 3. Настройки, выбор модели, статусы анализа, ETA, Retry

**Новые эндпоинты**
- `GET /api/settings` → `{auto_mode, auto_sort, auto_dataset, llm_profile, profiles: {gemini: {provider, model, active}, local: {provider, model, base_url, active}}}`.
- `PATCH /api/settings`: любое подмножество полей:
  - `auto_mode: bool` — ручной или автоматический режим;
  - `auto_sort: "date_asc" | "date_desc" | "size_asc" | "size_desc"` — дата импорта или число реплик;
  - `auto_dataset: string | null` — null означает все наборы;
  - `llm_profile: "gemini" | "local"` — применяется сразу, без рестарта.
  Неверное значение → 422.
- `GET /api/settings/models` — проверка профилей: `{gemini: {model, available, ...}, local: {model, available, model_loaded, models[], error?}}`. Нужна для подсказки «LM Studio не запущен» или «модель не загружена».
- `GET /api/queue?dataset=` → `{model: {profile, name, avg_eval_sec, workers}, running: [...], queued: [...], upcoming: [...], failed: [...], counts: {...}, eta_total_sec}`:
  - в каждом элементе есть `conversation_id`, `source_id`, `dataset`, `source` (`manual|batch|auto`), `error`, `attempts`, `eta_sec`;
  - в `running` дополнительно есть `elapsed_sec`, в `queued`/`upcoming` — `position`;
  - `upcoming` — следующие диалоги авто-воркера (появятся в разделе 4).
- `GET /api/jobs?active=true` — задачи пакетной оценки (последние 20 или только активные). Нужен для восстановления прогресса после F5.
- `POST /api/evaluate/batch` принимает `only_failed: true` — повтор только упавших (кнопка Retry). Диалоги, уже стоящие в очереди или в работе, повторно не ставятся.
- `GET /api/health` → `{status, profile, provider, model}`.

**Новые поля в `GET /api/conversations`**
- `status`: `null | queued | running | done | failed | skipped`.
- `status_source`, `status_error`, `status_attempts`, `status_queued_at`, `status_started_at`, `status_finished_at`.
- `eta_sec`: примерное время до конца для `queued`/`running`.
- После рестарта сервера диалоги, которые были `queued`/`running`, получают `failed` с ошибкой «сервер перезапущен во время анализа».
- Одиночный `POST /api/evaluate` тоже пишет статус (`source: manual`).

**Что сделать во фронте**
- Экран «Настройки»:
  - переключатель «Ручной / Автоматический» (`auto_mode`);
  - сортировка (4 варианта, активна только в авторежиме);
  - выбор набора (`auto_dataset`);
  - выбор модели Gemini/Локальная (`llm_profile`) рядом с результатом `GET /settings/models` (зелёный — доступна, красный — текст `error`).
- Список диалогов: в каждой строке бейдж статуса (в очереди №N / анализируется · ~Xс / ошибка / пропущен) и иконка ошибки с `status_error` во всплывающей подсказке. У `failed` кнопка «Повторить» → `POST /api/evaluate {conversation_id}`.
- Общий статус-бар над списком при `counts.running + counts.queued + counts.upcoming > 0`: «Анализ: X в работе, Y в очереди, ~Z мин (модель …)». При `counts.failed > 0` кнопка «Повторить упавшие (N)» → `POST /evaluate/batch {only_failed: true}`.
- Опрос `GET /api/queue` и `GET /api/conversations` каждые 2–3 с, пока есть running/queued или включён авторежим, иначе раз в 15–30 с.
- При загрузке страницы: `GET /api/jobs?active=true` → если есть задача, показать её прогресс (вместо хранения `R.job` в памяти).
- Если у ручного «Оценить» статус ответа ≠ 200, сразу показать ошибку в строке диалога (бэкенд уже записал `failed`).

## 4. Авто-воркер

**Что изменилось в бэкенде**
- Фоновый воркер живёт всё время работы сервера. При `auto_mode: true` он по одному берёт **неоценённые** диалоги без статуса:
  - фильтр `auto_dataset`;
  - сортировка `auto_sort`;
  - каналы из `EXCLUDE_CHANNELS` пропускаются.
- Упавшие (`failed`) и пропущенные (`skipped`) диалоги воркер **не повторяет**, нужен ручной Retry. Устаревшие оценки (после смены чек-листа) тоже не трогает, их переоценивают вручную.
- Пока идёт ручная пакетная оценка, воркер стоит на паузе.
- `GET /api/worker` → `{alive, mode: manual|auto, status: idle|running|paused|error, reason, current, processed, failed, last_tick, last_error}`.
- `GET /api/queue` дополнительно содержит:
  - `worker` (то же, что и выше, плюс `auto_mode`, `auto_sort`, `auto_dataset`);
  - `upcoming` — очередь воркера в порядке обработки, с `position` и `eta_sec`.
- `eta_sec` в `GET /api/conversations` заполняется и для диалогов из `upcoming`.

**Что сделать во фронте**
- В статус-баре показывать состояние воркера:
  - «Автопроверка: анализирует SOURCE_ID»;
  - «на паузе — идёт пакетная оценка»;
  - «нет новых диалогов»;
  - «ручной режим»;
  - при `status=error` — `last_error` красным.
- Диалоги из `upcoming` помечать «в автоочереди №N · ~X мин».
- Когда пользователь меняет сортировку, сразу перезапрашивать `/api/queue`: порядок `upcoming` пересчитывается.
