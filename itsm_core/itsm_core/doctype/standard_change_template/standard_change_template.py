# -*- coding: utf-8 -*-
# Copyright (c) 2026 and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class StandardChangeTemplate(Document):
    """Standard Change Template DocType controller for ERPNext v16."""

    def validate(self):
        self._validate_allowed_services()

    def _validate_allowed_services(self):
        """Ensure at least one allowed service is defined."""
        if not self.allowed_services:
            frappe.throw(_("At least one allowed service must be specified."), frappe.MandatoryError)

        # Check for duplicates
        services = [row.service for row in self.allowed_services]
        if len(services) != len(set(services)):
            frappe.throw(_("Duplicate services found in allowed services list."), frappe.DuplicateEntryError)


# Standard Change Template Service is a child table, no controller needed