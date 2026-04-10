# src/api/middleware.py
"""Flask middleware — CORS, error handling, request logging."""

import time
import traceback
from flask import request, jsonify


def register_middleware(app):
    """Register all middleware on the Flask app."""

    @app.before_request
    def log_request():
        request._start_time = time.time()
        print(f"[REQ] {request.method} {request.path}")

    @app.after_request
    def add_headers(response):
        elapsed = time.time() - getattr(request, "_start_time", time.time())
        response.headers["X-Response-Time"] = f"{elapsed:.3f}s"
        print(f"[RES] {request.method} {request.path} -> {response.status_code} ({elapsed:.3f}s)")
        return response

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": str(e), "status": 400}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found", "status": 404}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large", "status": 413}), 413

    @app.errorhandler(500)
    def internal_error(e):
        traceback.print_exc()
        return jsonify({"error": "Internal server error", "status": 500}), 500
