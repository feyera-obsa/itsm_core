# -*- coding: utf-8 -*-
# Copyright (c) 2026 and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class ServiceRegistry(Document):
    def validate(self):
        if not self.service_name:
            frappe.throw("Service Name is required")
