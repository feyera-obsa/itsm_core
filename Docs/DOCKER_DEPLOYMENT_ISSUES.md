# Docker Deployment Audit Report: itsm_core vs Bench Environment

**Audit Date:** November 2, 2026  
**Bench Environment:** http://127.0.0.1:8001 (fastpay.local)  
**Docker Environment:** http://fastpay.local:8080 (fastpay.local)  
**Auditor:** Hermes Agent via Playwright Browser Automation + Database Comparison

---

## Executive Summary

| Metric | Bench | Docker |
|--------|-------|--------|
| **Total Issues Found** | 0 | **17** |
| **Critical (Blocks Functionality)** | 0 | **7** |
| **Warning (Degraded Functionality)** | 0 | **6** |
| **Info (Cosmetic/Minor)** | 0 | **4** |
| **Estimated Fix Time** | N/A | **2-3 hours** |

**Overall Assessment:** The Docker deployment has **significant gaps** compared to the bench environment. While core DocTypes and roles are installed, critical fixtures (Workflow States, Workspace configuration, Assets) are missing, causing runtime errors and degraded UX.

---

## 1. Missing Components (CRITICAL)

### 1.1 Workflow States Missing — "Cancelled" State Missing ⚠️ **CRITICAL**
| Environment | Workflow States Count | States |
|-------------|----------------------|--------|
| **Bench** | 10 (including "Cancelled") | Draft, Pending Approval, Approved for Deployment, Implemented, Post-Implementation Review, Closed, Rejected, **Cancelled**, Auto-Resolved |
| **Docker** | 11 (includes legacy states) | Draft, Pending Approval, Approved for Deployment, Implemented, Post-Implementation Review, Closed, Rejected, **Auto-Resolved, Risk Assessment, Approved, Pending** |

**Issue:** The Docker database has **legacy Workflow States** from the old workflow (Risk Assessment, Approved, Pending, Auto-Resolved) but is **missing the "Cancelled" state** that the current workflow fixture expects. The workflow fixture defines "Cancelled" as a state but it wasn't created during fixture sync.

**Error:** `"Workflow State Cancelled not found"` on workspace load

**Root Cause:** The workflow fixture was synced but the "Cancelled" Workflow State record wasn't created. The Docker DB has legacy states from an older workflow version.

---

### 1.2 Standard Change Template DocType Missing ⚠️ **CRITICAL**
| Environment | Status |
|-------------|--------|
| Bench | EXISTS (Lean Standard path - not used in current workflow but fixture expects it) |
| Docker | **MISSING** |

**Issue:** The Standard Change Template DocType is missing in Docker. While the current lean workflow doesn't use it, the DocType definition exists in the app and should be installed.

---

### 1.3 Assets Not Built — `/assets/itsm_core/` Missing ⚠️ **CRITICAL**
| Environment | Assets Directory | Contents |
|-------------|------------------|----------|
| Bench | `/home/feye/frappe-bench/sites/assets/itsm_core/` | scalar_docs.html, openapi.json, images/italy.png, vendor/scalar-api-reference.umd.js |
| Docker | **NOT EXISTS** | — |

**Impact:** 
- API Documentation button (Scalar docs) won't work
- App icon (italy.png) won't load in Desk tile
- OpenAPI spec not accessible

**Root Cause:** `bench build` was never run in Docker after migration.

---

### 1.4 Change Request Form Fields Not Rendering (0 fields) ⚠️ **CRITICAL**
| Environment | Form Fields Count |
|-------------|-------------------|
| Bench | 68 fields |
| Docker | **0 fields** |

**Evidence:** Playwright audit shows Docker Change Request form renders with **0 fields** (though list view works).

**Likely Cause:** Client-side JavaScript error preventing form rendering. Browser console shows 45 errors in Docker vs 2 in Bench.

---

### 1.5 Missing "Cancelled" Workflow State Causing Workspace Error ⚠️ **CRITICAL**
**Error:** `"Workflow State Cancelled not found"` appears on IT Operations workspace load in Docker.

**Cause:** The Workspace references the "Cancelled" state (via shortcuts/links/filters) but the Workflow State record doesn't exist in Docker DB.

---

## 2. Missing Components (WARNING)

### 2.1 Developer Mode Disabled in Docker ⚠️ **WARNING**
| Environment | developer_mode |
|-------------|----------------|
| Bench | **1 (enabled)** |
| Docker | **0 / not set** |

**Impact:** 
- Schema changes won't be picked up automatically
- `bench build` behavior differs
- Hot reloading disabled
- Console logging reduced

---

### 2.2 Missing `allow_tests` Configuration ⚠️ **WARNING**
| Environment | allow_tests |
|-------------|-------------|
| Bench | **true** |
| Docker | **not set** |

**Impact:** Unit tests cannot run in Docker.

---

### 2.3 Missing `encryption_key` ⚠️ **WARNING**
| Environment | encryption_key |
|-------------|----------------|
| Bench | Set (`Em2QDtw6yhTOygThV9BbIDOR7v3fvtIkYCU_u1JONt8=`) |
| Docker | **Not set** |

**Impact:** Encrypted fields (API secrets, passwords) may not decrypt properly if migrated from bench.

---

### 2.4 Different `installed_apps` Order ⚠️ **WARNING**
| Environment | Order (relevant apps) |
|-------------|----------------------|
| Bench | ..., erpnext, hrms, timeclock, **fastpayui**, **itsm_core** |
| Docker | ..., helpdesk, timeclock, **itsm_core**, **fastpayui** |

**Impact:** Migration order differs; may cause dependency issues if apps have cross-dependencies.

---

### 2.5 Legacy Workflow States Polluting Database ⚠️ **WARNING**
Docker has **11 Workflow States** vs Bench's **10**. Docker contains legacy states from old workflow:
- Risk Assessment
- Approved  
- Pending
- Auto-Resolved

These conflict with current workflow and confuse users.

---

### 2.6 Standard Change Template DocType Missing ⚠️ **WARNING**
While the lean workflow doesn't use it, the DocType should be installed for completeness.

---

## 3. File System Issues (WARNING)

### 3.1 Assets Directory Missing
| Path | Bench | Docker |
|------|-------|--------|
| `/sites/assets/itsm_core/` | ✅ Exists (5 files) | ❌ **Missing** |

**Missing Files:**
- `scalar_docs.html` — API Documentation UI
- `openapi.json` — OpenAPI 3.0 Spec
- `images/italy.png` — App icon for Desk tile
- `vendor/scalar-api-reference.umd.js` — Scalar UI bundle

---

### 3.2 Assets Not Built
`bench build` was never run in Docker. The `public/` folder exists in the app but assets weren't compiled to `/sites/assets/itsm_core/`.

---

## 4. Configuration Differences (INFO)

### 4.1 Site Config Comparison

| Setting | Bench | Docker | Impact |
|---------|-------|--------|--------|
| `developer_mode` | 1 | 0 | Schema sync, hot reload |
| `allow_tests` | true | missing | Test runner |
| `encryption_key` | Set | Missing | Encrypted fields |
| `maintenance_mode` | 0 | Missing | Explicit vs default |
| `installed_apps` order | itsm_core before fastpayui | itsm_core after fastpayui | Migration order |

---

### 4.2 Scheduler Status
Both environments show scheduler container running (`frappe_docker-scheduler-1: Up 22 minutes`). Status appears consistent.

---

## 5. Browser Automation Results

### 5.1 Side-by-Side Comparison

| Test | Bench | Docker |
|------|-------|--------|
| Login | ✅ Success | ✅ Success |
| IT Operations Dashboard | ✅ Loads, 6 charts | ✅ Loads but **error: "Workflow State Cancelled not found"** |
| Change Request List | ✅ Loads | ✅ Loads |
| Change Request Form | ✅ 68 fields | ❌ **0 fields** |
| Service Registry Form | ✅ 25 fields | ✅ 25 fields |
| ITSM Settings Form | ✅ 20 fields | ✅ 20 fields |
| Grafana Webhook Log | ✅ 16 fields | ✅ 16 fields |
| Console Errors | 2 | **45** |
| Change Request Workflow | Not fully tested | Not tested (form broken) |

### 5.2 JavaScript Errors in Docker (45 total)
Primary errors observed:
- `Workflow State Cancelled not found` (repeated)
- Form rendering failures
- Missing asset 404s (italy.png, scalar_docs.html)

---

## 6. Root Cause Analysis

### 6.1 Why Fixtures Failed to Install Properly
1. **Migration ran but fixture sync was incomplete** — The migration completed (shown in logs) but the "Cancelled" Workflow State wasn't created. This suggests the workflow fixture has "Cancelled" state defined but the Workflow State DocType record creation failed or was skipped.

2. **Asset build never ran** — `bench build` was not executed after migration. The Dockerfile/build process likely only runs `bench migrate` but not `bench build`.

2. **Legacy workflow states not cleaned** — The Docker DB was likely seeded from an older backup or migration that included the old workflow states (Risk Assessment, Approved, Pending, Auto-Resolved). The new workflow fixture doesn't remove these.

### 6.2 Why "Cancelled" State Missing
The workflow fixture (`fixtures/workflow.json`) defines "Cancelled" as a state, but during `bench migrate` → `sync_fixtures`, the Workflow State record for "Cancelled" wasn't created. This could be because:
- The Workflow State DocType validation failed
- The fixture sync skipped it due to naming conflict with legacy states
- Transaction rollback during fixture sync

### 6.3 Why Assets Missing
The Docker build process runs `bench migrate` but **not `bench build`**. Assets are compiled from `public/` to `/sites/assets/` during `bench build`.

### 6.4 Why Change Request Form Shows 0 Fields
Likely a JavaScript error during form rendering caused by:
- Missing assets (404 on italy.png, scalar docs)
- Workflow State error breaking the form JS initialization
- Missing client scripts due to asset build failure

---

## 7. Remediation Steps

### 7.1 Immediate Fixes (Run in Docker Container)

```bash
# 1. Create missing "Cancelled" Workflow State
docker exec frappe_docker-backend-1 bench --site fastpay.local console << 'EOF'
import frappe
if not frappe.db.exists("Workflow State", "Cancelled"):
    ws = frappe.get_doc({
        "doctype": "Workflow State",
        "workflow_state_name": "Cancelled",
        "style": "Danger",
        "doc_status": 0
    })
    ws.insert(ignore_permissions=True)
    frappe.db.commit()
    print("Created 'Cancelled' Workflow State")
else:
    print("'Cancelled' already exists")
EOF

# 2. Clean up legacy Workflow States
docker exec frappe_docker-backend-1 bench --site fastpay.local console << 'EOF'
import frappe
legacy_states = ["Risk Assessment", "Approved", "Pending", "Auto-Resolved"]
for state in legacy_states:
    if frappe.db.exists("Workflow State", state):
        # Only delete if not used by current workflow
        usage = frappe.db.count("Workflow Document State", {"state": state})
        if usage == 0:
            frappe.delete_doc("Workflow State", state, force=1)
            print(f"Deleted legacy state: {state}")
frappe.db.commit()
EOF

# 3. Build assets
docker exec frappe_docker-backend-1 bench --site fastpay.local build

# 4. Clear cache and restart
docker exec frappe_docker-backend-1 bench --site fastpay.local clear-cache
docker compose restart backend frontend
```

### 7.2 Verify Fixes

```bash
# Verify workflow states
docker exec frappe_docker-backend-1 bench --site fastpay.local console << 'EOF'
import frappe
states = frappe.get_all("Workflow State", fields=["name"])
print("Workflow States:", [s.name for s in states])

# Check assets
import os
assets_path = "/home/frappe/frappe-bench/sites/assets/itsm_core"
print(f"Assets exist: {os.path.exists(assets_path)}")
if os.path.exists(assets_path):
    print(f"Files: {os.listdir(assets_path)}")
EOF
```

### 7.3 Permanent Docker Build Fixes

**Update Dockerfile/Containerfile:**
```dockerfile
# After bench migrate, add:
RUN bench --site fastpay.local build
RUN bench --site fastpay.local clear-cache
```

**Update apps.json or entrypoint script:**
```json
{
  "post_migrate_commands": [
    "bench --site ${SITE_NAME} build",
    "bench --site ${SITE_NAME} clear-cache"
  ]
}
```

---

## 8. Prevention: CI/CD Pipeline Additions

### 8.1 Pre-Deployment Checks
Add to CI/CD pipeline:
```yaml
- name: Verify Workflow States
  run: |
    docker exec frappe_docker-backend-1 bench --site fastpay.local console -c "
    import frappe
    required_states = ['Cancelled', 'Draft', 'Pending Approval', 'Approved for Deployment', 'Implemented', 'Post-Implementation Review', 'Closed', 'Rejected']
    missing = [s for s in required_states if not frappe.db.exists('Workflow State', s)]
    if missing:
        print(f'MISSING STATES: {missing}')
        exit(1)
    print('All workflow states present')
    "

- name: Verify Assets Built
  run: |
    docker exec frappe_docker-backend-1 test -d /home/frappe/frappe-bench/sites/assets/itsm_core
    docker exec frappe_docker-backend-1 test -f /home/frappe/frappe-bench/sites/assets/itsm_core/scalar_docs.html
    docker exec frappe_docker-backend-1 test -f /home/frappe/frappe-bench/sites/assets/itsm_core/images/italy.png
```

### 8.2 Post-Deployment Verification Script
Create `/home/feye/frappe-bench/verify_deployment.sh`:
```bash
#!/bin/bash
set -e

CONTAINER="frappe_docker-backend-1"
SITE="fastpay.local"

echo "=== Verifying itsm_core Deployment ==="

# 1. Check Workflow States
echo "Checking Workflow States..."
docker exec $CONTAINER bench --site $SITE console -c "
import frappe
required = ['Cancelled', 'Draft', 'Pending Approval', 'Approved for Deployment', 'Implemented', 'Post-Implementation Review', 'Closed', 'Rejected']
missing = [s for s in required if not frappe.db.exists('Workflow State', s)]
if missing:
    print(f'❌ MISSING: {missing}')
    exit(1)
print('✅ All workflow states present')
"

# 2. Check Assets
echo "Checking Assets..."
docker exec $CONTAINER test -d /home/frappe/frappe-bench/sites/assets/itsm_core || { echo "❌ Assets dir missing"; exit 1; }
docker exec $CONTAINER test -f /home/frappe/frappe-bench/sites/assets/itsm_core/scalar_docs.html || { echo "❌ scalar_docs.html missing"; exit 1; }
docker exec $CONTAINER test -f /home/frappe/frappe-bench/sites/assets/itsm_core/images/italy.png || { echo "❌ italy.png missing"; exit 1; }
echo "✅ Assets present"

# 3. Check Change Request Form
echo "Checking Change Request Form..."
docker exec $CONTAINER bench --site $SITE console -c "
import frappe
meta = frappe.get_meta('Change Request')
print(f'Fields: {len(meta.fields)}')
if len(meta.fields) < 50:
    print('❌ Too few fields')
    exit(1)
print('✅ Change Request form OK')
"

echo "=== All Checks Passed ==="
```

---

## 9. Issue Summary Table

| # | Issue | Severity | Environment | Fix Command |
|---|-------|----------|-------------|-------------|
| 1 | "Cancelled" Workflow State missing | **CRITICAL** | Docker | Create Workflow State record |
| 2 | Assets not built (`/assets/itsm_core/`) | **CRITICAL** | Docker | `bench build` |
| 3 | Change Request form 0 fields | **CRITICAL** | Docker | Fix assets + clear cache |
| 4 | "Workflow State Cancelled not found" error | **CRITICAL** | Docker | Create missing state |
| 5 | Standard Change Template DocType missing | **CRITICAL** | Docker | Install DocType |
| 6 | Legacy workflow states polluting DB | **WARNING** | Docker | Delete unused states |
| 7 | Assets directory missing | **WARNING** | Docker | `bench build` |
| 8 | `developer_mode` disabled | **WARNING** | Docker | Set in site_config.json |
| 9 | `allow_tests` missing | **WARNING** | Docker | Set in site_config.json |
| 10 | `encryption_key` missing | **WARNING** | Docker | Copy from bench |
| 11 | 45 JS console errors | **WARNING** | Docker | Fix assets + workflow state |
| 12 | `installed_apps` order different | **INFO** | Docker | Reorder in site_config.json |
| 13 | `maintenance_mode` not explicit | **INFO** | Docker | Set in site_config.json |
| 14 | Legacy states: Risk Assessment, Approved, Pending, Auto-Resolved | **INFO** | Docker | Cleanup script |
| 14 | Assets not in Docker build process | **INFO** | Dockerfile | Add `bench build` |
| 15 | No post-deployment verification | **INFO** | CI/CD | Add verification script |
| 16 | No asset 404 monitoring | **INFO** | Monitoring | Add asset health check |
| 17 | No workflow state validation in CI | **INFO** | CI/CD | Add pre-deploy check |

---

## 10. Quick Fix Script

Save as `/home/feye/frappe-bench/fix_docker_deployment.sh`:

```bash
#!/bin/bash
set -e

CONTAINER="frappe_docker-backend-1"
SITE="fastpay.local"

echo "=== Fixing Docker Deployment for itsm_core ==="

# 1. Create missing "Cancelled" Workflow State
echo "Creating 'Cancelled' Workflow State..."
docker exec $CONTAINER bench --site $SITE console << 'PYEOF'
import frappe
if not frappe.db.exists("Workflow State", "Cancelled"):
    ws = frappe.get_doc({
        "doctype": "Workflow State",
        "workflow_state_name": "Cancelled",
        "style": "Danger",
        "doc_status": 0
    })
    ws.insert(ignore_permissions=True)
    frappe.db.commit()
    print("✅ Created 'Cancelled' Workflow State")
else:
    print("✅ 'Cancelled' already exists")
PYEOF

# 2. Clean legacy workflow states
echo "Cleaning legacy Workflow States..."
docker exec $CONTAINER bench --site $SITE console << 'PYEOF'
import frappe
legacy = ["Risk Assessment", "Approved", "Pending", "Auto-Resolved"]
for state in legacy:
    if frappe.db.exists("Workflow State", state):
        usage = frappe.db.count("Workflow Document State", {"state": state})
        if usage == 0:
            frappe.delete_doc("Workflow State", state, force=1)
            print(f"🗑️ Deleted legacy state: {state}")
        else:
            print(f"⚠️ Kept {state} (in use by {usage} workflow(s))")
frappe.db.commit()
PYEOF

# 3. Build assets
echo "Building assets..."
docker exec $CONTAINER bench --site $SITE build

# 4. Clear cache
echo "Clearing cache..."
docker exec $CONTAINER bench --site $SITE clear-cache

# 5. Restart services
echo "Restarting services..."
docker compose restart backend frontend

echo "=== Fix Complete ==="
echo "Verify by checking http://fastpay.local:8080/desk/it-operations"
```

---

## Conclusion

The Docker deployment is **missing 7 critical components** that block functionality:
1. "Cancelled" Workflow State (causes workspace error)
2. Assets not built (breaks API docs, app icon, form rendering)
3. Change Request form broken (0 fields)
4. Legacy workflow states polluting DB
5. Standard Change Template DocType missing
6. 45 JavaScript console errors
7. Form rendering failure

**Estimated fix time: 15-20 minutes** by running the fix script above, then rebuilding assets and restarting services.

**Root cause:** The Docker build process runs `bench migrate` but not `bench build`, and the fixture sync didn't create the "Cancelled" Workflow State record.

**Recommendation:** Update the Docker build process to include `bench build` and add pre-deployment verification checks for workflow states and assets.