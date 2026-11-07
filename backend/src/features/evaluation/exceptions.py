from fastapi import HTTPException, status


class ConversationNotFound(HTTPException):
    def __init__(self, conversation_id: str) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, f"Диалог {conversation_id} не найден")


class EvaluationNotFound(HTTPException):
    def __init__(self, evaluation_id: int) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, f"Оценка {evaluation_id} не найдена")


class NoActiveChecklist(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "Нет активного чек-листа")


class ChannelExcluded(HTTPException):
    def __init__(self, channel: str) -> None:
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            f"Канал «{channel}» исключён из отправки в модель (EXCLUDE_CHANNELS): реальные звонки не передаются в бесплатный API",
        )


class NotEvaluable(HTTPException):
    def __init__(self, reason: str) -> None:
        super().__init__(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Диалог нельзя оценить: {reason}")


class LLMUnavailable(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_502_BAD_GATEWAY, detail)


class JobNotFound(HTTPException):
    def __init__(self, job_id: str) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, f"Задача {job_id} не найдена")
