# -*- coding: utf-8 -*-
# Copyright (c) 2026 and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


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
        """Enforce mandatory fields for Normal and Emergency change types."""
        if self.change_type in ("Normal", "Emergency"):
            missing = []
            if not self.impact:
                missing.append("Impact")
            if not self.likelihood:
                missing.append("Likelihood")
            if not self.rollback_plan:
                missing.append("Rollback Plan")
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
        """Validate Standard change requirements."""
        if self.change_type != "Standard":
            return

        # Standard changes require a template
        if not self.change_template:
            frappe.throw(
                _("Standard changes require a valid Change Template."),
                frappe.MandatoryError,
            )

        template = frappe.get_doc("Standard Change Template", self.change_template)
        if not template.enabled:
            frappe.throw(
                _("Selected Change Template is not enabled."),
                frappe.MandatoryError,
            )

        # All affected services must be in template's allowed_services
        allowed_services = {row.service for row in template.allowed_services}
        for row in self.affected_services or []:
            if row.service not in allowed_services:
                frappe.throw(
                    _("Service {0} is not allowed for this Standard Change Template. "
                      "Allowed services: {1}").format(
                        row.service, ", ".join(sorted(allowed_services))
                    ),
                    frappe.MandatoryError,
                )

        # Standard may not touch a Critical tier service
        for row in self.affected_services or []:
            svc = frappe.get_doc("Service Registry", row.service)
            if svc.tier == "Critical":
                frappe.throw(
                    _("Standard changes may not affect Critical tier services. "
                      "Service {0} is tier Critical.").format(row.service),
                    frappe.MandatoryError,
                )

        # Set risk_level to Low for Standard
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
                return (
                    row.get("service") or "",
                    row.get("name") or "",
                )

            old_children = sorted(
                [get_child_signature(dict(c)) for c in (old.affected_services or [])],
            )
            new_children = sorted(
                [get_child_signature(dict(c)) for c in (self.affected_services or [])],
            )
            if old_children != new_children:
                frappe.throw(
                    _("Affected Services is locked after approval")
                )

    def on_update(self):
        if self.workflow_state == "Approved for Deployment" and not self.approved_by:
            self.db_set("approved_by", frappe.session.user, update_modified=False)