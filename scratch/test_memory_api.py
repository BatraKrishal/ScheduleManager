import httpx

client = httpx.Client(base_url="http://localhost:8000")
proj_id = "d2c363c7-dbe1-4bab-95e2-c96ca02da053"

sum_res = client.get(f"/api/v1/projects/{proj_id}/institutional-memory/summary").json()
print("=== 1. SUMMARY ===")
print("Verified events:", sum_res.get("verified_event_count"))
print("Ledger entries:", sum_res.get("ledger_entry_count"))
print("Completed activities:", sum_res.get("completed_activity_count"))
print("Total quantity by unit:", sum_res.get("total_quantity_by_unit"))
print("Avg actual duration:", sum_res.get("average_actual_duration"), "days")

prod_res = client.get(f"/api/v1/projects/{proj_id}/institutional-memory/productivity").json()
print("\n=== 2. PRODUCTIVITY ===")
for p in prod_res:
    print(f"- {p.get('discipline')}: {p.get('rate')} {p.get('unit')} across {p.get('reporting_days')} day(s) ({p.get('sample_count')} sample, {len(p.get('evidence', []))} evidence rows)")

dur_res = client.get(f"/api/v1/projects/{proj_id}/institutional-memory/durations").json()
print("\n=== 3. DURATIONS ===")
print("Completed activities:", dur_res.get("activities_completed"))
print("Avg planned duration:", dur_res.get("average_planned_duration"), "days")
print("Avg actual duration:", dur_res.get("average_actual_duration"), "days")
print("Avg variance:", dur_res.get("average_variance_days"), "days")
print("On-time count:", dur_res.get("on_time_count"))
print("Delayed count:", dur_res.get("delayed_count"))

query_res = client.post(
    f"/api/v1/projects/{proj_id}/institutional-memory/query",
    json={"query_type": "PRODUCTIVITY", "discipline": "Civil"},
).json()
print("\n=== 4. HISTORICAL QUERY ===")
print("Status:", query_res.get("data_status"))
print("Summary:", query_res.get("summary"))
print("Evidence attached:", len(query_res.get("evidence", [])))

ledger_res = client.get(f"/api/v1/projects/{proj_id}/institutional-memory/ledger?page=1&page_size=3").json()
print("\n=== 5. LEDGER (First 3 entries) ===")
print("Total ledger records:", ledger_res.get("total"))
for it in ledger_res.get("items", []):
    print(f"- Activity: {it['activity_code']} ({it['activity_name']}) | Date: {it['reporting_date']} | Incr: +{it['incremental_percent']}% | Cumul: {it['cumulative_percent']}% | Qty: {it['installed_quantity']} {it['unit_of_measure']}")
