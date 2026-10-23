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

    def on_submit(self):
        """Called when document is submitted."""
        if self.workflow_state == "Approved for Deployment" and not self.approved_by:
            self.db_set("approved_by", frappe.session.user, update_modified=False)

    def on_cancel(self):
        """Called when document is cancelled."""
        # Clear approval fields when cancelled
        if self.approved_by:
            self.db_set("approved_by", None, update_modified=False)
        if self.emergency_authorized_by:
            self.db_set("emergency_authorized_by", None, update_modified=False)
        if self.retro_review_due:
            self.db_set("retro_review_due", None, update_modified=False)

    def on_trash(self):
        """Called when document is deleted - clean up child table."""
        # The child table 'affected_services' will be auto-deleted by Frappe
        # since it's a Table field with istable=1. No manual cleanup needed.
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
        if score >= 12:
            self.risk_level = "Critical"
        elif score >= 8:
            self.risk_level = "High"
        elif score >= 4:
            self.risk_level = "Medium"
        else:
            self.risk_level = "Low"

    def _lock_fields_after_approval(self):
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
                "scheduled_window",
            ]
            for field in locked_simple:
                if self.get(field) != old.get(field):
                    frappe.throw(
                        _("Field {0} is locked after approval").format(field)
                    )
            def get_sort_key(row):
                return (row.get("name") or "") + (row.get("service") or "")
            
            old_children = sorted(
                [dict(c) for c in (old.affected_services or [])],
                key=get_sort_key,
            )
            new_children = sorted(
                [dict(c) for c in (self.affected_services or [])],
                key=get_sort_key,
            )
            if old_children != new_children:
                frappe.throw(
                    _("Affected Services is locked after approval")
                )

    def on_update(self):
        if self.workflow_state == "Approved for Deployment" and not self.approved_by:
            self.db_set("approved_by", frappe.session.user, update_modified=False)