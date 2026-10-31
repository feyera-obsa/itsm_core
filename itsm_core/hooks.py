# -*- coding: utf-8 -*-
# Copyright (c) 2026 and contributors
# License: MIT. See LICENSE

app_name = "itsm_core"
app_title = "ITSM Core"
app_publisher = "Your Organization"
app_email = "itops@example.com"
app_license = "MIT"
app_description = (
    "Unified ITSM workflow for ERPNext v16: Change Request with approval workflow, "
    "Service Registry, ITSM Settings, Grafana webhook ingestion to HD Ticket, "
    "CI gate methods, and heartbeat. Replaces external middleware."
)
app_version = "1.0.0"

required_apps = ["erpnext"]

app_include_js = []
app_include_css = []

# App icon for desk
app_icon = "flag"
app_logo = "/assets/itsm_core/images/itsm_core.png"

fixtures = [
    {
        "dt": "Role",
        "filters": [
            ["name", "in", [
                "Change Requester", "Change Approver", "Change Implementer",
                "Change Manager", "Grafana Integration", "CI Integration"
            ]]
        ],
    },
    {
        "dt": "HD Ticket Priority",
        "filters": [[ "name", "in", ["Critical", "High", "Medium", "Low"] ]],
    },
    {
        "dt": "HD Ticket Status",
        "filters": [
            ["name", "in", ["Open", "Replied", "Resolved", "Closed", "Auto-Resolved"]]
        ],
    },
    {
        "dt": "HD Service Level Agreement",
        "filters": [["name", "in", ["SLA - Critical", "SLA - High", "SLA - Medium", "SLA - Low"]]],
    },
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", [
                "HD Ticket-alert_instance_key",
                "HD Ticket-grafana_status",
                "HD Ticket-runbook_url",
                "HD Ticket-custom_service",
                "HD Ticket-occurrence_count",
                "HD Ticket-last_seen",
            ]]
        ],
    },
    {
        "dt": "Workflow",
        "filters": [["name", "=", "Change Request Approval"]],
    },
    {
        "dt": "Workflow State",
        "filters": [["name", "in", [
                "Draft", "Pending Approval", "Approved for Deployment", "Implemented",
                "Post-Implementation Review", "Closed", "Rejected", "Cancelled"
            ]]],
    },
    {
        "dt": "Workflow Action Master",
        "filters": [["name", "in", [
                "Submit for Approval", "Approve", "Reject / Request Changes",
                "Reopen", "Emergency Approve", "Mark Implemented",
                "Close", "Start Review", "Close Review", "Cancel Request"
            ]]],
    },
    {
        "dt": "Dashboard Chart",
        "filters": [["module", "=", "ITSM Core"]],
    },
]

add_to_apps_screen = [
    {
        "name": "itsm_core",
        "logo": "/assets/itsm_core/images/itsm_core.png",
        "title": "IT Operations",
        "route": "/desk/it-operations",
        "sequence_id": 60,
    }
]