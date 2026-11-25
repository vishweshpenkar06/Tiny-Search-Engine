from typing import Any

from flask import jsonify, g


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _request_id() -> str | None:
    return getattr(g, "request_id", None)


def api_success(data: dict[str, Any], status_code: int = 200):
    body = dict(data)
    request_id = _request_id()
    if request_id:
        body.setdefault("request_id", request_id)
    response = jsonify(body)
    response.status_code = status_code
    return response


def api_error(message: str, status_code: int = 400, code: str = "bad_request"):
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    request_id = _request_id()
    if request_id:
        body["request_id"] = request_id
    response = jsonify(body)
    response.status_code = status_code
    return response


def error_response(error: ApiError):
    return api_error(error.message, error.status_code, error.code)
