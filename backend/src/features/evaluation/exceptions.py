from fastapi import HTTPException, status


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
        super().__init__(status.HTTP_409_CONFLICT, "Нет активного чек-листа")


class ChannelExcluded(HTTPException):
    code = "channel_excluded"

    def __init__(self, channel: str) -> None:
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            f"Канал «{channel}» исключён из отправки в модель (EXCLUDE_CHANNELS): реальные звонки не передаются в бесплатный API",
        )


class LLMUnavailable(HTTPException):
    def __init__(self, detail: str, code: str) -> None:
        super().__init__(status.HTTP_502_BAD_GATEWAY, detail)
        self.code = code


class JobAlreadyRunning(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "Оценка уже идёт, дождитесь её окончания")


class JobNotFound(HTTPException):
    def __init__(self, job_id: str) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, f"Задача {job_id} не найдена")
