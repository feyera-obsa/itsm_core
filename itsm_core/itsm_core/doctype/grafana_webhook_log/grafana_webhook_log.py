# -*- coding: utf-8 -*-
# Copyright (c) 2026 and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class GrafanaWebhookLog(Document):
    """Log of received Grafana webhook payloads for replay and debugging."""
    pass
