# * Единый клиент LLM: Gemini (OpenAI-совместимый endpoint) или любой OpenAI-совместимый сервер (LM Studio)
import asyncio
import copy
import json
import logging
import time
from typing import Any

import openai
from openai import AsyncOpenAI

from src.config.settings import Settings

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
    # ** Qwen пишет рассуждения в <think>: в них бывают фигурные скобки, поэтому блок отбрасываем
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


def is_daily_quota_error(body_text: str) -> tuple[bool, str]:
    # Gemini's OpenAI-compatible endpoint may wrap error objects in a one-item array.
    try:
        payload = json.loads(body_text)
    except ValueError:
        return False, body_text[:1000]
    if isinstance(payload, list):
        payload = next((item for item in payload if isinstance(item, dict)), {})
    if not isinstance(payload, dict):
        return False, body_text[:1000]
    error = payload.get("error", payload)
    if not isinstance(error, dict):
        return False, body_text[:1000]
    message = str(error.get("message") or body_text[:1000])
    status = str(error.get("status") or "").upper()
    lower = message.lower()
    return status == "RESOURCE_EXHAUSTED" and ("per day" in lower or "daily" in lower), message


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        # ** Встроенные ретраи SDK выключены — повторы и паузы контролируем сами
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key or "not-set",
            base_url=settings.resolved_base_url,
            timeout=settings.llm_timeout_sec,
            max_retries=0,
        )
        self.fallback_client = None
        if settings.llm_fallback_model and settings.llm_fallback_api_key:
            self.fallback_client = AsyncOpenAI(
                api_key=settings.llm_fallback_api_key,
                base_url=settings.resolved_fallback_base_url,
                timeout=settings.llm_timeout_sec,
                max_retries=0,
            )
        self._semaphore = asyncio.Semaphore(max(1, settings.llm_concurrency))
        self._throttle_lock = asyncio.Lock()
        self._last_call = 0.0

    def configure(self, concurrency: int, min_interval_sec: float) -> None:
        # ** Идущие вызовы дорабатывают со старым семафором, новые берут новый лимит
        self.concurrency = concurrency
        self._min_interval_sec = min_interval_sec
        self._semaphore = asyncio.Semaphore(concurrency)
        logger.info("LLM limits updated: concurrency=%d min_interval_sec=%.2f", concurrency, min_interval_sec)

    async def close(self) -> None:
        await self.client.close()
        if self.fallback_client:
            await self.fallback_client.close()

    def model_for_channel(self, channel: str | None) -> str:
        normalized = (channel or "").strip().lower()
        if ("call" in normalized or "звон" in normalized) and self.settings.llm_call_model:
            return self.settings.llm_call_model
        if "chat" in normalized and self.settings.llm_chat_model:
            return self.settings.llm_chat_model
        return self.model

    def cost_usd(self, prompt_tokens: int, completion_tokens: int, model: str | None = None) -> float:
        price_in, price_out = (self.settings.llm_prices.get(model or self.model) or [0.0, 0.0])[:2]
        return round((prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000, 6)

    async def _throttle(self) -> None:
        # * Глобальный минимальный интервал между запросами (бесплатный Gemini ~10 запросов/мин)
        async with self._throttle_lock:
            wait = self._last_call + self._min_interval_sec - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()

    def _request_kwargs(
        self, messages: list[dict[str, str]], schema: dict[str, Any], provider: str | None = None, model: str | None = None
    ) -> dict[str, Any]:
        provider = provider or self.provider
        send_schema = gemini_schema(schema) if provider == "gemini" else schema
        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "evaluation", "strict": True, "schema": send_schema},
            },
        }
        if self.settings.llm_reasoning_effort and provider == "gemini":
            kwargs["reasoning_effort"] = self.settings.llm_reasoning_effort
        return kwargs

    async def complete_json(
        self, messages: list[dict[str, str]], schema: dict[str, Any], channel: str | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if self.provider == "gemini" and not self.settings.llm_api_key:
            raise LLMError("LLM_API_KEY не задан в .env", "llm_auth")

        active_client = self.client
        active_provider = self.provider
        active_model = self.model_for_channel(channel)
        kwargs = self._request_kwargs(messages, schema, active_provider, active_model)
        fallback_used = False
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        attempts, rate_limited, last_error, last_code = 0, 0, "", "llm_bad_answer"
        started = time.monotonic()

        async with self._semaphore:
            while attempts <= self.settings.llm_retries:
                attempts += 1
                await self._throttle()
                try:
                    resp = await active_client.chat.completions.create(**kwargs)
                except openai.RateLimitError as e:
                    # ! 429 не тратит обычные попытки: ждём 15, 30, 45... с, максимум 5 раз
                    rate_limited += 1
                    attempts -= 1
                    try:
                        body_text = e.response.text
                    except Exception:
                        body_text = str(getattr(e, "body", "") or e)
                    response_text = body_text[:1000]
                    daily_quota_exhausted, provider_message = is_daily_quota_error(body_text)
                    if daily_quota_exhausted:
                        last_error = f"daily API quota exhausted: {provider_message}"
                        logger.error(
                            "LLM daily quota exhausted (429), provider=%s model=%s body=%s",
                            active_provider, active_model, response_text,
                        )
                        if self.fallback_client and not fallback_used:
                            fallback_used = True
                            active_client = self.fallback_client
                            active_provider = self.settings.llm_fallback_provider
                            active_model = self.settings.llm_fallback_model
                            kwargs = self._request_kwargs(messages, schema, active_provider, active_model)
                            attempts = rate_limited = 0
                            logger.warning("LLM daily quota exhausted; switching immediately to fallback model=%s", active_model)
                            continue
                        raise LLMError(f"LLM исчерпал дневную квоту (429): {provider_message}") from e
                    if rate_limited > RATE_LIMIT_ATTEMPTS:
                        last_error = f"rate limit (429): {response_text}"
                        if self.fallback_client and not fallback_used:
                            fallback_used = True
                            active_client = self.fallback_client
                            active_provider = self.settings.llm_fallback_provider
                            active_model = self.settings.llm_fallback_model
                            kwargs = self._request_kwargs(messages, schema, active_provider, active_model)
                            attempts = rate_limited = 0
                            logger.warning("LLM primary exhausted 429 retries; switching to configured fallback model=%s", active_model)
                            continue
                        logger.error(
                            "LLM 429 retry limit exhausted, provider=%s model=%s body=%s",
                            active_provider, active_model, response_text,
                        )
                        break
                    pause = RATE_LIMIT_BASE_PAUSE_SEC * rate_limited
                    retry_after = None
                    try:
                        retry_after = float(e.response.headers.get("retry-after", ""))
                    except (TypeError, ValueError, AttributeError):
                        pass
                    if retry_after is not None:
                        pause = max(pause, retry_after)
                    logger.warning(
                        "LLM rate limited (429), provider=%s model=%s retry %d/%d in %ds body=%s",
                        active_provider, active_model, rate_limited, RATE_LIMIT_ATTEMPTS, pause, response_text,
                    )
                    await asyncio.sleep(pause)
                    continue
                except (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError) as e:
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
                try:
                    data = extract_json(content or "")
                except ValueError as e:
                    last_error, last_code = f"bad JSON: {e}", "llm_bad_answer"
                    logger.warning("LLM returned invalid JSON on attempt %d: %s; head=%r", attempts, e, (content or "")[:200])
                    continue

                meta = {
                    "provider": active_provider,
                    "model": active_model,
                    "fallback_used": fallback_used,
                    "seconds": round(time.monotonic() - started, 2),
                    "attempts": attempts,
                    "rate_limited": rate_limited,
                    "tokens": usage,
                    "cost_usd": self.cost_usd(usage["prompt_tokens"], usage["completion_tokens"], active_model),
                }
                logger.info(
                    "LLM call ok: model=%s seconds=%.1f attempts=%d tokens_in=%d tokens_out=%d cost_usd=%.6f",
                    active_model, meta["seconds"], attempts, usage["prompt_tokens"], usage["completion_tokens"], meta["cost_usd"],
                )
                return data, meta

        logger.error("LLM call failed after %d attempts: %s", attempts, last_error)
        raise LLMError(f"Модель не ответила корректно: {last_error}", last_code)
