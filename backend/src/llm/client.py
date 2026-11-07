# * Единый клиент LLM: Gemini (OpenAI-совместимый endpoint) или любой OpenAI-совместимый сервер (LM Studio)
import asyncio
import copy
import json
import logging
import time
from typing import Any

import openai
from openai import AsyncOpenAI

from src.config.settings import LLMProfile, Settings

logger = logging.getLogger(__name__)

RATE_LIMIT_ATTEMPTS = 5
RATE_LIMIT_BASE_PAUSE_SEC = 15


class LLMError(Exception):
    # * code — машинная причина сбоя: по ней интерфейс показывает понятное сообщение
    def __init__(self, message: str, code: str = "llm_rejected") -> None:
        super().__init__(message)
        self.code = code


def network_error_code(error: Exception) -> str:
    if isinstance(error, openai.APITimeoutError):
        return "llm_timeout"
    return "llm_server_error" if isinstance(error, openai.InternalServerError) else "llm_unavailable"


def status_error_code(error: openai.APIStatusError) -> str:
    if error.status_code in (401, 403):
        return "llm_auth"
    if error.status_code == 404 or "no models loaded" in str(error).lower():
        return "llm_model_not_found"
    return "llm_rejected"


def _error_text(e: openai.APIStatusError) -> str:
    # * У 429 str(e) — только код; причина (квота RPM/RPD, модель) лежит в теле ответа
    body = e.body
    if isinstance(body, list) and body:
        body = body[0]
    if isinstance(body, dict):
        err = body.get("error", body)
        body = err.get("message", err) if isinstance(err, dict) else err
    return str(body or e)[:400]


def is_daily_quota(e: openai.APIStatusError) -> bool:
    # ! Дневной лимит (free tier: ~20 запросов/день на модель) паузами не лечится
    raw = json.dumps(e.body, ensure_ascii=False, default=str)
    lower = _error_text(e).lower()
    return "PerDay" in raw or ("RESOURCE_EXHAUSTED" in raw and ("per day" in lower or "daily" in lower))


def gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    # ** Gemini понимает подмножество JSON Schema: убираем additionalProperties, числовые enum -> description
    schema = copy.deepcopy(schema)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("additionalProperties", None)
            enum = node.get("enum")
            if enum and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in enum):
                del node["enum"]
                node["description"] = "Одно из значений: " + ", ".join(str(v) for v in enum)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema


def extract_json(text: str) -> dict[str, Any]:
    # ** Qwen может писать рассуждения в <think>: в них бывают фигурные скобки, поэтому блок отбрасываем
    _, closed, answer = text.rpartition("</think>")
    text = answer if closed else text
    # * Ответ может прийти в ```json-обёртке: берём первый {...}
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in response")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise ValueError("JSON root is not an object")
    return obj


class LLMClient:
    def __init__(self, profile: LLMProfile, prices: dict[str, list[float]] | None = None) -> None:
        self.profile = profile
        self.prices = prices or {}
        self.provider = profile.provider
        self.model = profile.model
        # * Запасной клиент (LLM_FALLBACK_*): включается при исчерпании квоты основного
        self.fallback: LLMClient | None = None
        # ** Встроенные ретраи SDK выключены — повторы и паузы контролируем сами
        self.client = AsyncOpenAI(
            api_key=profile.api_key or "not-set", base_url=profile.base_url, timeout=profile.timeout_sec, max_retries=0,
        )
        self.concurrency = max(1, profile.concurrency)
        self.min_interval_sec = profile.min_interval_sec
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._throttle_lock = asyncio.Lock()
        self._last_call = 0.0

    def configure(self, concurrency: int, min_interval_sec: float) -> None:
        # ** Лимиты из настроек UI; пауза не опускается ниже профиля, иначе бесплатный Gemini уйдёт в 429
        self.concurrency = max(1, concurrency)
        self.min_interval_sec = max(self.profile.min_interval_sec, min_interval_sec)
        # * Идущие вызовы дорабатывают со старым семафором, новые берут новый лимит
        self._semaphore = asyncio.Semaphore(self.concurrency)
        logger.info("LLM limits for %s: concurrency=%d min_interval_sec=%.2f", self.profile.name, self.concurrency, self.min_interval_sec)

    async def close(self) -> None:
        await self.client.close()

    def model_for_channel(self, channel: str | None) -> str:
        # * Отдельные модели для чатов и звонков (LLM_CHAT_MODEL / LLM_CALL_MODEL), иначе модель профиля
        normalized = (channel or "").strip().lower()
        if ("call" in normalized or "звон" in normalized) and self.profile.call_model:
            return self.profile.call_model
        if "chat" in normalized and self.profile.chat_model:
            return self.profile.chat_model
        return self.model

    def cost_usd(self, prompt_tokens: int, completion_tokens: int, model: str | None = None) -> float:
        price_in, price_out = (self.prices.get(model or self.model) or [0.0, 0.0])[:2]
        return round((prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000, 6)

    async def _throttle(self) -> None:
        # * Глобальный минимальный интервал между запросами (бесплатный Gemini ~10 запросов/мин)
        async with self._throttle_lock:
            wait = self._last_call + self.min_interval_sec - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()

    def _request_kwargs(self, messages: list[dict[str, Any]], schema: dict[str, Any], model: str) -> dict[str, Any]:
        send_schema = gemini_schema(schema) if self.provider == "gemini" else schema
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_schema", "json_schema": {"name": "evaluation", "strict": True, "schema": send_schema}},
        }
        if self.profile.reasoning_effort:
            kwargs["reasoning_effort"] = self.profile.reasoning_effort
        if self.profile.max_tokens:
            kwargs["max_tokens"] = self.profile.max_tokens
        return kwargs

    async def complete_json(
        self, messages: list[dict[str, Any]], schema: dict[str, Any], channel: str | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if self.provider == "gemini" and not self.profile.api_key:
            raise LLMError("LLM_API_KEY не задан в .env", "llm_auth")
        if not self.model:
            raise LLMError(f"Модель для профиля {self.profile.name} не задана в .env", "llm_model_not_found")

        model = self.model_for_channel(channel)
        kwargs = self._request_kwargs(messages, schema, model)
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        attempts, rate_limited, last_error, last_code, fallback_reason = 0, 0, "", "llm_bad_answer", ""
        started = time.monotonic()

        async with self._semaphore:
            while attempts <= self.profile.retries:
                attempts += 1
                await self._throttle()
                try:
                    resp = await self.client.chat.completions.create(**kwargs)
                except openai.RateLimitError as e:
                    if is_daily_quota(e):
                        logger.error("LLM daily quota exhausted for model %s: %s", model, _error_text(e))
                        if self.fallback:
                            fallback_reason = "daily quota exhausted"
                            break
                        raise LLMError(f"Дневная квота модели {model} исчерпана: {_error_text(e)[:200]}", "llm_quota") from e
                    # ! 429 не тратит обычные попытки: ждём 15, 30, 45... с (или retry-after), максимум 5 раз
                    rate_limited += 1
                    attempts -= 1
                    if rate_limited > RATE_LIMIT_ATTEMPTS:
                        last_error, last_code = f"rate limit: {_error_text(e)}", "llm_rate_limited"
                        fallback_reason = "429 retries exhausted" if self.fallback else ""
                        break
                    pause = RATE_LIMIT_BASE_PAUSE_SEC * rate_limited
                    try:
                        pause = max(pause, float(e.response.headers.get("retry-after", "")))
                    except (TypeError, ValueError, AttributeError):
                        pass
                    logger.warning("LLM rate limited (429), model=%s retry %d/%d in %ds: %s",
                                   model, rate_limited, RATE_LIMIT_ATTEMPTS, pause, _error_text(e))
                    await asyncio.sleep(pause)
                    continue
                except openai.APITimeoutError as e:
                    last_error, last_code = f"timeout after {self.profile.timeout_sec:.0f}s", "llm_timeout"
                    logger.warning("LLM timeout on attempt %d (model=%s, %.0fs)", attempts, model, self.profile.timeout_sec)
                    if not self.profile.retry_on_timeout:
                        raise LLMError(f"Модель {model} не ответила за {self.profile.timeout_sec:.0f} с", "llm_timeout") from e
                    continue
                except (openai.APIConnectionError, openai.InternalServerError) as e:
                    last_error, last_code = f"{type(e).__name__}: {e}", network_error_code(e)
                    logger.warning("LLM network/server error on attempt %d: %s", attempts, last_error)
                    continue
                except openai.APIStatusError as e:
                    # ! 400/401/403 повторять бессмысленно
                    logger.error("LLM request rejected: status=%s body=%s", e.status_code, str(e)[:500])
                    raise LLMError(f"LLM отклонил запрос ({e.status_code}): {str(e)[:300]}", status_error_code(e)) from e

                if resp.usage:
                    usage["prompt_tokens"] += resp.usage.prompt_tokens or 0
                    usage["completion_tokens"] += resp.usage.completion_tokens or 0
                    usage["total_tokens"] += resp.usage.total_tokens or 0

                content = resp.choices[0].message.content if resp.choices else None
                if resp.choices and resp.choices[0].finish_reason == "length":
                    # ! Ответ упёрся в max_tokens: при temperature=0 повтор даст то же самое — сразу ошибка
                    logger.error("LLM response truncated by max_tokens=%s (model=%s, tokens_out=%d)",
                                 self.profile.max_tokens or "default", model, usage["completion_tokens"])
                    raise LLMError(f"Ответ модели {model} обрезан по длине ({usage['completion_tokens']} токенов)", "llm_bad_answer")
                try:
                    data = extract_json(content or "")
                except ValueError as e:
                    last_error, last_code = f"bad JSON: {e}", "llm_bad_answer"
                    logger.warning("LLM returned invalid JSON on attempt %d: %s; head=%r", attempts, e, (content or "")[:200])
                    continue

                meta = {
                    "profile": self.profile.name, "provider": self.provider, "model": model, "fallback_used": False,
                    "seconds": round(time.monotonic() - started, 2), "attempts": attempts, "rate_limited": rate_limited,
                    "tokens": usage, "cost_usd": self.cost_usd(usage["prompt_tokens"], usage["completion_tokens"], model),
                }
                logger.info("LLM call ok: model=%s seconds=%.1f attempts=%d tokens_in=%d tokens_out=%d cost_usd=%.6f",
                            model, meta["seconds"], attempts, usage["prompt_tokens"], usage["completion_tokens"], meta["cost_usd"])
                return data, meta

        if fallback_reason:
            logger.warning("LLM %s: %s; switching to fallback model=%s", model, fallback_reason, self.fallback.model)
            data, meta = await self.fallback.complete_json(messages, schema, channel)
            meta.update(fallback_used=True, primary_model=model)
            return data, meta
        logger.error("LLM call failed after %d attempts: %s", attempts, last_error)
        raise LLMError(f"Модель не ответила корректно: {last_error}", last_code)

    async def ping(self) -> dict[str, Any]:
        # * Быстрая проверка доступности: список моделей сервера (для LM Studio — запущен ли и загружена ли модель)
        try:
            models = await self.client.with_options(timeout=5).models.list()
            ids = [m.id for m in models.data]
        except openai.OpenAIError as e:
            return {"available": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
        loaded = self.model in ids or any(i.endswith(self.model) for i in ids) if self.provider != "gemini" else True
        return {"available": True, "model_loaded": loaded, "models": ids[:20] if self.provider != "gemini" else []}


class LLMRegistry:
    # ** Все профили создаются при старте; активный меняется из /api/settings без рестарта
    def __init__(self, settings: Settings, active: str | None = None) -> None:
        self.clients = {name: LLMClient(p, settings.llm_prices) for name, p in settings.llm_profiles().items()}
        fallback = settings.fallback_profile()
        self.fallback = LLMClient(fallback, settings.llm_prices) if fallback else None
        self.clients["gemini"].fallback = self.fallback
        # * Отдельный клиент для распознавания звонков: модель Gemini с поддержкой аудио, не зависит от активного профиля
        self.transcriber = LLMClient(settings.transcribe_profile(), settings.llm_prices)
        self.active_name = active if active in self.clients else settings.default_llm_profile

    def configure(self, concurrency: int, min_interval_sec: float) -> None:
        for c in self.clients.values():
            c.configure(concurrency, min_interval_sec)

    def use(self, name: str) -> None:
        if name not in self.clients:
            raise KeyError(name)
        if name != self.active_name:
            logger.info("LLM profile switched: %s -> %s (model=%s)", self.active_name, name, self.clients[name].model)
        self.active_name = name

    def active(self) -> LLMClient:
        return self.clients[self.active_name]

    async def close(self) -> None:
        for c in [*self.clients.values(), self.transcriber, *([self.fallback] if self.fallback else [])]:
            await c.close()
