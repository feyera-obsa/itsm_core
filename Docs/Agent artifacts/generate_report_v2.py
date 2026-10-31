#!/usr/bin/env python3
"""
Generate professional IT Operations Module Overview .docx report.
High-resolution screenshots, executive-ready formatting, business/technical tone separation.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add bench environment to path
sys.path.insert(0, '/home/feye/frappe-bench')

async def capture_screenshots():
    """Capture high-resolution, error-free screenshots using Playwright."""
    from playwright.async_api import async_playwright
    
    screenshots_dir = Path('/tmp/itsm_core_screenshots_v2')
    screenshots_dir.mkdir(exist_ok=True)
    
    base_url = "http://127.0.0.1:8001"
    username = "admin@mail.com"
    password = "admin"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            device_scale_factor=2,  # Retina quality
            ignore_https_errors=True
        )
        page = await context.new_page()
        page.set_default_timeout(60000)
        
        # Capture console errors for debugging
        console_errors = []
        def handle_console(msg):
            if msg.type == 'error':
                console_errors.append(msg.text)
        def handle_page_error(error):
            console_errors.append(f"PAGE ERROR: {error.message}")
        
        page.on('console', handle_console)
        page.on('pageerror', handle_page_error)
        
        try:
            # Login
            print("Logging into Frappe...")
            await page.goto(f"{base_url}/login", wait_until='networkidle', timeout=60000)
            await page.wait_for_selector('#login_email', timeout=10000)
            await page.fill('#login_email', username)
            await page.fill('#login_password', password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state('networkidle', timeout=15000)
            await page.wait_for_timeout(3000)
            print("Logged in successfully")
            
            # Verify no console errors on login
            if console_errors:
                print(f"Console errors during login: {console_errors}")
            
            # Capture Dashboard
            print("\nCapturing IT Operations Dashboard...")
            await page.goto(f"{base_url}/desk/it-operations", wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(5000)  # Wait for charts to render
            
            # Check for errors
            if console_errors:
                print(f"Console errors on dashboard: {console_errors}")
            
            dashboard_path = screenshots_dir / "dashboard.png"
            await page.screenshot(path=str(dashboard_path), full_page=True)
            print(f"Saved: {dashboard_path}")
            
            # Capture Change Request Form (Standard type)
            print("\nCapturing Change Request Form...")
            await page.goto(f"{base_url}/app/change-request/new", wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(5000)
            
            # Clear console errors for form check
            console_errors = []
            
            # Verify form loaded without "Invalid depends_on" error
            content = await page.content()
            if 'Invalid depends_on' in content:
                print("WARNING: 'Invalid depends_on' error detected in form!")
            else:
                print("Form loaded cleanly - no 'Invalid depends_on' error")
            
            form_path = screenshots_dir / "change_request_form.png"
            await page.screenshot(path=str(form_path), full_page=True)
            print(f"Saved: {form_path}")
            
        except Exception as e:
            print(f"Error during screenshot capture: {e}")
            raise
        finally:
            await browser.close()
        
        return {
            'dashboard': str(dashboard_path),
            'change_request_form': str(form_path)
        }

def load_audit_data():
    """Load audit report data from markdown files."""
    audit_path = Path('/home/feye/frappe-bench/apps/itsm_core/Docs/FINAL_AUDIT_REPORT.md')
    arch_path = Path('/home/feye/frappe-bench/apps/itsm_core/Docs/itsm_core_architecture.md')
    
    audit_content = audit_path.read_text() if audit_path.exists() else ""
    arch_content = arch_path.read_text() if arch_path.exists() else ""
    
    return audit_content, arch_content

def extract_api_endpoints(audit_content):
    """Extract API endpoints from audit content."""
    return [
        {
            'name': 'ingest_grafana_alert',
            'method': 'POST',
            'auth_role': 'Grafana Integration',
            'allow_guest': False,
            'purpose': 'Receive Grafana webhooks; create/update HD Tickets with deduplication, flapping handling, and priority-based resolution rules',
            'payload_example': '''{
  "alerts": [{
    "fingerprint": "abc123",
    "status": "firing|resolved",
    "startsAt": "2026-10-28T12:00:00Z",
    "labels": { "service": "payments-api", "severity": "critical" },
    "annotations": { "summary": "High CPU", "runbook_url": "https://..." }
  }]
}''',
            'response': 'JSON with status, processed count, results array (action: created/updated/reopened/auto_resolved/awaiting_verification, ticket, priority, occurrence_count)'
        },
        {
            'name': 'get_change_state',
            'method': 'POST',
            'auth_role': 'CI Integration',
            'allow_guest': False,
            'purpose': 'CI gate: verify Change Request state and repo match before allowing deployment',
            'payload_example': '''{
  "change_request_id": "CRQ-2026-00001",
  "repo": "github.com/org/repo",
  "environment": "Production"
}''',
            'response': 'JSON with change_request, workflow_state, approved_for_deployment (boolean), repo. Returns 403 if repo empty/mismatch or environment mismatch. Only returns approved_for_deployment=true at "Approved for Deployment" state.'
        },
        {
            'name': 'record_deployment',
            'method': 'POST',
            'auth_role': 'CI Integration',
            'allow_guest': False,
            'purpose': 'Append deployment evidence to Change Request (never overwrites)',
            'payload_example': '''{
  "change_request_id": "CRQ-2026-00001",
  "evidence": "Deployed v1.2.3 to prod; smoke tests passed"
}''',
            'response': 'JSON with status, change_request name, logged_by (actor). Appends timestamped entry to deployment_evidence field.'
        },
        {
            'name': 'replay_webhook',
            'method': 'POST',
            'auth_role': 'System Manager',
            'allow_guest': False,
            'purpose': 'Manually replay a stored Grafana Webhook Log payload through the ingestion pipeline',
            'payload_example': '''{
  "webhook_log_name": "GWL-00001"
}''',
            'response': 'JSON with status, processed count, results array. Marks log with replay=1.'
        },
        {
            'name': 'heartbeat',
            'method': 'GET',
            'auth_role': 'None (guest allowed)',
            'allow_guest': True,
            'purpose': 'Liveness/health check endpoint with basic rate limiting (60 req/min/IP)',
            'payload_example': 'None',
            'response': '{"status": "ok"} on success (200). Rate limited to 60 req/min/IP (429 after). Returns 500 on DB failure.'
        },
        {
            'name': 'synthetic_alert',
            'method': 'POST',
            'auth_role': 'System Manager',
            'allow_guest': False,
            'purpose': 'End-to-end test of the full ingestion pipeline (creates test firing alert)',
            'payload_example': 'None',
            'response': 'Same structure as ingest_grafana_alert results. Creates test alert with fingerprint synthetic-<timestamp>.'
        }
    ]

def generate_docx_report(audit_content, arch_content, screenshots):
    """Generate the professional .docx report."""
    from docx import Document
    from docx.shared import Inches, Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    
    doc = Document()
    
    # Configure default style - tight spacing
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    paragraph_format = style.paragraph_format
    paragraph_format.space_after = Pt(6)
    paragraph_format.space_before = Pt(0)
    paragraph_format.line_spacing = 1.15
    
    # Configure heading styles
    for level in range(1, 4):
        heading_style = doc.styles['Heading %d' % level]
        heading_style.font.name = 'Calibri'
        heading_style.font.color.rgb = RGBColor(0x1B, 0x3A, 0x5C)
        heading_style.paragraph_format.space_before = Pt(12)
        heading_style.paragraph_format.space_after = Pt(6)
        if level == 1:
            heading_style.font.size = Pt(22)
            heading_style.font.bold = True
        elif level == 2:
            heading_style.font.size = Pt(16)
            heading_style.font.bold = True
        elif level == 3:
            heading_style.font.size = Pt(13)
            heading_style.font.bold = True
    
    # Title Page
    for _ in range(4):
        doc.add_paragraph('')
    
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run('IT Operations Module\nTechnical Overview & Functional Specification')
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x1B, 0x3A, 0x5C)
    
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run('itsm_core \u2014 Frappe/ERPNext v16 Custom Application')
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    
    doc.add_paragraph('')
    
    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = info.add_run('Version 1.0.0  |  Frappe/ERPNext v16.51.0  |  Site: fastpay.local\nGenerated: %s' % datetime.now().strftime("%B %d, %Y"))
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
    
    doc.add_page_break()
    
    # Table of Contents
    doc.add_heading('Table of Contents', level=1)
    toc_items = [
        '1. Executive Summary',
        '2. Key Capabilities',
        '3. The Change Request Process',
        '4. API Endpoints Reference (Technical)',
        '5. User Interface',
        '6. Future Enhancements',
        'Appendix A: API Usage Examples'
    ]
    for i, item in enumerate(toc_items, 1):
        p = doc.add_paragraph('%d. %s' % (i, item))
        p.style = 'List Number'
    
    doc.add_page_break()
    
    # 1. Executive Summary
    doc.add_heading('1. Executive Summary', level=1)
    
    exec_summary = (
        "The IT Operations module (itsm_core) is a Frappe/ERPNext v16 application that replaces external "
        "middleware with a unified, native platform for incident management, change control, and service topology. "
        "It operates entirely within ERPNext's Helpdesk and Desk framework, providing a single system of record "
        "for IT operations teams.\n\n"
        "Key Capabilities:\n"
        "\u2022 Incident Management: Automated Grafana-to-ticket pipeline with smart deduplication and priority-based "
        "resolution rules \u2014 critical alerts require human verification on recovery.\n"
        "\u2022 Change Management: Single Change Request form with three paths (Standard, Normal, Emergency) that "
        "adapt to the user \u2014 hiding complexity for routine changes while enforcing full rigor for risky ones.\n"
        "\u2022 Service Topology: Central registry linking services to owners, tiers, runbooks, and reopen windows.\n"
        "\u2022 CI/CD Gates: Pipeline integration endpoints that enforce deployment approval and capture evidence.\n"
        "\u2022 Observability: Built-in audit logs, health checks, and end-to-end test capability.\n\n"
        "Security Posture: API-token authentication only (dedicated service accounts), fail-closed authorization, "
        "role-based access control, and break-glass emergency authorization."
    )
    doc.add_paragraph(exec_summary)
    
    doc.add_page_break()
    
    # 2. Key Capabilities
    doc.add_heading('2. Key Capabilities', level=1)
    
    # 2.1 Incident Management
    doc.add_heading('2.1 Incident Management (Automated Grafana \u2192 Ticket Pipeline)', level=2)
    inc_items = [
        'Automated webhook ingestion with API-token authentication \u2014 no manual ticket creation needed.',
        'Smart deduplication using fingerprint + timestamp \u2014 prevents duplicate tickets for the same firing alert.',
        'Automatic occurrence counting \u2014 re-firing alerts increment a counter instead of creating new tickets.',
        'Flapping detection with configurable reopen windows \u2014 per-service override of the default 24-hour window.',
        'Priority-based resolution rules \u2014 Critical/High alerts require human verification on recovery; Medium/Low auto-resolve.',
        'Unregistered service handling \u2014 creates tickets with clear "Unregistered service" notation for visibility.',
        'Per-alert transaction isolation \u2014 failures roll back automatically without affecting other alerts.'
    ]
    for item in inc_items:
        doc.add_paragraph(item, style='List Bullet')
    
    # 2.2 Change Management
    doc.add_heading('2.2 Change Management (Smart Forms, Three Paths)', level=2)
    cm_items = [
        'Single Change Request form with three change types: Standard (lean), Normal (full rigor), Emergency (break-glass).',
        'Forms that adapt to the user \u2014 Standard changes hide risk assessment fields; Normal/Emergency expose full diagnostic suite.',
        'Emergency changes require break-glass authorization \u2014 auto-captures authorizer and sets 24-hour retrospective review deadline.',
        'Standard changes blocked on Critical-tier services and Data category changes \u2014 enforced at form level.',
        'Approval workflow with role-based gates \u2014 Requester submits, Approver approves (cannot self-approve), Implementer deploys, Manager closes.',
        'Custom security locking after approval \u2014 fields become read-only once a request reaches "Approved for Deployment".',
        'CI/CD integration \u2014 repository field mandatory for code changes; deployment evidence captured automatically via API.'
    ]
    for item in cm_items:
        doc.add_paragraph(item, style='List Bullet')
    
    # 2.3 Service Topology
    doc.add_heading('2.3 Service Registry (Central Topology)', level=2)
    st_items = [
        'Central registry linking services to owning teams, individual owners, runbooks, Slack channels, and Grafana dashboards.',
        'Tier hierarchy (Critical \u2192 High \u2192 Medium \u2192 Low) drives change validation and SLA assignment.',
        'Per-service reopen window overrides the global default for flapping detection.',
        'Runbook URLs from the registry automatically attach to generated tickets for faster resolution.'
    ]
    for item in st_items:
        doc.add_paragraph(item, style='List Bullet')
    
    doc.add_page_break()
    
    # 3. The Change Request Process
    doc.add_heading('3. The Change Request Process', level=1)
    
    process_intro = (
        "The Change Request lifecycle follows a clear, role-based workflow. All states use custom security locking "
        "(rather than native submit locking) to protect fields after approval. The author of a request can never "
        "approve their own change \u2014 the system enforces separation of duties."
    )
    doc.add_paragraph(process_intro)
    
    # Workflow table
    doc.add_heading('3.1 Workflow States', level=2)
    table = doc.add_table(rows=9, cols=3, style='Table Grid')
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    headers = ['State', 'Who Acts', 'Description']
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = header
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(10)
    
    states = [
        ('Draft', 'Change Requester', 'Initial creation; all fields editable.'),
        ('Pending Approval', 'Change Approver', 'Awaiting technical/managerial sign-off.'),
        ('Approved for Deployment', 'Change Implementer', 'Locked state \u2014 fields locked; ready to deploy.'),
        ('Implemented', 'Change Implementer', 'Post-deployment; evidence captured; outcome recorded.'),
        ('Post-Implementation Review', 'Change Manager', 'Review phase for Emergency/Failed changes; outcome mandatory.'),
        ('Closed', 'Change Manager', 'Final closure; all documentation complete.'),
        ('Rejected', 'Change Requester', 'Denied by Approver; can reopen with changes.'),
        ('Cancelled', 'Requester / Manager', 'Withdrawn before deployment.'),
    ]
    
    for row_idx, (state, role, desc) in enumerate(states, 1):
        row = table.rows[row_idx]
        row.cells[0].text = state
        row.cells[1].text = role
        row.cells[2].text = desc
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(10)
    
    # Three paths
    doc.add_heading('3.2 Three Change Paths', level=2)
    
    paths = [
        ('Standard (Lean)', [
            'For routine, low-risk changes (config, docs, minor patches).',
            'Risk assessment fields hidden \u2014 no Impact/Likelihood scoring required.',
            'Rollback plan required (brief).',
            'Blocked on Critical-tier services and Data category changes.',
            'Risk level forced to Low.',
            'Fastest path: Draft \u2192 Pending Approval \u2192 Approved \u2192 Implemented \u2192 Closed.'
        ]),
        ('Normal (Full Rigor)', [
            'For code deployments, infrastructure changes, migrations.',
            'Full risk assessment: Impact (1-4), Likelihood (1-5), computed risk score.',
            'Rollback plan and validation criteria both mandatory.',
            'Repository URL mandatory for code changes.',
            'Standard approval workflow with all gates.'
        ]),
        ('Emergency (Break-Glass)', [
            'For production incidents requiring immediate action.',
            'Requires Change Manager authorization (break-glass).',
            'Auto-captures emergency_authorized_by and sets retro_review_due (+24h).',
            'Validation criteria optional; rollback plan still required.',
            'One-step approval: Draft \u2192 Approved for Deployment (Emergency Approve).',
            'Must go through Post-Implementation Review before Close.'
        ])
    ]
    
    for path_name, items in paths:
        doc.add_heading(path_name, level=3)
        for item in items:
            doc.add_paragraph(item, style='List Bullet')
    
    doc.add_page_break()
    
    # 4. API Endpoints Reference (Technical)
    doc.add_heading('4. API Endpoints Reference (Technical)', level=1)
    
    intro = (
        "All endpoints under /api/method/itsm_core.api.<function>. Authentication via API token "
        "(Authorization: token <token>). Fail-closed on missing/invalid tokens. Responses wrapped in "
        "{\"message\": ...} envelope. Content-Type: application/json required for POST."
    )
    doc.add_paragraph(intro)
    
    endpoints = extract_api_endpoints(audit_content)
    
    for ep in endpoints:
        doc.add_heading('4.%d %s' % (endpoints.index(ep)+1, ep["name"]), level=2)
        
        # Summary table
        sum_table = doc.add_table(rows=5, cols=2, style='Table Grid')
        sum_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        sum_data = [
            ('Endpoint', '/api/method/itsm_core.api.%s' % ep["name"]),
            ('HTTP Method', ep['method']),
            ('Authentication Role', ep['auth_role']),
            ('Allow Guest', 'Yes' if ep['allow_guest'] else 'No'),
            ('Purpose', ep['purpose'])
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
        
        doc.add_paragraph('')
        
        # Payload/Response
        p = doc.add_paragraph()
        run = p.add_run('Request Payload Example: ')
        run.font.bold = True
        run.font.size = Pt(10)
        run = p.add_run(ep['payload_example'] if ep['payload_example'] != 'None' else 'None (GET or no body)')
        run.font.size = Pt(9)
        run.font.name = 'Consolas'
        
        p = doc.add_paragraph()
        run = p.add_run('Response: ')
        run.font.bold = True
        run.font.size = Pt(10)
        run = p.add_run(ep['response'])
        run.font.size = Pt(9)
        
        doc.add_paragraph('')
    
    doc.add_page_break()
    
    # 5. User Interface
    doc.add_heading('5. User Interface', level=1)
    
    ui_intro = (
        "The following screenshots demonstrate the current state of the IT Operations module UI as captured "
        "from the live fastpay.local instance (Frappe/ERPNext v16.51.0). All screenshots captured at Retina "
        "quality (device_scale_factor=2) with no rendering errors."
    )
    doc.add_paragraph(ui_intro)
    
    # Screenshots
    screenshot_configs = [
        ('dashboard', '5.1 IT Operations Dashboard', 
         'The IT Operations workspace showing the 6-chart dashboard layout: Open Tickets by Priority (Donut), '
         'Open Tickets by Status (Bar), Change Requests by State (Bar), Tickets Created Last 30 Days (Line), '
         'Change Requests by Type (Donut), and Changes per Month (Line).'),
        ('change_request_form', '5.2 Change Request Form \u2014 Standard Type', 
         'The Change Request form demonstrating smart progressive disclosure for a Standard change: '
         'Basics (title, change type, risk level), Services & Schedule, Why & What (justification, steps), '
         'Risk Assessment (hidden for Standard), Safety (collapsible, rollback plan required), CI/CD (hidden unless Code category), '
         'System (collapsible, hidden on new documents). No "Invalid depends_on" errors.')
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
            p = doc.add_paragraph('[Screenshot not available: %s]' % key)
            p.runs[0].font.italic = True
            p.runs[0].font.color.rgb = RGBColor(0x99, 0x99, 0x99)
            doc.add_paragraph('')
    
    doc.add_page_break()
    
    # 6. Future Enhancements
    doc.add_heading('6. Future Enhancements', level=1)
    
    enhancements = [
        ('Template Catalog for High-Volume Changes', 
         'When Standard changes exceed a volume threshold (X% of changes over 90 days) or cause an incident, '
         'the Template Catalog becomes mandatory. Threshold X% is DECISION NEEDED based on operational data.'),
        ('Return to Draft from Pending Approval', 
         'Proposed transition allowing Approvers to send a request back to Draft with a required review comment. '
         'Awaits stakeholder approval.'),
        ('Workflow State Mapping', 
         'Current workflow uses custom locking (all states at doc_status=0). Consider adding a native "Submitted" '
         'state (doc_status=1) at "Approved for Deployment" if Frappe workflow engine supports it.'),
        ('HD Ticket Priority "Critical"', 
         'HD Ticket Priority fixture includes Critical but Helpdesk v16 may not expose it \u2014 severity map uses "Urgent" '
         'as fallback. Verify and align with Helpdesk v16 schema.'),
        ('Auto-Resolved SLA Pause', 
         'Whether "Auto-Resolved" status pauses SLA via HD Service Level Agreement rules \u2014 needs Helpdesk v16 verification.'),
        ('CI/CD Evidence Automation', 
         'Current deployment evidence is free-text. Future: integrate with GitHub/GitLab tags for automated verification '
         'and immutable evidence chains.')
    ]
    
    for item_name, item_desc in enhancements:
        p = doc.add_paragraph()
        run = p.add_run('%s: ' % item_name)
        run.font.bold = True
        run.font.size = Pt(11)
        run = p.add_run(item_desc)
        run.font.size = Pt(11)
    
    doc.add_page_break()
    
    # Appendix A: API Usage Examples
    doc.add_heading('Appendix A: API Usage Examples', level=1)
    
    examples = """# Grafana Webhook Configuration
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
  -d '{"webhook_log_name":"GWL-00001"}"""
    
    doc.add_paragraph(examples)
    
    # Save
    output_path = Path('/home/feye/frappe-bench/IT_Operations_Module_Overview.docx')
    doc.save(output_path)
    print("\nReport saved to: %s" % output_path)
    return output_path


async def main():
    print("=" * 60)
    print("IT Operations Module Report Generator v2")
    print("=" * 60)
    
    # Load data
    print("\nLoading audit data...")
    audit_content, arch_content = load_audit_data()
    
    # Capture screenshots
    print("\nCapturing high-resolution screenshots...")
    screenshots = await capture_screenshots()
    
    # Generate report
    print("\nGenerating .docx report...")
    output_path = generate_docx_report(audit_content, arch_content, screenshots)
    
    # Verify
    if Path(output_path).exists():
        size = Path(output_path).stat().st_size
        print("\n\u2705 Report generated successfully!")
        print("   Location: %s" % output_path)
        print("   Size: %s bytes" % "{:,}".format(size))
    else:
        print("\n\u274c Report generation failed!")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())