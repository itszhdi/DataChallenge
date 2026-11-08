from fastapi import HTTPException, status

# * Оба конфликта приходят с 409: фронт различает их по машинному коду в заголовке
ERROR_CODE_HEADER = "X-Error-Code"


class ConversationNotFound(HTTPException):
    code = "conversation_not_found"

    def __init__(self, conversation_id: str) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, f"Диалог {conversation_id} не найден")


class EvaluationNotFound(HTTPException):
    def __init__(self, evaluation_id: int) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, f"Оценка {evaluation_id} не найдена")


class NoActiveChecklist(HTTPException):
    code = "no_checklist"

    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "Нет активного чек-листа", headers={ERROR_CODE_HEADER: self.code})


class ChannelExcluded(HTTPException):
    code = "channel_excluded"

    def __init__(self, channel: str) -> None:
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            f"Канал «{channel}» исключён из отправки в модель (EXCLUDE_CHANNELS): реальные звонки не передаются в бесплатный API",
        )


class NotEvaluable(HTTPException):
    code = "not_evaluable"

    def __init__(self, reason: str) -> None:
        super().__init__(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Диалог нельзя оценить: {reason}")


class LLMUnavailable(HTTPException):
    def __init__(self, detail: str, code: str) -> None:
        super().__init__(status.HTTP_502_BAD_GATEWAY, detail)
        self.code = code


class JobAlreadyRunning(HTTPException):
    code = "job_running"

    def __init__(self) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT, "Оценка уже идёт, дождитесь её окончания", headers={ERROR_CODE_HEADER: self.code}
        )


class JobNotFound(HTTPException):
    def __init__(self, job_id: str) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, f"Задача {job_id} не найдена")


class JobNotActive(HTTPException):
    code = "job_not_active"

    def __init__(self, job_id: str, action: str) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT, f"Задачу {job_id} нельзя {action}: она уже завершена или в другом состоянии",
            headers={ERROR_CODE_HEADER: self.code},
        )
