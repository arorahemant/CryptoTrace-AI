"""
CryptoTrace AI — Comprehensive P0 Validation Suite
Tests the FULL investigator journey end-to-end:
  1. Login
  2. Create Case
  3. Run Investigation
  4. Validate all data endpoints
  5. WHY, AI, Replay, Report
  6. Graph data quality assertions
"""
import httpx
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0
RESULTS = []


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        RESULTS.append(("PASS", name, detail))
        print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL += 1
        RESULTS.append(("FAIL", name, detail))
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("CryptoTrace AI — P0 Full Validation")
print("=" * 60)

# ─── 1. HEALTH CHECK ──────────────────────────────────────
print("\n--- 1. Health Check ---")
try:
    r = httpx.get(f"{BASE}/api/v1/health", timeout=5)
    check("Health endpoint", r.status_code == 200, f"status={r.status_code}")
except Exception as e:
    check("Health endpoint", False, str(e))

# ─── 2. LOGIN ─────────────────────────────────────────────
print("\n--- 2. Authentication ---")
r = httpx.post(f"{BASE}/api/v1/auth/login", json={"username": "investigator", "password": "investigate123"})
check("Login returns 200", r.status_code == 200, f"status={r.status_code}")
login_data = r.json()
check("Login returns access_token", "access_token" in login_data)
check("Login returns user object", "user" in login_data)
token = login_data.get("access_token", "")
headers = {"Authorization": f"Bearer {token}"}

# Bad login
r2 = httpx.post(f"{BASE}/api/v1/auth/login", json={"username": "wrong", "password": "wrongpass"})
check("Bad login returns 401", r2.status_code == 401, f"status={r2.status_code}")

# ─── 3. CREATE CASE ──────────────────────────────────────
print("\n--- 3. Case Creation ---")
case_payload = {
    "title": "P0 Test — Full Validation",
    "reported_wallet": "0xReported001",
    "blockchain": "demo",
    "description": "Automated P0 validation test case",
    "reported_amount": 12500.0,
}
r = httpx.post(f"{BASE}/api/v1/cases", json=case_payload, headers=headers)
check("Create case returns 200", r.status_code == 200, f"status={r.status_code}")
case_data = r.json()
case_id = case_data.get("id", "")
check("Case has UUID id", len(case_id) == 36, case_id)
check("Case has case_number", bool(case_data.get("case_number")), case_data.get("case_number", ""))
check("Case status is 'new'", case_data.get("status") == "new")
check("Case wallet matches input", case_data.get("reported_wallet") == "0xReported001")
check("Case is_demo=True", case_data.get("is_demo") == True)

# ─── 4. GET CASE DETAIL ─────────────────────────────────
print("\n--- 4. Case Detail (Pre-Investigation) ---")
r = httpx.get(f"{BASE}/api/v1/cases/{case_id}", headers=headers)
check("Get case returns 200", r.status_code == 200)
detail = r.json()
check("Case detail has summary", "summary" in detail)
check("Pre-investigation wallets = 0", detail["summary"]["total_wallets"] == 0)
check("Pre-investigation transactions = 0", detail["summary"]["total_transactions"] == 0)

# ─── 5. RUN INVESTIGATION ───────────────────────────────
print("\n--- 5. Investigation Execution ---")
r = httpx.post(f"{BASE}/api/v1/cases/{case_id}/investigate", json={}, headers=headers, timeout=30)
check("Investigate returns 200", r.status_code == 200, f"status={r.status_code}")
inv_data = r.json()
check("Investigation returns case_id", inv_data.get("case_id") == case_id)

# Stats
stats = inv_data.get("stats", {})
check("Stats: traced_transactions > 0", stats.get("traced_transactions", 0) > 0, f"{stats.get('traced_transactions')}")
check("Stats: discovered_wallets > 0", stats.get("discovered_wallets", 0) > 0, f"{stats.get('discovered_wallets')}")
check("Stats: findings > 0", stats.get("findings", 0) > 0, f"{stats.get('findings')}")
check("Stats: hops_completed > 0", stats.get("hops_completed", 0) > 0, f"{stats.get('hops_completed')}")

# Graph in response
graph = inv_data.get("graph", {})
check("Graph has nodes", len(graph.get("nodes", [])) > 0, f"{len(graph.get('nodes', []))} nodes")
check("Graph has edges", len(graph.get("edges", [])) > 0, f"{len(graph.get('edges', []))} edges")
check("Graph has primary_path", len(graph.get("primary_path", [])) > 0, f"path len={len(graph.get('primary_path', []))}")

# Risk
risk = inv_data.get("risk", {})
check("Risk has overall category", risk.get("overall") in ["low", "medium", "high", "critical"], risk.get("overall"))
check("Risk has by_wallet data", len(risk.get("by_wallet", {})) > 0)

# ─── 6. POST-INVESTIGATION DATA ENDPOINTS ───────────────
print("\n--- 6. Data Endpoints (Post-Investigation) ---")

# Case detail now has data
r = httpx.get(f"{BASE}/api/v1/cases/{case_id}", headers=headers)
detail = r.json()
check("Post-inv wallets > 0", detail["summary"]["total_wallets"] > 0, f"{detail['summary']['total_wallets']}")
check("Post-inv transactions > 0", detail["summary"]["total_transactions"] > 0, f"{detail['summary']['total_transactions']}")
check("Post-inv findings > 0", detail["summary"]["total_findings"] > 0, f"{detail['summary']['total_findings']}")
check("Post-inv evidence > 0", detail["summary"]["total_evidence"] > 0, f"{detail['summary']['total_evidence']}")

# Wallets
r = httpx.get(f"{BASE}/api/v1/cases/{case_id}/wallets", headers=headers)
check("Wallets endpoint 200", r.status_code == 200)
wallets = r.json().get("wallets", [])
check("Wallets count > 0", len(wallets) > 0, f"{len(wallets)}")
reported = [w for w in wallets if w.get("is_reported")]
check("Exactly 1 reported wallet", len(reported) == 1)
check("Reported wallet = 0xReported001", reported[0]["address"] == "0xReported001" if reported else False)

# Transactions
r = httpx.get(f"{BASE}/api/v1/cases/{case_id}/transactions", headers=headers)
check("Transactions endpoint 200", r.status_code == 200)
txs = r.json().get("transactions", [])
check("Transactions count > 0", len(txs) > 0, f"{len(txs)}")
# Check each tx has required fields
if txs:
    tx = txs[0]
    check("TX has hash", bool(tx.get("hash")))
    check("TX has from_address", bool(tx.get("from_address")))
    check("TX has to_address", bool(tx.get("to_address")))
    check("TX has amount > 0", (tx.get("amount") or 0) > 0)
    check("TX has hop_number", tx.get("hop_number") is not None)

# Findings
r = httpx.get(f"{BASE}/api/v1/cases/{case_id}/findings", headers=headers)
check("Findings endpoint 200", r.status_code == 200)
findings = r.json().get("findings", [])
check("Findings count > 0", len(findings) > 0, f"{len(findings)}")
if findings:
    f = findings[0]
    check("Finding has pattern_name", bool(f.get("pattern_name")))
    check("Finding has description", bool(f.get("description")))
    check("Finding has severity", f.get("severity") in ["low", "medium", "high", "critical"])
    check("Finding has confidence (0-1)", 0 <= (f.get("confidence") or 0) <= 1)

# Evidence
r = httpx.get(f"{BASE}/api/v1/cases/{case_id}/evidence", headers=headers)
check("Evidence endpoint 200", r.status_code == 200)
evidence = r.json().get("evidence", [])
check("Evidence count > 0", len(evidence) > 0, f"{len(evidence)}")

# Timeline
r = httpx.get(f"{BASE}/api/v1/cases/{case_id}/timeline", headers=headers)
check("Timeline endpoint 200", r.status_code == 200)
timeline = r.json().get("events", [])
check("Timeline events > 0", len(timeline) > 0, f"{len(timeline)}")

# Fund Flow
r = httpx.get(f"{BASE}/api/v1/cases/{case_id}/fund-flow", headers=headers)
check("Fund flow endpoint 200", r.status_code == 200)
flows = r.json().get("fund_flows", [])
check("Fund flows > 0", len(flows) > 0, f"{len(flows)}")

# ─── 7. GRAPH ENDPOINT ──────────────────────────────────
print("\n--- 7. Graph Endpoint ---")
r = httpx.get(f"{BASE}/api/v1/cases/{case_id}/graph", headers=headers)
check("Graph endpoint 200", r.status_code == 200)
graph_ep = r.json()
g_nodes = graph_ep.get("nodes", [])
g_edges = graph_ep.get("edges", [])
check("Graph nodes > 0", len(g_nodes) > 0, f"{len(g_nodes)} nodes")
check("Graph edges > 0", len(g_edges) > 0, f"{len(g_edges)} edges")
if g_nodes:
    n = g_nodes[0]
    check("Node has address", bool(n.get("address")))
    check("Node has hop_distance", n.get("hop_distance") is not None)
    check("Graph carries risk score context", any(node.get("risk_score") is not None for node in g_nodes))
    check("Graph carries attribution context", any(node.get("vasp_name") and node.get("vasp_confidence") and node.get("vasp_source") for node in g_nodes))
if g_edges:
    e = g_edges[0]
    check("Edge has source", bool(e.get("source")))
    check("Edge has target", bool(e.get("target")))
    check("Edge has amount", e.get("amount") is not None)

# ─── 8. WHY ENDPOINT ────────────────────────────────────
print("\n--- 8. WHY (Explainability) ---")
# Pick an intermediary wallet from wallets
intermediaries = [w for w in wallets if w.get("is_intermediary")]
if intermediaries:
    test_wallet = intermediaries[0]["address"]
else:
    test_wallet = wallets[1]["address"] if len(wallets) > 1 else wallets[0]["address"]

r = httpx.get(f"{BASE}/api/v1/cases/{case_id}/why/{test_wallet}", headers=headers)
check("WHY endpoint 200", r.status_code == 200, f"wallet={test_wallet[:20]}")
why = r.json()
check("WHY has wallet_address", why.get("wallet_address") == test_wallet)
check("WHY has reasons[]", len(why.get("reasons", [])) > 0, f"{len(why.get('reasons', []))} reasons")

# ─── 9. AI COPILOT ──────────────────────────────────────
print("\n--- 9. AI Copilot ---")
r = httpx.post(f"{BASE}/api/v1/cases/{case_id}/ai/query",
    json={"question": "Where did the money go?"}, headers=headers, timeout=15)
check("AI query 200", r.status_code == 200)
ai = r.json()
check("AI has answer", len(ai.get("answer", "")) > 10, f"len={len(ai.get('answer', ''))}")
check("AI answer is grounded", ai.get("grounded") == True)
check("AI has sources", len(ai.get("sources", [])) > 0)
check("AI has suggested_questions", len(ai.get("suggested_questions", [])) > 0)

# ─── 10. REPLAY ─────────────────────────────────────────
print("\n--- 10. Replay ---")
r = httpx.post(f"{BASE}/api/v1/cases/{case_id}/replay", headers=headers, timeout=15)
check("Replay endpoint 200", r.status_code == 200)
replay = r.json()
check("Replay has events > 0", len(replay.get("events", [])) > 0, f"{len(replay.get('events', []))} events")
if replay.get("events"):
    ev = replay["events"][0]
    replay_events = replay["events"]
    check("Replay event has title", bool(ev.get("title")))
    check("Replay event has description", bool(ev.get("description")))
    check("Replay event has event_id", bool(ev.get("event_id")))
    check("Replay event has step order", [item.get("step") for item in replay_events] == list(range(1, len(replay_events) + 1)))
    check("Replay events map to traced transactions", all(item.get("transaction_hash") in {tx.get("hash") for tx in txs} for item in replay_events))
    check("Replay event has timestamp", all(item.get("timestamp") for item in replay_events))
    check("Replay event has highlight_nodes", "highlight_nodes" in ev)
    check("Replay event has highlight_edges", "highlight_edges" in ev)
    check("Replay event highlights a graph edge", any(item.get("highlight_edges") for item in replay_events))

# ─── 11. REPORT ─────────────────────────────────────────
print("\n--- 11. Report Generation ---")
r = httpx.post(f"{BASE}/api/v1/cases/{case_id}/report", headers=headers, timeout=15)
check("Report generation 200", r.status_code == 200)
report = r.json()
check("Report has title", bool(report.get("title")))
sections = report.get("sections", [])
check("Report has sections > 0", len(sections) > 0, f"{len(sections)} sections")

# Check section types
section_types = {s.get("section_type") for s in sections}
check("Report has FACT section", "fact" in section_types)
check("Report has ANALYSIS section", "analysis" in section_types)

# Get report endpoint
r = httpx.get(f"{BASE}/api/v1/cases/{case_id}/report", headers=headers)
check("Get report 200", r.status_code == 200)

# ─── 12. LIST CASES (verify case appears) ───────────────
print("\n--- 12. Case Listing ---")
r = httpx.get(f"{BASE}/api/v1/cases", headers=headers)
check("List cases 200", r.status_code == 200)
all_cases = r.json().get("cases", [])
our_case = [c for c in all_cases if c.get("id") == case_id]
check("Our case appears in listing", len(our_case) == 1)

# ─── SUMMARY ────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"TOTAL: {PASS + FAIL} | PASS: {PASS} | FAIL: {FAIL}")
if FAIL > 0:
    print("\nFAILED TESTS:")
    for status, name, detail in RESULTS:
        if status == "FAIL":
            print(f"  ✗ {name}: {detail}")
print("=" * 60)

if FAIL > 0:
    print("P0 validation failed")
else:
    print("✅ ALL P0 TESTS PASSED")


def test_p0_full_validation():
    """Keep the executable validation suite visible to pytest as one test."""
    assert FAIL == 0, "P0 validation reported failures: " + "; ".join(
        f"{name}: {detail}" for status, name, detail in RESULTS if status == "FAIL"
    )


if __name__ == "__main__":
    sys.exit(1 if FAIL > 0 else 0)
