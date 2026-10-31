#!/usr/bin/env python3
"""
Generate professional .docx report for itsm_core IT Operations Module.
Uses python-docx for document generation and Playwright for screenshots.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add bench environment to path
sys.path.insert(0, '/home/feye/frappe-bench')

def install_dependencies():
    """Install required packages if missing."""
    import subprocess
    
    # Install python-docx
    try:
        import docx
    except ImportError:
        print("Installing python-docx...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'python-docx'], check=True)
    
    # Install playwright
    try:
        import playwright
    except ImportError:
        print("Installing playwright...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'playwright'], check=True)
        # Install browsers
        subprocess.run([sys.executable, '-m', 'playwright', 'install', 'chromium'], check=True)

def load_audit_data():
    """Load audit report data from markdown files."""
    audit_path = Path('/home/feye/frappe-bench/apps/itsm_core/Docs/FINAL_AUDIT_REPORT.md')
    arch_path = Path('/home/feye/frappe-bench/apps/itsm_core/Docs/itsm_core_architecture.md')
    
    audit_content = audit_path.read_text() if audit_path.exists() else ""
    arch_content = arch_path.read_text() if arch_path.exists() else ""
    
    return audit_content, arch_content

async def capture_screenshots():
    """Capture UI screenshots using Playwright."""
    from playwright.async_api import async_playwright
    
    screenshots_dir = Path('/tmp/itsm_core_screenshots')
    screenshots_dir.mkdir(exist_ok=True)
    
    # Use environment variables or defaults
    base_url = os.environ.get('FRAPPE_URL', 'http://127.0.0.1:8001')
    username = os.environ.get('FRAPPE_USER', 'admin@mail.com')
    password = os.environ.get('FRAPPE_PASSWORD', 'admin')
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=1.5
        )
        page = await context.new_page()
        
        # Login
        print("Logging into Frappe...")
        await page.goto(f"{base_url}/login")
        await page.wait_for_selector('#login_email', timeout=10000)
        await page.fill('#login_email', username)
        await page.fill('#login_password', password)
        await page.click('button[type="submit"]')
        # Wait for navigation to complete (could be desk, helpdesk, or other)
        await page.wait_for_load_state('networkidle', timeout=15000)
        await page.wait_for_timeout(2000)
        
        # Capture IT Operations Workspace Dashboard
        print("Capturing IT Operations Dashboard...")
        await page.goto(f"{base_url}/desk/it-operations")
        await page.wait_for_timeout(3000)  # Wait for charts to render
        dashboard_path = screenshots_dir / "dashboard.png"
        await page.screenshot(path=str(dashboard_path), full_page=True)
        print(f"  Saved: {dashboard_path}")
        
        # Capture Change Request List View
        print("Capturing Change Request List...")
        await page.goto(f"{base_url}/app/change-request")
        await page.wait_for_timeout(2000)
        list_path = screenshots_dir / "change_request_list.png"
        await page.screenshot(path=str(list_path), full_page=True)
        print(f"  Saved: {list_path}")
        
        # Capture New Change Request Form
        print("Capturing Change Request Form...")
        # Try multiple selectors for the New button
        try:
            await page.click('button:has-text("New")', timeout=5000)
        except:
            try:
                await page.click('.btn-primary:has-text("New")', timeout=5000)
            except:
                try:
                    await page.click('[data-doctype="Change Request"] .btn-primary', timeout=5000)
                except:
                    # Just navigate to the new form directly
                    await page.goto(f"{base_url}/app/change-request/new")
        await page.wait_for_timeout(2000)
        form_path = screenshots_dir / "change_request_form.png"
        await page.screenshot(path=str(form_path), full_page=True)
        print(f"  Saved: {form_path}")
        
        # Capture Workspace Navigation
        print("Capturing Module Navigation...")
        await page.goto(f"{base_url}/desk")
        await page.wait_for_timeout(1000)
        desk_path = screenshots_dir / "desk_navigation.png"
        await page.screenshot(path=str(desk_path), full_page=True)
        print(f"  Saved: {desk_path}")
        
        await browser.close()
        
        return {
            'dashboard': str(dashboard_path),
            'change_request_list': str(list_path),
            'change_request_form': str(form_path),
            'desk_navigation': str(desk_path)
        }

def extract_api_endpoints(audit_content):
    """Extract API endpoints from audit content."""
    endpoints = [
        {
            'name': 'ingest_grafana_alert',
            'method': 'POST',
            'auth_role': 'Grafana Integration',
            'allow_guest': False,
            'purpose': 'Receive Grafana webhooks; create/update HD Tickets with deduplication, flapping handling, and priority-based resolution rules',
            'input_fields': ['fingerprint', 'status (firing/resolved)', 'startsAt', 'labels.service', 'labels.severity', 'annotations.summary', 'annotations.runbook_url'],
            'output': 'JSON with status, processed count, and results array containing action (created/updated/reopened/auto_resolved/awaiting_verification), ticket name, priority, occurrence_count'
        },
        {
            'name': 'get_change_state',
            'method': 'POST',
            'auth_role': 'CI Integration',
            'allow_guest': False,
            'purpose': 'CI gate: verify Change Request state and repo match before allowing deployment',
            'input_fields': ['change_request_id', 'repo', 'environment (optional)'],
            'output': 'JSON with change_request, workflow_state, approved_for_deployment (boolean), repo. Returns 403 if repo empty/mismatch or environment mismatch. Only returns approved_for_deployment=true at "Approved for Deployment" state.'
        },
        {
            'name': 'record_deployment',
            'method': 'POST',
            'auth_role': 'CI Integration',
            'allow_guest': False,
            'purpose': 'Append deployment evidence to Change Request (never overwrites)',
            'input_fields': ['change_request_id', 'evidence (text)'],
            'output': 'JSON with status, change_request name, logged_by (actor). Appends timestamped entry to deployment_evidence field.'
        },
        {
            'name': 'replay_webhook',
            'method': 'POST',
            'auth_role': 'System Manager',
            'allow_guest': False,
            'purpose': 'Manually replay a stored Grafana Webhook Log payload through the ingestion pipeline',
            'input_fields': ['webhook_log_name'],
            'output': 'JSON with status, processed count, results array. Marks log with replay=1.'
        },
        {
            'name': 'heartbeat',
            'method': 'GET',
            'auth_role': 'None (allow_guest=True)',
            'allow_guest': True,
            'purpose': 'Liveness/health check endpoint with basic rate limiting',
            'input_fields': 'None',
            'output': '{"status": "ok"} on success (200). Rate limited to 60 req/min/IP (429 after). Returns 500 on DB failure.'
        },
        {
            'name': 'synthetic_alert',
            'method': 'POST',
            'auth_role': 'System Manager',
            'allow_guest': False,
            'purpose': 'End-to-end test of the full ingestion pipeline (creates test firing alert)',
            'input_fields': 'None',
            'output': 'Same structure as ingest_grafana_alert results. Creates test alert with fingerprint synthetic-<timestamp>.'
        }
    ]
    return endpoints

def extract_workflow_steps(audit_content):
    """Extract workflow steps from audit content."""
    return [
        {'step': 1, 'state': 'Draft', 'description': 'Initial creation by Change Requester', 'allowed_role': 'Change Requester'},
        {'step': 2, 'state': 'Risk Assessment', 'description': 'Author reviews risk assessment', 'allowed_role': 'Change Requester'},
        {'step': 3, 'state': 'Pending Approval', 'description': 'Awaiting approval', 'allowed_role': 'Change Approver'},
        {'step': 4, 'state': 'Approved for Deployment', 'description': 'Ready to deploy; approved_by auto-set', 'allowed_role': 'Change Implementer'},
        {'step': 5, 'state': 'Implemented', 'description': 'Deployed; implemented_on, implementer set', 'allowed_role': 'Change Implementer'},
        {'step': 6, 'state': 'Post-Implementation Review', 'description': 'PIR phase; outcome required', 'allowed_role': 'Change Manager'},
        {'step': 7, 'state': 'Closed', 'description': 'Completed', 'allowed_role': 'Change Manager'},
        {'step': 8, 'state': 'Rejected', 'description': 'Denied by Approver', 'allowed_role': 'Change Requester'},
        {'step': 9, 'state': 'Cancelled', 'description': 'Cancelled by Requester or Manager', 'allowed_role': 'Change Requester / Change Manager'},
    ]

def generate_docx_report(audit_content, arch_content, screenshots):
    """Generate the professional .docx report."""
    from docx import Document
    from docx.shared import Inches, Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    
    doc = Document()
    
    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    
    # Configure heading styles
    for level in range(1, 4):
        heading_style = doc.styles[f'Heading {level}']
        heading_style.font.name = 'Calibri'
        heading_style.font.color.rgb = RGBColor(0x1B, 0x3A, 0x5C)
        if level == 1:
            heading_style.font.size = Pt(24)
            heading_style.font.bold = True
        elif level == 2:
            heading_style.font.size = Pt(18)
            heading_style.font.bold = True
        elif level == 3:
            heading_style.font.size = Pt(14)
            heading_style.font.bold = True
    
    # Title Page
    for _ in range(4):
        doc.add_paragraph('')
    
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run('IT Operations Module\nTechnical Overview & Functional Specification')
    run.font.size = Pt(28)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x1B, 0x3A, 0x5C)
    
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run('itsm_core Frappe/ERPNext v16 Custom Application')
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    
    doc.add_paragraph('')
    
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = info.add_run(f'Version 1.0.0  |  Frappe/ERPNext v16.51.0  |  Site: fastpay.local\nGenerated: {datetime.now().strftime("%B %d, %Y")}')
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
    
    doc.add_page_break()
    
    # Table of Contents
    doc.add_heading('Table of Contents', level=1)
    toc_items = [
        '1. Executive Summary',
        '2. Core Features',
        '3. Workflow Overview',
        '4. API Endpoints Reference',
        '5. UI Overview & Screenshots',
        '6. Technical Architecture',
        '7. Outstanding Design Decisions',
        'Appendix A: API Usage Examples'
    ]
    for i, item in enumerate(toc_items, 1):
        p = doc.add_paragraph(f'{i}. {item}')
        p.style = 'List Number'
    
    doc.add_page_break()
    
    # 1. Executive Summary
    doc.add_heading('1. Executive Summary', level=1)
    
    exec_summary = """
    The IT Operations module (itsm_core) is a Frappe/ERPNext v16 custom application that replaces external middleware 
    with native Grafana webhook ingestion, HD Ticket deduplication, and unified Change Request lifecycle management. 
    It operates entirely within ERPNext's Helpdesk (HD Ticket) and Desk framework, providing a single system of record 
    for incident management, change control, and service topology.
    
    Key Capabilities:
    • Incident Management: Automated Grafana → HD Ticket pipeline with fingerprint-based deduplication, flapping 
      detection, and priority-based resolution rules (Critical/High require human verification on recovery).
    • Change Management: Single Change Request DocType governing Standard, Normal, and Emergency changes with 
      progressive disclosure, ITIL-aligned approval workflow, and custom field locking post-approval.
    • Service Topology: Service Registry links services to owners, tiers, runbooks, and configurable reopen windows.
    • CI/CD Gates: get_change_state and record_deployment endpoints for pipeline integration with fail-closed security.
    • Observability: Grafana Webhook Log for audit/replay, heartbeat for liveness, synthetic alerts for end-to-end testing.
    
    Security Posture: API-token authentication only (dedicated Grafana Integration / CI Integration users), 
    fail-closed authorization, role-based access control, and break-glass emergency authorization.
    """
    doc.add_paragraph(exec_summary.strip())
    
    doc.add_page_break()
    
    # 2. Core Features
    doc.add_heading('2. Core Features', level=1)
    
    # 2.1 Incident Management
    doc.add_heading('2.1 Incident Management (Grafana → HD Ticket)', level=2)
    inc_items = [
        'Automated webhook ingestion at /api/method/itsm_core.api.ingest_grafana_alert with API-token authentication',
        'Fingerprint-based deduplication using composite key alert_instance_key = fingerprint:startsAt',
        'Atomic occurrence counting and last_seen updates on re-firing alerts',
        'Flapping detection with configurable reopen window (Service Registry override → ITSM Settings default 24h)',
        'Priority-based resolution: Critical/High alerts require human verification on recovery (awaiting_verification); Medium/Low auto-resolve',
        'Unregistered service handling: ticket created with "Unregistered service: <name>" in description, subject truncated to 140 chars',
        'Per-alert savepoint isolation with automatic rollback on failure; no mid-request commits'
    ]
    for item in inc_items:
        doc.add_paragraph(item, style='List Bullet')
    
    # 2.2 Change Management
    doc.add_heading('2.2 Change Management (Progressive Disclosure)', level=2)
    cm_items = [
        'Single Change Request DocType with three change types: Standard (lean), Normal (full), Emergency (break-glass)',
        'Progressive disclosure: Standard hides impact, likelihood, computed_risk_score, validation_criteria; rollback_plan required for all types',
        'Emergency changes require Change Manager role; auto-sets emergency_authorized_by and retro_review_due (+24h) on first save only',
        'Standard changes blocked on Critical-tier services and Data category; risk_level forced to Low',
        '8-state approval workflow (Draft → Risk Assessment → Pending Approval → Approved for Deployment → Implemented → Post-Implementation Review → Closed/Rejected/Cancelled)',
        'Author ≠ Approver enforced at Pending Approval → Approved for Deployment transition',
        'Custom field locking after approval (all workflow states at doc_status=0; native submit locking inactive)',
        'CI/CD integration: repo field mandatory for Code category; deployment_evidence append-only via record_deployment'
    ]
    for item in cm_items:
        doc.add_paragraph(item, style='List Bullet')
    
    # 2.3 Service Topology
    doc.add_heading('2.3 Service Topology & Registry', level=2)
    st_items = [
        'Service Registry DocType with service_name, owning_team (Role), service_owner (User), runbook_url, tier (Critical/High/Medium/Low), slack_channel, grafana_dashboard_url',
        'Per-service reopen_window_hours overrides ITSM Settings default (24h)',
        'Runbook URL from registry applied to HD Ticket before alert-provided URL',
        'Service Registry tier hierarchy: Critical (highest, blocks Standard changes) → High → Medium → Low'
    ]
    for item in st_items:
        doc.add_paragraph(item, style='List Bullet')
    
    doc.add_page_break()
    
    # 3. Workflow Overview
    doc.add_heading('3. Workflow Overview: Change Request Approval', level=1)
    
    workflow_text = """
    The Change Request Approval workflow operates with all 9 states mapped to doc_status=0 (Draft). 
    Frappe's native submit locking (which activates at doc_status=1) never triggers; custom field locking 
    in _lock_fields_after_approval() is the sole protection against post-approval modifications.
    """
    doc.add_paragraph(workflow_text.strip())
    
    # Workflow table
    doc.add_heading('3.1 State Definitions', level=2)
    table = doc.add_table(rows=10, cols=4, style='Table Grid')
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    headers = ['#', 'State', 'DocStatus', 'Allow Edit Role']
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = header
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(10)
    
    workflow_states = [
        ('1', 'Draft', '0', 'Change Requester'),
        ('2', 'Risk Assessment', '0', 'Change Requester'),
        ('3', 'Pending Approval', '0', 'Change Approver'),
        ('4', 'Approved for Deployment', '0', 'Change Implementer'),
        ('5', 'Implemented', '0', 'Change Implementer'),
        ('6', 'Post-Implementation Review', '0', 'Change Manager'),
        ('7', 'Closed', '0', 'Change Manager'),
        ('8', 'Rejected', '0', 'Change Requester'),
        ('9', 'Cancelled', '0', 'Change Requester / Change Manager'),
    ]
    
    for row_idx, (num, state, docstatus, role) in enumerate(workflow_states, 1):
        row = table.rows[row_idx]
        row.cells[0].text = num
        row.cells[1].text = state
        row.cells[2].text = docstatus
        row.cells[3].text = role
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(10)
    
    # Transitions
    doc.add_heading('3.2 Key Transitions', level=2)
    trans_table = doc.add_table(rows=11, cols=5, style='Table Grid')
    trans_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    trans_headers = ['From State', 'Action', 'To State', 'Allowed Role', 'Allow Self?']
    for i, header in enumerate(trans_headers):
        cell = trans_table.rows[0].cells[i]
        cell.text = header
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(10)
    
    transitions = [
        ('Draft', 'Submit for Approval', 'Risk Assessment', 'Change Requester', 'Yes'),
        ('Risk Assessment', 'Submit for Approval', 'Pending Approval', 'Change Requester', 'Yes'),
        ('Pending Approval', 'Approve', 'Approved for Deployment', 'Change Approver', 'No'),
        ('Pending Approval', 'Reject / Request Changes', 'Rejected', 'Change Approver', 'No'),
        ('Rejected', 'Reopen', 'Draft', 'Change Requester', 'Yes'),
        ('Approved for Deployment', 'Mark Implemented', 'Implemented', 'Change Implementer', 'Yes'),
        ('Implemented', 'Close', 'Post-Implementation Review', 'Change Manager', 'Yes'),
        ('Implemented', 'Start Review', 'Post-Implementation Review', 'Change Manager', 'Yes*'),
        ('Post-Implementation Review', 'Close Review', 'Closed', 'Change Manager', 'Yes'),
        ('Draft/Pending/Approved', 'Cancel Request', 'Cancelled', 'Change Requester / Change Manager', 'Yes'),
    ]
    
    for row_idx, (from_s, action, to_s, role, self_allowed) in enumerate(transitions, 1):
        row = trans_table.rows[row_idx]
        row.cells[0].text = from_s
        row.cells[1].text = action
        row.cells[2].text = to_s
        row.cells[3].text = role
        row.cells[4].text = self_allowed
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)
    
    doc.add_paragraph('')
    p = doc.add_paragraph()
    run = p.add_run('* Start Review: condition doc.change_type == "Emergency" or doc.outcome in ("Failed", "Rolled back")')
    run.font.size = Pt(9)
    run.font.italic = True
    
    doc.add_page_break()
    
    # 4. API Endpoints Reference
    doc.add_heading('4. API Endpoints Reference', level=1)
    
    intro = """
    All endpoints are accessed under /api/method/itsm_core.api.<function>. Authentication uses API tokens 
    via Authorization: token <token> header. All endpoints are fail-closed on missing/invalid tokens. 
    Responses are wrapped in {"message": ...} envelope.
    """
    doc.add_paragraph(intro.strip())
    
    endpoints = extract_api_endpoints(audit_content)
    
    for ep in endpoints:
        doc.add_heading(f'4.{endpoints.index(ep)+1} {ep["name"]}', level=2)
        
        # Summary table
        sum_table = doc.add_table(rows=6, cols=2, style='Table Grid')
        sum_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        sum_data = [
            ('Endpoint', f'/api/method/itsm_core.api.{ep["name"]}'),
            ('HTTP Method', ep['method']),
            ('Authentication Role', ep['auth_role']),
            ('Allow Guest', 'Yes' if ep['allow_guest'] else 'No'),
            ('Purpose', ep['purpose']),
            ('Input Parameters', ', '.join(ep['input_fields']))
        ]
        
        for row_idx, (label, value) in enumerate(sum_data):
            row = sum_table.rows[row_idx]
            row.cells[0].text = label
            row.cells[1].text = value
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(10)
                        if cell == row.cells[0]:
                            run.font.bold = True
        
        # Input/Output details
        doc.add_paragraph('')
        p = doc.add_paragraph()
        run = p.add_run('Input Fields: ')
        run.font.bold = True
        run.font.size = Pt(10)
        run = p.add_run(', '.join(ep['input_fields']))
        run.font.size = Pt(10)
        
        p = doc.add_paragraph()
        run = p.add_run('Output: ')
        run.font.bold = True
        run.font.size = Pt(10)
        run = p.add_run(ep['output'])
        run.font.size = Pt(10)
        
        doc.add_paragraph('')
    
    doc.add_page_break()
    
    # 5. UI Overview & Screenshots
    doc.add_heading('5. UI Overview & Screenshots', level=1)
    
    ui_intro = """
    The following screenshots demonstrate the current state of the IT Operations module UI as captured 
    from the live fastpay.local instance (Frappe/ERPNext v16.51.0).
    """
    doc.add_paragraph(ui_intro.strip())
    
    # Screenshots
    screenshot_configs = [
        ('dashboard', '5.1 IT Operations Dashboard', 'The IT Operations workspace showing the 6-chart dashboard layout: Open Tickets by Priority (Donut), Open Tickets by Status (Bar), Change Requests by State (Bar), Tickets Created Last 30 Days (Line), Change Requests by Type (Donut), and Changes per Month (Line).'),
        ('desk_navigation', '5.2 Desk Navigation & Module Access', 'The Frappe Desk showing the ITSM Core module (labeled "IT Operations" with flag icon) accessible via Awesomebar (Ctrl+K) and module sidebar.'),
        ('change_request_list', '5.3 Change Request List View', 'The Change Request list view showing filters, search, and actions. Standard view with workflow_state, change_type, risk_level columns visible.'),
        ('change_request_form', '5.4 New Change Request Form', 'The Change Request form demonstrating progressive disclosure: Basics section (title, change_type, risk_level), Services & Schedule, Why & What, Risk Assessment (conditional), Safety (collapsible), CI/CD (conditional on Code category), and System (collapsible, hidden on new documents).')
    ]
    
    for key, title, caption in screenshot_configs:
        if key in screenshots and os.path.exists(screenshots[key]):
            doc.add_heading(title, level=2)
            doc.add_picture(screenshots[key], width=Inches(6.5))
            p = doc.add_paragraph(caption)
            p.style = 'Caption' if 'Caption' in doc.styles else 'Normal'
            for run in p.runs:
                run.font.size = Pt(9)
                run.font.italic = True
                run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
            doc.add_paragraph('')
        else:
            doc.add_heading(title, level=2)
            p = doc.add_paragraph(f'[Screenshot not available: {key}]')
            p.runs[0].font.italic = True
            p.runs[0].font.color.rgb = RGBColor(0x99, 0x99, 0x99)
            doc.add_paragraph('')
    
    doc.add_page_break()
    
    # 6. Technical Architecture
    doc.add_heading('6. Technical Architecture', level=1)
    
    arch_items = [
        ('Platform', 'Frappe Framework v16.51.0 / ERPNext v16.51.0 (Helpdesk module for HD Ticket)'),
        ('Application', 'itsm_core (custom app, module "ITSM Core", workspace label "IT Operations")'),
        ('Database', 'MariaDB (via Frappe ORM); HD Ticket for ticketing, custom DocTypes for CR, Service Registry, ITSM Settings'),
        ('Authentication', 'API-token only (Header: Authorization: token <token>); dedicated Grafana Integration and CI Integration users; no HMAC, no session auth for API endpoints'),
        ('Rate Limiting', 'Heartbeat endpoint: 60 requests/minute/IP (fail-open on cache error)'),
        ('Data Integrity', 'Composite unique index on HD Ticket.alert_instance_key (fingerprint:startsAt); atomic SQL increment for occurrence_count; savepoint isolation per alert; per-alert rollback on failure'),
        ('Workflow Engine', 'Frappe Workflow with 9 states (all doc_status=0); custom field locking via _lock_fields_after_approval() since native submit locking never activates'),
        ('Deployment', 'Bench-managed; fixtures for Roles, Workflow, Dashboard Charts, Custom Fields, HD Ticket Priority/Status/SLA; workspace via JSON')
    ]
    
    for label, value in arch_items:
        p = doc.add_paragraph()
        run = p.add_run(f'{label}: ')
        run.font.bold = True
        run.font.size = Pt(10)
        run = p.add_run(value)
        run.font.size = Pt(10)
    
    doc.add_page_break()
    
    # 7. Outstanding Design Decisions
    doc.add_heading('7. Outstanding Design Decisions (Human Review Required)', level=1)
    
    decisions = [
        ('1', 'Standard Change Template Revisit Trigger', 'DECISION NEEDED', 'Threshold X% for "Standard exceeds X% of changes over 90 days" — set X when operational data available'),
        ('2', 'Return to Draft from Pending Approval', 'Proposed, Not Applied', 'Add transition Pending Approval → Draft (action: "Return to Draft") for Change Approver with required review_comment (Small Text). Awaits approval.'),
        ('3', 'Workflow doc_status Mapping', 'Known Gap', 'All states = doc_status 0. Native submit locking inactive. Custom locking works but is non-standard. Consider adding "Submitted" state (doc_status=1) at "Approved for Deployment" if workflow engine supports.'),
        ('4', 'HD Ticket Priority "Critical"', 'Missing', 'HD Ticket Priority fixture has Critical/High/Medium/Low but HD Ticket DocType may not expose "Critical" — severity map uses "Urgent" as fallback. Verify Helpdesk v16 schema.'),
        ('5', 'Auto-Resolved HD Ticket SLA Pause', 'Unverified', 'Whether "Auto-Resolved" status pauses SLA via HD Service Level Agreement rules — needs Helpdesk v16 verification.'),
        ('6', 'Standard CR risk_level Forced to Low', 'Implemented', '_derive_risk_level() forces "Low" for Standard (impact/likelihood hidden). Correct per lean path.'),
    ]
    
    dec_table = doc.add_table(rows=len(decisions)+1, cols=4, style='Table Grid')
    dec_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    dec_headers = ['#', 'Item', 'Status', 'Details']
    for i, header in enumerate(dec_headers):
        cell = dec_table.rows[0].cells[i]
        cell.text = header
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(10)
    
    for row_idx, (num, item, status, details) in enumerate(decisions, 1):
        row = dec_table.rows[row_idx]
        row.cells[0].text = num
        row.cells[1].text = item
        row.cells[2].text = status
        row.cells[3].text = details
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)
    
    doc.add_page_break()
    
    # Appendix A: API Usage Examples
    doc.add_heading('Appendix A: API Usage Examples', level=1)
    
    examples = """
# Grafana Webhook Configuration
curl -X POST https://fastpay.local/api/method/itsm_core.api.ingest_grafana_alert \\
  -H "Authorization: token <grafana_integration_token>" \\
  -H "Content-Type: application/json" \\
  -d '{"alerts":[{"fingerprint":"fp-001","status":"firing","startsAt":"2026-10-28T12:00:00Z","labels":{"service":"payments-api","severity":"critical"},"annotations":{"summary":"High CPU","runbook_url":"https://runbooks/cpu.md"}}]}'

# CI Pipeline Gate (GitHub Actions / GitLab CI)
STATE=$(curl -s -X POST https://fastpay.local/api/method/itsm_core.api.get_change_state \\
  -H "Authorization: token <ci_integration_token>" \\
  -H "Content-Type: application/json" \\
  -d '{"change_request_id":"CRQ-2026-00001","repo":"github.com/org/repo","environment":"Production"}')

if echo "$STATE" | jq -e '.message.approved_for_deployment' >/dev/null; then
  echo "Deploy approved"
else
  echo "Deploy blocked: $(echo "$STATE" | jq -r '.message.message')"
  exit 1
fi

# CI Post-Deploy Evidence Recording
curl -X POST https://fastpay.local/api/method/itsm_core.api.record_deployment \\
  -H "Authorization: token <ci_integration_token>" \\
  -H "Content-Type: application/json" \\
  -d '{"change_request_id":"CRQ-2026-00001","evidence":"Deployed v1.2.3 to prod; smoke tests passed"}'

# Health Check
curl https://fastpay.local/api/method/itsm_core.api.heartbeat

# Manual Webhook Replay (System Manager)
curl -X POST https://fastpay.local/api/method/itsm_core.api.replay_webhook \\
  -H "Authorization: token <system_manager_token>" \\
  -H "Content-Type: application/json" \\
  -d '{"webhook_log_name":"GWL-00001"}'
    """
    doc.add_paragraph(examples.strip())
    
    # Save
    output_path = Path('/home/feye/frappe-bench/IT_Operations_Module_Overview.docx')
    doc.save(output_path)
    print(f"\nReport saved to: {output_path}")
    return output_path


async def main():
    print("=" * 60)
    print("IT Operations Module Report Generator")
    print("=" * 60)
    
    # Install dependencies
    install_dependencies()
    
    # Load audit data
    print("\nLoading audit data...")
    audit_content, arch_content = load_audit_data()
    
    # Capture screenshots
    print("\nCapturing UI screenshots...")
    screenshots = await capture_screenshots()
    
    # Generate report
    print("\nGenerating .docx report...")
    output_path = generate_docx_report(audit_content, arch_content, screenshots)
    
    # Verify
    if Path(output_path).exists():
        size = Path(output_path).stat().st_size
        print(f"\n✅ Report generated successfully!")
        print(f"   Location: {output_path}")
        print(f"   Size: {size:,} bytes")
    else:
        print(f"\n❌ Report generation failed!")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())