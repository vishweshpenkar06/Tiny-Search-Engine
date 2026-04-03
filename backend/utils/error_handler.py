from flask import jsonify

def api_error(message: str, status_code: int = 400):
    """Format an error response consistently."""
    response = jsonify({"error": message})
    response.status_code = status_code
    return response

def api_success(data: dict, status_code: int = 200):
    """Format a success response consistently."""
    response = jsonify(data)
    response.status_code = status_code
    return response
