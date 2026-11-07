from fastapi import HTTPException, status


class DatasetSourceNotConfigured(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_500_INTERNAL_SERVER_ERROR, "DATASET_API_URL не задан в .env")


class DatasetFetchError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_502_BAD_GATEWAY, f"Не удалось получить датасет: {detail}")


class InvalidDatasetPayload(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Некорректный формат датасета: {detail}")
