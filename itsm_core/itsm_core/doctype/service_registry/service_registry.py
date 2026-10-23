# -*- coding: utf-8 -*-
# Copyright (c) 2026 and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class ServiceRegistry(Document):
    """Service Registry DocType controller for ERPNext v16."""

    def validate(self):
        if not self.service_name:
            frappe.throw(_("Service Name is required"))

        # Ensure service_name is unique
        if frappe.db.exists("Service Registry", {"service_name": self.service_name, "name": ["!=", self.name]}):
            frappe.throw(_("Service with name {0} already exists").format(self.service_name))

    def on_update(self):
        """Update linked tickets if service details change."""
        if self.has_value_changed("runbook_url") or self.has_value_changed("service_owner"):
            frappe.db.sql("""
                UPDATE `tabHD Ticket`
                SET runbook_url = %s, service_owner = %s
                WHERE custom_service = %s
            """, (self.runbook_url, self.service_owner, self.service_name))
            frappe.db.commit()