"""
API Metrics Collector
Collects and stores API performance metrics
"""

import time
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional
import statistics


class MetricsCollector:
    """Collect and analyze API performance metrics"""

    def __init__(self):
        self.metrics = defaultdict(list)
        self.errors = []
        self.max_history_hours = 24

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        error: str = None
    ):
        """Record API request metrics"""
        metric = {
            "timestamp": datetime.utcnow(),
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "error": error
        }

        self.metrics[endpoint].append(metric)

        # Record errors
        if error or status_code >= 400:
            self.errors.append({
                "timestamp": datetime.utcnow(),
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "error": error
            })

        # Cleanup old data
        self._cleanup_old_metrics()

    def get_endpoint_stats(self, endpoint: str, hours: int = 24) -> Optional[dict]:
        """Get statistics for specific endpoint"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [m for m in self.metrics.get(endpoint, []) if m['timestamp'] > cutoff]

        if not recent:
            return None

        durations = [m['duration_ms'] for m in recent]
        errors = [m for m in recent if m['status_code'] >= 400]

        return {
            "endpoint": endpoint,
            "requests": len(recent),
            "avg_duration_ms": statistics.mean(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "p50_duration_ms": self._percentile(durations, 50),
            "p95_duration_ms": self._percentile(durations, 95),
            "p99_duration_ms": self._percentile(durations, 99),
            "error_count": len(errors),
            "error_rate": (len(errors) / len(recent) * 100) if recent else 0
        }

    def get_all_stats(self, hours: int = 24) -> dict:
        """Get overall API statistics"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        all_requests = []
        all_durations = []
        total_errors = 0

        for endpoint_metrics in self.metrics.values():
            recent = [m for m in endpoint_metrics if m['timestamp'] > cutoff]
            all_requests.extend(recent)
            all_durations.extend([m['duration_ms'] for m in recent])
            total_errors += len([m for m in recent if m['status_code'] >= 400])

        if not all_requests:
            return {
                "requests_24h": 0,
                "avg_response_time_ms": 0,
                "p95_response_time_ms": 0,
                "p99_response_time_ms": 0,
                "errors_24h": 0,
                "error_rate_percent": 0
            }

        return {
            "requests_24h": len(all_requests),
            "avg_response_time_ms": statistics.mean(all_durations),
            "p95_response_time_ms": self._percentile(all_durations, 95),
            "p99_response_time_ms": self._percentile(all_durations, 99),
            "errors_24h": total_errors,
            "error_rate_percent": (total_errors / len(all_requests) * 100) if all_requests else 0
        }

    def get_slowest_endpoints(self, limit: int = 10, hours: int = 24) -> list:
        """Get slowest API endpoints"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        endpoint_stats = []
        for endpoint in self.metrics.keys():
            stats = self.get_endpoint_stats(endpoint, hours)
            if stats and stats['requests'] > 0:
                endpoint_stats.append({
                    "endpoint": endpoint,
                    "avg_ms": stats['avg_duration_ms'],
                    "requests": stats['requests']
                })

        # Sort by average duration (slowest first)
        endpoint_stats.sort(key=lambda x: x['avg_ms'], reverse=True)
        return endpoint_stats[:limit]

    def get_recent_errors(self, hours: int = 24, limit: int = 100) -> list:
        """Get recent errors"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_errors = [e for e in self.errors if e['timestamp'] > cutoff]
        recent_errors.sort(key=lambda x: x['timestamp'], reverse=True)
        return recent_errors[:limit]

    def _percentile(self, data: list, percentile: int) -> float:
        """Calculate percentile"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

    def _cleanup_old_metrics(self):
        """Remove metrics older than max_history_hours"""
        cutoff = datetime.utcnow() - timedelta(hours=self.max_history_hours)

        # Cleanup endpoint metrics
        for endpoint in list(self.metrics.keys()):
            self.metrics[endpoint] = [
                m for m in self.metrics[endpoint] if m['timestamp'] > cutoff
            ]
            if not self.metrics[endpoint]:
                del self.metrics[endpoint]

        # Cleanup errors
        self.errors = [e for e in self.errors if e['timestamp'] > cutoff]


# Global metrics collector instance
metrics_collector = MetricsCollector()


def metrics_middleware():
    """FastAPI middleware to collect metrics"""

    async def middleware(request, call_next):
        start_time = time.time()

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            metrics_collector.record_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms
            )

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            metrics_collector.record_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=500,
                duration_ms=duration_ms,
                error=str(e)
            )
            raise

    return middleware
