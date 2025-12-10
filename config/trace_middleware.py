"""
Request timing middleware for performance monitoring.
Logs detailed timing information for each request to help identify slow endpoints.
"""

import logging
import time

logger = logging.getLogger(__name__)


class RequestTimingMiddleware:
    """
    Middleware to log detailed timing information for each request.
    Helps identify slow endpoints and bottlenecks.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Start timing
        start_time = time.time()
        start_cpu = time.process_time()

        # Process request
        response = self.get_response(request)

        # Calculate timing
        duration = time.time() - start_time
        cpu_time = time.process_time() - start_cpu

        # Log detailed timing information
        logger.info(
            f"Request timing: {request.method} {request.path}",
            extra={
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_seconds": round(duration, 3),
                "cpu_time_seconds": round(cpu_time, 3),
                "query_string": request.META.get("QUERY_STRING", ""),
            },
        )

        # Add timing header to response (useful for debugging)
        response["X-Request-Duration"] = f"{duration:.3f}"

        return response
