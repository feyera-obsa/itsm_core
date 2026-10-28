# -*- coding: utf-8 -*-
# Copyright (c) 2026 and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


# Constants for Standard Change validation
STANDARD_BLOCKED_TIERS = {"Critical"}  # Highest tier in Service Registry
STANDARD_BLOCKED_CATEGORIES = {"Data"}  # Standard changes cannot be Data category


class ChangeRequest(Document):
    """Change Request DocType controller for ERPNext v16."""

    def before_validate(self):
        if self.change_type == "Emergency":
            user = frappe.session.user
            roles = frappe.get_roles(user)
            if "Change Manager" not in roles and "CI Integration" not in roles:
                frappe.throw(
                    _("Only a break-glass role (Change Manager / CI Integration) "
                      "may authorize an Emergency change."),
                    frappe.PermissionError,
                )
            # Only set on first save (new doc)
            if self.is_new():
                self.emergency_authorized_by = user
                from frappe.utils import now, add_to_date
                self.retro_review_due = add_to_date(now(), hours=24)
        else:
            self.emergency_authorized_by = None
            self.retro_review_due = None

    def validate(self):
        self._compute_risk_score()
        self._derive_risk_level()
        self._lock_fields_after_approval()
        self._validate_mandatory_fields_by_change_type()
        self._validate_standard_change()

    def _validate_mandatory_fields_by_change_type(self):
        """Enforce mandatory fields per change type."""
        # rollback_plan is required for ALL change types (reqd=1 in JSON)
        if not self.rollback_plan:
            frappe.throw(
                _("Rollback Plan is required for all change types."),
                frappe.MandatoryError,
            )

        if self.change_type in ("Normal", "Emergency"):
            missing = []
            if not self.impact:
                missing.append("Impact")
            if not self.likelihood:
                missing.append("Likelihood")
            # validation_criteria only mandatory for Normal
            if self.change_type == "Normal" and not self.validation_criteria:
                missing.append("Validation Criteria")
            if missing:
                frappe.throw(
                    _("The following fields are required for {0} changes: {1}").format(
                        self.change_type, ", ".join(missing)
                    ),
                    frappe.MandatoryError,
                )

    def _validate_standard_change(self):
        """Validate Standard change requirements (lean path, no template)."""
        if self.change_type != "Standard":
            return

        # Block if any affected service has the highest tier (Critical)
        for row in self.affected_services or []:
            svc = frappe.get_doc("Service Registry", row.service)
            if svc.tier in STANDARD_BLOCKED_TIERS:
                frappe.throw(
                    _("Standard changes may not affect {0} tier services. "
                      "Service {1} is tier {2}.").format(
                        ", ".join(STANDARD_BLOCKED_TIERS), row.service, svc.tier
                    ),
                    frappe.MandatoryError,
                )

        # Block Data category for Standard changes
        if self.change_category in STANDARD_BLOCKED_CATEGORIES:
            frappe.throw(
                _("Standard changes may not have category '{0}'.").format(self.change_category),
                frappe.MandatoryError,
            )

        # Set risk_level to Low for Standard (since impact/likelihood are hidden/empty)
        self.risk_level = "Low"

    def on_submit(self):
        """Called when document is submitted."""
        if self.workflow_state == "Approved for Deployment" and not self.approved_by:
            self.db_set("approved_by", frappe.session.user, update_modified=False)

    def on_cancel(self):
        """Called when document is cancelled."""
        if self.approved_by:
            self.db_set("approved_by", None, update_modified=False)
        if self.emergency_authorized_by:
            self.db_set("emergency_authorized_by", None, update_modified=False)
        if self.retro_review_due:
            self.db_set("retro_review_due", None, update_modified=False)

    def on_trash(self):
        """Called when document is deleted - clean up child table."""
        pass

    def _compute_risk_score(self):
        impact_map = {"1 - Low": 1, "2 - Medium": 2, "3 - High": 3, "4 - Critical": 4}
        likelihood_map = {
            "1 - Rare": 1, "2 - Unlikely": 2, "3 - Possible": 3,
            "4 - Likely": 4, "5 - Certain": 5,
        }
        impact = impact_map.get(self.impact, 0)
        likelihood = likelihood_map.get(self.likelihood, 0)
        self.computed_risk_score = impact * likelihood

    def _derive_risk_level(self):
        score = self.computed_risk_score or 0
        if self.change_type == "Standard":
            # Standard changes have impact/likelihood hidden -> risk_level = Low
            self.risk_level = "Low"
            return
        if score >= 12:
            self.risk_level = "Critical"
        elif score >= 8:
            self.risk_level = "High"
        elif score >= 4:
            self.risk_level = "Medium"
        else:
            self.risk_level = "Low"

    def _lock_fields_after_approval(self):
        """
        Lock content fields after the Change Request reaches an approved/closed state.

        DECISION: Keep custom field locking instead of relying on Frappe's native submit locking.
        REASON: The workflow maps ALL states to doc_status=0 (Draft). No state transitions
        to doc_status=1 (Submitted), so Frappe's native submit locking (which only triggers
        at docstatus=1) is NEVER activated. The custom locking is the ONLY protection
        against post-approval content changes.

        The child table comparison uses stable identifiers (service + name) rather than
        full row dict comparison, because child rows may not have stable names before
        the parent is saved. We compare by (service, name) tuple which provides
        deterministic ordering.
        """
        if self.is_new():
            return
        old = self.get_doc_before_save()
        if not old:
            return
        if old.workflow_state in (
            "Approved for Deployment", "Implemented", "Closed", "Rejected"
        ):
            locked_simple = [
                "title", "justification", "implementation_steps",
                "rollback_plan", "validation_criteria", "repo",
                "scheduled_start", "scheduled_end", "scheduled_window",
            ]
            for field in locked_simple:
                if self.get(field) != old.get(field):
                    frappe.throw(
                        _("Field {0} is locked after approval").format(field)
                    )

            # Compare child tables by stable signature (service + name)
            def get_child_signature(row):
                # row can be a Document object or dict
                if hasattr(row, 'as_dict'):
                    row = row.as_dict()
                return (
                    row.get("service") or "",
                    row.get("name") or "",
                )

            old_children = sorted(
                [get_child_signature(c) for c in (old.affected_services or [])],
            )
            new_children = sorted(
                [get_child_signature(c) for c in (self.affected_services or [])],
            )
            if old_children != new_children:
                frappe.throw(
                    _("Affected Services is locked after approval")
                )

    def on_update(self):
        if self.workflow_state == "Approved for Deployment" and not self.approved_by:
            self.db_set("approved_by", frappe.session.user, update_modified=False)