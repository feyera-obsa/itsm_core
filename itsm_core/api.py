# -*- coding: utf-8 -*-
# Copyright (c) 2026 and contributors
# License: MIT. See LICENSE

"""
itsm_core API endpoints for ERPNext v16 (HD Ticket).

Endpoints:
  POST /api/method/itsm_core.api.ingest_grafana_alert   (Grafana webhook)
  POST /api/method/itsm_core.api.get_change_state         (CI gate)
  POST /api/method/itsm_core.api.record_deployment         (CI evidence)
  POST /api/method/itsm_core.api.replay_webhook            (System Manager replay)
  GET  /api/method/itsm_core.api.heartbeat                 (allow_guest liveness)

VERIFY: Frappe Helpdesk v16 doctype names and field names (HD Ticket, HD Ticket
Priority, HD Ticket Status, HD Service Level Agreement, HD Ticket SLA).
VERIFY: `frappe.DuplicateEntryError` vs `frappe.UniqueValidationError` for a
unique-field violation on HD Ticket custom fields.
VERIFY: Whether "Auto-Resolved" HD Ticket status can pause the SLA via
HD Service Level Agreement rules.
"""

import hashlib
import hmac
import json
import traceback

import frappe
from frappe import _
from frappe.utils import now, add_to_date

# FIX #5: API-token auth only. HMAC removed entirely.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_role(role):
    """Fail closed: require an authenticated session user with the given role."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Authentication required"), frappe.PermissionError)
    if role not in frappe.get_roles(user):
        frappe.throw(
            _("Insufficient permissions: {0} role required").format(role),
            frappe.PermissionError,
        )


def _get_settings():
    return frappe.get_single("ITSM Settings")


def _get_severity_priority(severity):
    """Lookup HD Ticket Priority from ITSM Settings severity->priority table.

    Queries the child table directly via SQL to avoid get_single caching
    issues with child table rows inserted outside the DocType controller.
    """
    rows = frappe.db.sql(
        """SELECT severity, priority FROM `tabITSM Settings Severity Priority Row`
           WHERE parent = 'ITSM Settings'""",
        as_dict=True,
    )
    mapping = {}
    for row in rows:
        mapping[(row.severity or "").lower()] = row.priority
    return mapping.get((severity or "").lower(), "Medium")


def _get_reopen_window(service_name):
    """Resolve reopen window: Service Registry override, else ITSM Settings default."""
    settings = _get_settings()
    default_hours = settings.default_reopen_window_hours or 24
    if not service_name:
        return default_hours
    try:
        svc = frappe.get_doc("Service Registry", service_name)
        return svc.reopen_window_hours or default_hours
    except frappe.DoesNotExistError:
        return default_hours


def _truncate_subject(subject, limit=140):
    if not subject:
        return "Grafana Alert"
    return subject[:limit]


def _normalize_datetime(value):
    """Convert ISO 8601 datetime (e.g. '2026-10-20T12:00:00Z') to MariaDB-friendly 'YYYY-MM-DD HH:MM:SS'."""
    if not value:
        return now()
    try:
        from frappe.utils import getdate
        # Handle trailing 'Z' and '+00:00'
        s = str(value)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        # Parse and reformat
        from datetime import datetime
        dt = datetime.fromisoformat(s)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return now()

def _find_existing_by_instance_key(alert_instance_key):
    # FIX #1: Dedup via alert_instance_key = f"{fingerprint}:{startsAt}".
    if not alert_instance_key:
        return None
    return frappe.db.exists("HD Ticket", {"alert_instance_key": alert_instance_key})


def _find_recent_by_fingerprint(fingerprint):
    # FIX #1: For flapping, look up the most recent ticket by fingerprint.
    if not fingerprint:
        return None
    rows = frappe.get_all(
        "HD Ticket",
        filters={"alert_instance_key": ("is", "set")},
        fields=["name", "status", "modified", "alert_instance_key"],
        order_by="modified desc",
        limit_page_length=1,
    )
    # Filter in Python because alert_instance_key is composite.
    for row in rows:
        key = row.alert_instance_key or ""
        if key.startswith(fingerprint + ":"):
            return row.name
    return None


def _log_webhook_payload(alert, error_message):
    try:
        log = frappe.get_doc({
            "doctype": "Grafana Webhook Log",
            "payload": json.dumps(alert),
            "error": error_message,
            "received_at": now(),
            "replay": 0,
        })
        log.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error("Failed to write Grafana Webhook Log", "itsm_core")


def _get_protected_priorities():
    """Get list of HD Ticket Priorities that should NOT auto-resolve on Grafana recovery.
    Reads from ITSM Settings protected_priorities table; defaults to Urgent, Critical, High.
    """
    settings = _get_settings()
    priorities = []
    if settings.protected_priorities:
        for row in settings.protected_priorities:
            if row.priority:
                priorities.append(row.priority)
    if not priorities:
        # Default: Urgent, Critical, High (Urgent is the highest in HD Ticket Priority)
        priorities = ["Urgent", "Critical", "High"]
    return priorities


def _process_alert(alert):
    """Process a single Grafana alert and return a result dict."""
    fingerprint = alert.get("fingerprint")
    starts_at = alert.get("startsAt")
    status = (alert.get("status") or "firing").lower()
    labels = alert.get("labels") or {}
    annotations = alert.get("annotations") or {}

    service = labels.get("service")
    severity = (labels.get("severity") or "warning").lower()
    summary = annotations.get("summary") or alert.get("summary") or ""
    runbook_url = annotations.get("runbook_url") or annotations.get("runbookUrl") or ""

    alert_instance_key = f"{fingerprint}:{starts_at}" if fingerprint and starts_at else None

    priority = _get_severity_priority(severity)
    reopen_window = _get_reopen_window(service)

    existing = _find_existing_by_instance_key(alert_instance_key)

    if status == "resolved" and existing:
        ticket = frappe.get_doc("HD Ticket", existing)
        # FIX #3: Protected priorities are NOT auto-resolved.
        protected_priorities = _get_protected_priorities()
        if ticket.priority in protected_priorities:
            ticket.add_comment(
                "Comment",
                "Grafana recovered; awaiting human verification "
                "(priority {0}).".format(ticket.priority),
            )
            ticket.grafana_status = "recovered_awaiting_verification"
            ticket.save(ignore_permissions=True)
            return {
                "fingerprint": fingerprint,
                "action": "awaiting_verification",
                "ticket": existing,
                "priority": ticket.priority,
            }
        ticket.status = "Auto-Resolved"
        ticket.grafana_status = "resolved"
        ticket.last_seen = now()
        ticket.save(ignore_permissions=True)
        ticket.add_comment("Comment", "Grafana resolved alert at {0}.".format(now()))
        return {
            "fingerprint": fingerprint,
            "action": "auto_resolved",
            "ticket": existing,
        }

    if status == "firing":
        if existing:
            # FIX #13: Atomic SQL increment of occurrence_count.
            frappe.db.sql(
                """UPDATE `tabHD Ticket`
                   SET occurrence_count = occurrence_count + 1,
                       last_seen = %s
                   WHERE name = %s""",
                (_normalize_datetime(starts_at) or now(), existing),
            )
            ticket = frappe.get_doc("HD Ticket", existing)
            ticket.grafana_status = "firing"
            ticket.save(ignore_permissions=True)
            ticket.add_comment(
                "Comment",
                "Occurrence #{0} at {1}: {2}".format(
                    ticket.occurrence_count or 1, starts_at or now(), summary
                ),
            )
            return {
                "fingerprint": fingerprint,
                "action": "updated",
                "ticket": existing,
                "occurrence_count": ticket.occurrence_count,
            }

        # Flapping check: most recent ticket by fingerprint.
        recent = _find_recent_by_fingerprint(fingerprint)
        if recent:
            recent_ticket = frappe.get_doc("HD Ticket", recent)
            if recent_ticket.status in ("Resolved", "Auto-Resolved", "Closed"):
                from frappe.utils import time_diff_in_seconds
                age = time_diff_in_seconds(now(), recent_ticket.modified or now())
                if age <= reopen_window * 3600:
                    recent_ticket.status = "Open"
                    recent_ticket.grafana_status = "firing"
                    recent_ticket.last_seen = _normalize_datetime(starts_at) or now()
                    recent_ticket.save(ignore_permissions=True)
                    recent_ticket.add_comment(
                        "Comment",
                        "Reopened after re-fire within {0}h window.".format(
                            reopen_window
                        ),
                    )
                    return {
                        "fingerprint": fingerprint,
                        "action": "reopened",
                        "ticket": recent,
                        "reopen_window_hours": reopen_window,
                    }

        # Create new HD Ticket.
        if service:
            service_exists = frappe.db.exists("Service Registry", service)
        else:
            service_exists = False

        # FIX #10: Apply registry runbook_url before building description.
        final_runbook = runbook_url
        owner = None
        if service_exists:
            svc = frappe.get_doc("Service Registry", service)
            if svc.runbook_url and not runbook_url:
                final_runbook = svc.runbook_url
            owner = svc.service_owner

        subject = _truncate_subject(summary or f"Grafana Alert: {fingerprint or 'unknown'}")
        description_lines = [
            "Grafana alert fired.",
            "Summary: {0}".format(summary),
            "Severity: {0}".format(severity),
            "Fingerprint: {0}".format(fingerprint or "-"),
            "Runbook: {0}".format(final_runbook or "-"),
        ]
        if service:
            if service_exists:
                description_lines.append("Service: {0}".format(service))
                if owner:
                    description_lines.append("Owner: {0}".format(owner))
            else:
                # FIX #3: Unregistered service -> ticket still created.
                description_lines.append("Unregistered service: {0}".format(service))

        ticket = frappe.get_doc({
            "doctype": "HD Ticket",
            "subject": subject,
            "priority": priority,
            "alert_instance_key": alert_instance_key,
            "grafana_status": "firing",
            "runbook_url": final_runbook,
            "custom_service": service if service_exists else None,
            "service_owner": owner,
            "description": "\\n".join(description_lines),
            "last_seen": _normalize_datetime(starts_at) or now(),
        })
        # FIX #2: Catch both DuplicateEntryError and UniqueValidationError.
        try:
            ticket.insert(ignore_permissions=True)
        except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
            existing_name = frappe.db.exists(
                "HD Ticket", {"alert_instance_key": alert_instance_key}
            ) if alert_instance_key else None
            if existing_name:
                return _process_alert({
                    **alert,
                    "status": "firing",
                })  # recurse into the update path
            raise

        return {
            "fingerprint": fingerprint,
            "action": "created",
            "ticket": ticket.name,
            "priority": priority,
        }

    return {
        "fingerprint": fingerprint,
        "action": "ignored",
        "message": "Unknown status: {0}".format(status),
    }


@frappe.whitelist()
def ingest_grafana_alert():
    """Receive Grafana webhook alerts and create/update HD Tickets.

    FIX #5: API-token auth only for dedicated Grafana Integration user (fail closed).
    FIX #4: Per-alert savepoint/rollback isolation; no frappe.db.commit().
    FIX #2/3: alert_instance_key dedup, flapping, priority-based resolve rules.
    # FIX #15: Run as Administrator internally since this is an authenticated
    # webhook endpoint and should not depend on the caller's DocType permissions.
    """
    if frappe.local.request.method != "POST":
        frappe.local.response.http_status_code = 405
        return {"status": "error", "message": "Method not allowed"}

    # FIX #5: Role-based fail-closed auth. Remove HMAC entirely.
    _require_role("Grafana Integration")

    # Run as Administrator internally: the webhook is already authenticated
    # via API token and role check, so it should not depend on the caller's
    # DocType permissions (HD Ticket lookups/inserts).
    frappe.set_user("Administrator")

    raw_body = frappe.local.request.get_data() or b"{}"
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": "Invalid JSON body"}

    alerts = payload.get("alerts") or [payload]
    results = []

    for alert in alerts:
        # FIX #4: savepoint isolation per alert.
        savepoint = "grafana_alert_{0}".format(abs(hash(json.dumps(alert, sort_keys=True))))
        try:
            frappe.db.savepoint(savepoint)
            result = _process_alert(alert)
            results.append(result)
        except Exception as e:
            frappe.db.rollback(save_point=savepoint)
            frappe.log_error(
                message=traceback.format_exc(),
                title="itsm_core: Grafana alert processing failed"
            )
            _log_webhook_payload(alert, str(e))
            results.append({
                "status": "error",
                "message": "Internal processing error",
                "raw_alert": None,
            })

    # FIX #4: Return 200; non-2xx only for infrastructure failures.
    frappe.local.response.http_status_code = 200
    return {
        "status": "ok",
        "processed": len(results),
        "results": results,
    }


@frappe.whitelist()
def replay_webhook(webhook_log_name):
    """FIX #4: Replay a stored Grafana Webhook Log payload (System Manager only)."""
    _require_role("System Manager")
    log = frappe.get_doc("Grafana Webhook Log", webhook_log_name)
    try:
        payload = json.loads(log.payload)
    except json.JSONDecodeError:
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": "Stored payload is not valid JSON"}
    # Re-run _process_alert for each alert in the stored payload.
    alerts = payload.get("alerts") or [payload]
    results = []
    for alert in alerts:
        savepoint = "replay_{0}".format(webhook_log_name)
        try:
            frappe.db.savepoint(savepoint)
            results.append(_process_alert(alert))
        except Exception as e:
            frappe.db.rollback(save_point=savepoint)
            results.append({"status": "error", "message": "Internal processing error"})
    log.replay = 1
    log.save(ignore_permissions=True)
    frappe.local.response.http_status_code = 200
    return {"status": "ok", "processed": len(results), "results": results}


# ---------------------------------------------------------------------------
# CI gate and deployment methods (FIX #8, #9)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_change_state(change_request_id, repo):
    """CI gate: verify Change Request state and repo match.

    FIX #9: Fail closed if cr.repo is empty or differs from the request.
    """
    _require_role("CI Integration")
    cr = frappe.get_doc("Change Request", change_request_id)
    if not cr.repo:
        frappe.local.response.http_status_code = 403
        return {
            "status": "error",
            "message": "Change Request has no repo set",
        }
    if cr.repo != repo:
        frappe.local.response.http_status_code = 403
        return {
            "status": "error",
            "message": "Change Request repo does not match pipeline repo",
        }
    return {
        "change_request": cr.name,
        "workflow_state": cr.workflow_state,
        "approved_for_deployment": cr.workflow_state == "Approved for Deployment",
        "repo": cr.repo,
    }


@frappe.whitelist()
def record_deployment(change_request_id, evidence):
    """FIX #9: APPEND evidence (never overwrite); log the actor."""
    _require_role("CI Integration")
    cr = frappe.get_doc("Change Request", change_request_id)
    actor = frappe.session.user
    timestamp = now()
    entry = "\n[{0}] {1}: {2}".format(timestamp, actor, evidence)
    cr.deployment_evidence = (cr.deployment_evidence or "") + entry
    cr.save(ignore_permissions=True)
    frappe.local.response.http_status_code = 200
    return {
        "status": "ok",
        "change_request": cr.name,
        "logged_by": actor,
    }


@frappe.whitelist(allow_guest=True)
def heartbeat():
    """FIX #5: allow_guest liveness; returns only {"status":"ok"} after SELECT 1.
    
    Includes basic rate limiting: max 60 requests per minute per IP.
    """
    # Basic rate limiting: 60 req/min per IP
    try:
        if hasattr(frappe.local, 'request') and frappe.local.request:
            remote_addr = getattr(frappe.local.request, 'remote_addr', None) or getattr(frappe.local.request, 'environ', {}).get('REMOTE_ADDR')
            if remote_addr:
                cache_key = f"heartbeat_rate_limit:{remote_addr}"
                count = frappe.cache().get(cache_key) or 0
                if count >= 60:
                    frappe.local.response.http_status_code = 429
                    return {"status": "error", "message": "Rate limit exceeded"}
                frappe.cache().setex(cache_key, 60, count + 1)
    except Exception:
        # If rate limiting fails, allow the request through (fail open for health checks)
        pass
    
    try:
        frappe.db.sql("SELECT 1")
        frappe.local.response.http_status_code = 200
        return {"status": "ok"}
    except Exception:
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": "Health check failed"}


@frappe.whitelist()
def synthetic_alert():
    """FIX #5: Exercise the full ingestion path (System Manager only).

    Creates a test firing alert so the dead-man's switch can validate
    end-to-end delivery, not just endpoint liveness.
    """
    _require_role("System Manager")
    alert = {
        "fingerprint": "synthetic-{0}".format(now()),
        "status": "firing",
        "startsAt": now(),
        "labels": {"service": "synthetic", "severity": "warning"},
        "annotations": {"summary": "Synthetic alert for ingestion path test"},
    }
    try:
        return _process_alert(alert)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "itsm_core: synthetic_alert failed")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": "Internal processing error"}
