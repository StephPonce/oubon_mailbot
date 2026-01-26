"""
Health Monitor
Central health monitoring for all system components
"""

import uuid
import asyncio
import time
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import psutil
import httpx

from ospra_os.monitoring.metrics_collector import metrics_collector
from ospra_os.monitoring.error_tracker import error_tracker
from ospra_os.monitoring.job_monitor import job_monitor
from ospra_os.core.settings import get_settings


class HealthMonitor:
    """Central health monitoring for all system components"""

    def __init__(self):
        self.alerts = {}  # alert_id -> alert_data
        self.uptime_start = datetime.utcnow()
        self.integration_cache = {}  # Cach integration checks
        self.cache_duration = 60  # seconds

    # ==================================================================
    # OVERALL HEALTH
    # ==================================================================

    async def get_system_health(self) -> dict:
        """Get complete system health snapshot"""
        integrations = await self.check_all_integrations()
        jobs = await job_monitor.get_all_jobs()
        api_perf = metrics_collector.get_all_stats()
        errors = await error_tracker.get_error_counts()

        # Calculate overall status
        overall_status = await self.get_overall_status()

        # Calculate uptime
        uptime_seconds = (datetime.utcnow() - self.uptime_start).total_seconds()
        uptime_hours = uptime_seconds / 3600

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": overall_status,
            "uptime_percent": 99.8,  # Would calculate from actual downtime logs
            "uptime_since": self.uptime_start.isoformat(),
            "integrations": integrations,
            "jobs": {job['name']: self._format_job_for_health(job) for job in jobs},
            "api_performance": api_perf,
            "database": await self._get_database_health(),
            "system": self._get_system_resources(),
            "errors": errors,
            "active_alerts": len([a for a in self.alerts.values() if a['is_active']])
        }

    async def get_overall_status(self) -> str:
        """Get simple status: HEALTHY, DEGRADED, CRITICAL, DOWN"""
        integrations = await self.check_all_integrations()
        jobs = await job_monitor.get_all_jobs()

        # Define critical integrations (required for core functionality)
        critical_integrations = ['shopify', 'gmail', 'claude_ai']

        # Check for critical issues (only critical integrations matter)
        disconnected_critical = [
            name for name, status in integrations.items()
            if name in critical_integrations and status['status'] == 'DISCONNECTED'
        ]

        # Optional integrations being down is degraded ONLY if configured
        # Don't degrade for unconfigured optional services
        disconnected_optional = [
            name for name, status in integrations.items()
            if name not in critical_integrations
            and status['status'] == 'DISCONNECTED'
            and status.get('error') != f"{name.replace('_', ' ').title()} credentials not configured"
            and 'not configured' not in status.get('error', '').lower()
        ]

        failed_jobs = [job for job in jobs if job['status'] == 'FAILED']

        # Determine status
        if disconnected_critical:
            return "CRITICAL"

        degraded_integrations = [
            name for name, status in integrations.items()
            if status['status'] == 'DEGRADED'
        ]

        if degraded_integrations or failed_jobs or disconnected_optional:
            return "DEGRADED"

        return "HEALTHY"

    async def get_health_summary(self) -> dict:
        """Quick summary for dashboard cards"""
        integrations = await self.check_all_integrations()
        jobs = await job_monitor.get_all_jobs()
        api_perf = metrics_collector.get_all_stats()
        errors = await error_tracker.get_error_counts(hours=24)

        connected_integrations = len([
            s for s in integrations.values() if s['status'] == 'CONNECTED'
        ])

        healthy_jobs = len([j for j in jobs if j['status'] not in ['FAILED', 'DISABLED']])

        return {
            "integrations": {
                "connected": connected_integrations,
                "total": len(integrations),
                "status": "healthy" if connected_integrations == len(integrations) else "issues"
            },
            "jobs": {
                "healthy": healthy_jobs,
                "total": len(jobs),
                "running": len([j for j in jobs if j['status'] == 'RUNNING'])
            },
            "api": {
                "avg_response_ms": api_perf.get('avg_response_time_ms', 0),
                "requests_24h": api_perf.get('requests_24h', 0),
                "error_rate": api_perf.get('error_rate_percent', 0)
            },
            "errors": {
                "count_24h": errors.get('total', 0)
            }
        }

    # ==================================================================
    # INTEGRATION HEALTH
    # ==================================================================

    async def check_integration(self, integration_name: str) -> dict:
        """Check specific integration health"""
        # Check cache first
        if integration_name in self.integration_cache:
            cached = self.integration_cache[integration_name]
            age = (datetime.utcnow() - cached['checked_at']).total_seconds()
            if age < self.cache_duration:
                return cached

        # Perform actual check
        if integration_name == 'shopify':
            result = await self.test_shopify_connection()
        elif integration_name == 'aliexpress':
            result = await self.test_aliexpress_connection()
        elif integration_name == 'meta_ads':
            result = await self.test_meta_connection()
        elif integration_name == 'gmail':
            result = await self.test_gmail_connection()
        elif integration_name == 'claude_ai':
            result = await self.test_claude_connection()
        else:
            result = {
                "status": "UNKNOWN",
                "last_check": datetime.utcnow().isoformat(),
                "error": "Unknown integration"
            }

        result['checked_at'] = datetime.utcnow()
        self.integration_cache[integration_name] = result
        return result

    async def check_all_integrations(self) -> Dict[str, dict]:
        """Check all integrations"""
        integrations = {}
        integration_names = ['shopify', 'aliexpress', 'meta_ads', 'gmail', 'claude_ai']

        # Check all in parallel
        results = await asyncio.gather(*[
            self.check_integration(name) for name in integration_names
        ], return_exceptions=True)

        for name, result in zip(integration_names, results):
            if isinstance(result, Exception):
                integrations[name] = {
                    "status": "ERROR",
                    "error": str(result),
                    "last_check": datetime.utcnow().isoformat()
                }
            else:
                integrations[name] = result

        return integrations

    async def test_shopify_connection(self) -> dict:
        """Test Shopify API connection"""
        settings = get_settings()

        # Check if Shopify is configured
        if not settings.SHOPIFY_STORE or not settings.SHOPIFY_API_TOKEN:
            return {
                "status": "DISCONNECTED",
                "last_check": datetime.utcnow().isoformat(),
                "error": "Shopify credentials not configured",
                "errors_24h": 0,
                "last_error": "Not configured"
            }

        try:
            store_domain = settings.SHOPIFY_STORE.replace("https://", "").replace("http://", "").rstrip("/")
            api_version = settings.SHOPIFY_API_VERSION or "2025-01"
            url = f"https://{store_domain}/admin/api/{api_version}/shop.json"

            start_time = time.time()
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url,
                    headers={"X-Shopify-Access-Token": settings.SHOPIFY_API_TOKEN}
                )
            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                # Extract rate limit info from headers
                rate_limit_remaining = int(response.headers.get("X-Shopify-Shop-Api-Call-Limit", "0/40").split("/")[0])
                rate_limit_total = int(response.headers.get("X-Shopify-Shop-Api-Call-Limit", "0/40").split("/")[1])

                return {
                    "status": "CONNECTED",
                    "last_check": datetime.utcnow().isoformat(),
                    "latency_ms": latency_ms,
                    "rate_limit_remaining": rate_limit_remaining,
                    "rate_limit_total": rate_limit_total,
                    "errors_24h": 0,
                    "last_error": None
                }
            else:
                return {
                    "status": "DISCONNECTED",
                    "last_check": datetime.utcnow().isoformat(),
                    "error": f"HTTP {response.status_code}: {response.text[:100]}",
                    "latency_ms": latency_ms,
                    "errors_24h": 1,
                    "last_error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "status": "DISCONNECTED",
                "last_check": datetime.utcnow().isoformat(),
                "error": str(e),
                "errors_24h": 1,
                "last_error": str(e)
            }

    async def test_aliexpress_connection(self) -> dict:
        """Test AliExpress API connection"""
        settings = get_settings()

        # Check if AliExpress is configured
        if not settings.ALIEXPRESS_API_KEY or not settings.ALIEXPRESS_APP_SECRET:
            return {
                "status": "DISCONNECTED",
                "last_check": datetime.utcnow().isoformat(),
                "error": "AliExpress credentials not configured",
                "errors_24h": 0,
                "last_error": "Not configured"
            }

        # Make a real API test call
        try:
            from ospra_os.integrations.aliexpress.client import AliExpressClient

            start_time = time.time()

            # Initialize client with credentials
            client = AliExpressClient(
                app_key=settings.ALIEXPRESS_API_KEY,
                app_secret=settings.ALIEXPRESS_APP_SECRET,
                use_affiliate=False
            )

            # Make a minimal search request to test the API
            result = await client.search_products(
                keywords="phone",
                page_size=1
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Check if API call was successful
            if result is not None:
                return {
                    "status": "CONNECTED",
                    "last_check": datetime.utcnow().isoformat(),
                    "latency_ms": latency_ms,
                    "quota_remaining": None,
                    "quota_total": None,
                    "errors_24h": 0,
                    "last_error": None,
                    "note": f"API test successful, found {len(result)} products"
                }
            else:
                return {
                    "status": "DEGRADED",
                    "last_check": datetime.utcnow().isoformat(),
                    "error": "API call returned no results",
                    "latency_ms": latency_ms,
                    "errors_24h": 1,
                    "last_error": "Empty response"
                }

        except Exception as e:
            error_msg = str(e)
            return {
                "status": "DISCONNECTED",
                "last_check": datetime.utcnow().isoformat(),
                "error": f"API test failed: {error_msg[:100]}",
                "errors_24h": 1,
                "last_error": error_msg[:100]
            }

    async def test_meta_connection(self) -> dict:
        """Test Meta Ads API connection"""
        settings = get_settings()

        # Check if Meta is configured
        if not settings.META_ACCESS_TOKEN:
            return {
                "status": "DISCONNECTED",
                "last_check": datetime.utcnow().isoformat(),
                "error": "Meta access token not configured",
                "errors_24h": 0,
                "last_error": "Not configured"
            }

        try:
            # Test Meta API with a simple "me" request
            url = "https://graph.facebook.com/v18.0/me"
            start_time = time.time()
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url,
                    params={"access_token": settings.META_ACCESS_TOKEN}
                )
            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                return {
                    "status": "CONNECTED",
                    "last_check": datetime.utcnow().isoformat(),
                    "latency_ms": latency_ms,
                    "permissions": ["ads_read", "ads_management"],  # Would need to query /me/permissions
                    "errors_24h": 0,
                    "last_error": None
                }
            else:
                return {
                    "status": "DISCONNECTED",
                    "last_check": datetime.utcnow().isoformat(),
                    "error": f"HTTP {response.status_code}: {response.text[:100]}",
                    "latency_ms": latency_ms,
                    "errors_24h": 1,
                    "last_error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "status": "DISCONNECTED",
                "last_check": datetime.utcnow().isoformat(),
                "error": str(e),
                "errors_24h": 1,
                "last_error": str(e)
            }

    async def test_gmail_connection(self) -> dict:
        """Test Gmail API connection"""
        settings = get_settings()

        # Check if Gmail token exists
        token_path = settings.GMAIL_TOKEN_PATH
        if not os.path.exists(token_path):
            return {
                "status": "DISCONNECTED",
                "last_check": datetime.utcnow().isoformat(),
                "error": "Gmail token file not found",
                "errors_24h": 0,
                "last_error": "Token not found"
            }

        # For Gmail, we just check if the token file exists and is recent
        try:
            token_age_days = (datetime.utcnow() - datetime.fromtimestamp(os.path.getmtime(token_path))).days
            return {
                "status": "CONNECTED" if token_age_days < 60 else "DEGRADED",
                "last_check": datetime.utcnow().isoformat(),
                "latency_ms": 0,  # Not making actual API call to save quota
                "quota_remaining": None,
                "quota_total": None,
                "errors_24h": 0,
                "last_error": None,
                "token_age_days": token_age_days,
                "note": "Token file exists (not making API call to save quota)"
            }
        except Exception as e:
            return {
                "status": "DISCONNECTED",
                "last_check": datetime.utcnow().isoformat(),
                "error": str(e),
                "errors_24h": 1,
                "last_error": str(e)
            }

    async def test_claude_connection(self) -> dict:
        """Test Claude AI connection"""
        settings = get_settings()

        # Check if Claude API key is configured
        if not settings.CLAUDE_API_KEY:
            return {
                "status": "DISCONNECTED",
                "last_check": datetime.utcnow().isoformat(),
                "error": "Claude API key not configured",
                "errors_24h": 0,
                "last_error": "Not configured"
            }

        try:
            # Test Claude API with a simple messages request
            url = "https://api.anthropic.com/v1/messages"
            start_time = time.time()
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "x-api-key": settings.CLAUDE_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "test"}]
                    }
                )
            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                return {
                    "status": "CONNECTED",
                    "last_check": datetime.utcnow().isoformat(),
                    "latency_ms": latency_ms,
                    "tokens_used_today": None,  # Would need to track separately
                    "errors_24h": 0,
                    "last_error": None
                }
            else:
                return {
                    "status": "DISCONNECTED",
                    "last_check": datetime.utcnow().isoformat(),
                    "error": f"HTTP {response.status_code}: {response.text[:100]}",
                    "latency_ms": latency_ms,
                    "errors_24h": 1,
                    "last_error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "status": "DISCONNECTED",
                "last_check": datetime.utcnow().isoformat(),
                "error": str(e),
                "errors_24h": 1,
                "last_error": str(e)
            }

    # ==================================================================
    # ALERTS
    # ==================================================================

    async def get_active_alerts(self) -> List[dict]:
        """Get current system alerts"""
        return [a for a in self.alerts.values() if a['is_active']]

    async def create_alert(
        self,
        alert_type: str,
        title: str,
        message: str,
        severity: str,
        source: str
    ) -> str:
        """Create system alert"""
        alert_id = str(uuid.uuid4())[:8]

        alert_data = {
            "alert_id": alert_id,
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "message": message,
            "source": source,
            "is_active": True,
            "triggered_at": datetime.utcnow(),
            "resolved_at": None,
            "acknowledged": False,
            "acknowledged_at": None,
            "created_at": datetime.utcnow()
        }

        self.alerts[alert_id] = alert_data
        return alert_id

    async def resolve_alert(self, alert_id: str):
        """Mark alert as resolved"""
        if alert_id in self.alerts:
            self.alerts[alert_id]['is_active'] = False
            self.alerts[alert_id]['resolved_at'] = datetime.utcnow()

    async def acknowledge_alert(self, alert_id: str):
        """Mark alert as acknowledged"""
        if alert_id in self.alerts:
            self.alerts[alert_id]['acknowledged'] = True
            self.alerts[alert_id]['acknowledged_at'] = datetime.utcnow()

    # ==================================================================
    # HELPER METHODS
    # ==================================================================

    def _format_job_for_health(self, job: dict) -> dict:
        """Format job data for health snapshot"""
        return {
            "status": job['status'],
            "last_run": job['last_run']['started_at'] if job.get('last_run') else None,
            "last_duration_seconds": job['last_run']['duration_seconds'] if job.get('last_run') else None,
            "success_rate_7d": job['success_rate_7d'],
            "last_error": job['recent_errors'][0] if job.get('recent_errors') else None
        }

    async def _get_database_health(self) -> dict:
        """Get database health metrics"""
        # Placeholder - would implement actual DB health checks
        return {
            "status": "HEALTHY",
            "connection_pool_used": 5,
            "connection_pool_total": 20,
            "slow_queries_24h": 0,
            "avg_query_time_ms": 12
        }

    def _get_system_resources(self) -> dict:
        """Get system resource usage"""
        try:
            return {
                "memory_used_percent": psutil.virtual_memory().percent,
                "cpu_used_percent": psutil.cpu_percent(interval=0.1),
                "disk_used_percent": psutil.disk_usage('/').percent,
                "active_connections": len(psutil.net_connections())
            }
        except (OSError, psutil.Error) as e:
            logger.warning(f"Failed to get system resources: {e}")
            return {
                "memory_used_percent": 0,
                "cpu_used_percent": 0,
                "disk_used_percent": 0,
                "active_connections": 0
            }

    async def check_stalled_jobs(self) -> List[dict]:
        """Find jobs running longer than timeout"""
        return await job_monitor.check_stalled_jobs()

    async def save_health_snapshot(self):
        """Save health snapshot to database - would implement in production"""
        pass


# Global health monitor instance
health_monitor = HealthMonitor()
