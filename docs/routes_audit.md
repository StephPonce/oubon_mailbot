# API Routes Audit Report
Generated: 2025-12-12T02:39:15.543976

## Summary
- **Total Routes:** 26
- **Files with Routes:** 2

## Routes by File

### ospra_os/api/task_routes.py

| Method | Path | Function | Auth | Validation | Response Model |
|--------|------|----------|------|------------|----------------|
| GET | `/active` | get_active_tasks | ❌ | ❌ | - |
| GET | `/beat-schedule` | get_beat_schedule | ❌ | ❌ | - |
| GET | `/queues` | get_queue_stats | ❌ | ❌ | - |
| POST | `/revoke/{task_id}` | revoke_task | ❌ | ❌ | - |
| GET | `/scheduled` | get_scheduled_tasks | ❌ | ❌ | - |
| GET | `/stats` | get_worker_stats | ❌ | ❌ | - |
| GET | `/status/{task_id}` | get_task_status | ❌ | ❌ | TaskStatusResponse |
| POST | `/trigger/analyze-performance` | trigger_performance_analysis | ❌ | ❌ | - |
| POST | `/trigger/daily-brief` | trigger_daily_brief | ❌ | ❌ | - |
| POST | `/trigger/discover-products` | trigger_product_discovery | ❌ | ❌ | - |
| POST | `/trigger/send-email` | trigger_email_send | ❌ | ❌ | - |
| POST | `/trigger/sync-store` | trigger_store_sync | ❌ | ❌ | - |

### ospra_os/api/template_routes.py

| Method | Path | Function | Auth | Validation | Response Model |
|--------|------|----------|------|------------|----------------|
| POST | `` | create_template | ❌ | ❌ | - |
| GET | `/browse` | browse_templates | ❌ | ❌ | - |
| GET | `/categories/list` | list_categories | ❌ | ❌ | - |
| GET | `/featured` | get_featured_templates | ❌ | ❌ | - |
| POST | `/from-actions` | create_template_from_actions | ❌ | ✅ | - |
| GET | `/my-templates` | get_my_templates | ❌ | ❌ | - |
| GET | `/purchased` | get_purchased_templates | ❌ | ❌ | - |
| GET | `/stats/overview` | get_marketplace_stats | ❌ | ❌ | - |
| GET | `/{template_id}` | get_template | ❌ | ❌ | - |
| PATCH | `/{template_id}` | update_template | ❌ | ❌ | - |
| POST | `/{template_id}/purchase` | purchase_template | ❌ | ✅ | - |
| POST | `/{template_id}/review` | add_review | ❌ | ✅ | - |
| POST | `/{template_id}/submit` | submit_for_review | ❌ | ❌ | - |
| POST | `/{template_id}/use` | use_template | ❌ | ✅ | - |

## Potential Issues

### Routes Without Authentication (non-GET)

- POST `` in ospra_os/api/template_routes.py- POST `/from-actions` in ospra_os/api/template_routes.py- PATCH `/{template_id}` in ospra_os/api/template_routes.py- POST `/{template_id}/submit` in ospra_os/api/template_routes.py- POST `/{template_id}/use` in ospra_os/api/template_routes.py- POST `/{template_id}/purchase` in ospra_os/api/template_routes.py- POST `/{template_id}/review` in ospra_os/api/template_routes.py- POST `/revoke/{task_id}` in ospra_os/api/task_routes.py- POST `/trigger/discover-products` in ospra_os/api/task_routes.py- POST `/trigger/sync-store` in ospra_os/api/task_routes.py- POST `/trigger/send-email` in ospra_os/api/task_routes.py- POST `/trigger/analyze-performance` in ospra_os/api/task_routes.py- POST `/trigger/daily-brief` in ospra_os/api/task_routes.py

### Routes Without Response Model

- GET `/featured` in ospra_os/api/template_routes.py- GET `/browse` in ospra_os/api/template_routes.py- GET `/my-templates` in ospra_os/api/template_routes.py- GET `/purchased` in ospra_os/api/template_routes.py- GET `/{template_id}` in ospra_os/api/template_routes.py- POST `` in ospra_os/api/template_routes.py- POST `/from-actions` in ospra_os/api/template_routes.py- POST `/{template_id}/submit` in ospra_os/api/template_routes.py- POST `/{template_id}/use` in ospra_os/api/template_routes.py- POST `/{template_id}/purchase` in ospra_os/api/template_routes.py- POST `/{template_id}/review` in ospra_os/api/template_routes.py- GET `/categories/list` in ospra_os/api/template_routes.py- GET `/stats/overview` in ospra_os/api/template_routes.py- GET `/active` in ospra_os/api/task_routes.py- GET `/scheduled` in ospra_os/api/task_routes.py- POST `/revoke/{task_id}` in ospra_os/api/task_routes.py- GET `/stats` in ospra_os/api/task_routes.py- GET `/queues` in ospra_os/api/task_routes.py- GET `/beat-schedule` in ospra_os/api/task_routes.py- POST `/trigger/discover-products` in ospra_os/api/task_routes.py
... and 4 more

### Duplicate Routes

✅ No duplicate routes found!

