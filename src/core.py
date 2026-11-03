"""Core database, deterministic synthetic data, underwriting rules, and validation."""
from __future__ import annotations

import csv
import hashlib
import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

DEFAULT_SEED = 20261022
PRODUCTS = [
    ("PRD-MOTOR", "Motor Insurance", 0.010, 50_000, 5_000_000, 18, 30),
    ("PRD-HOME", "Home Insurance", 0.003, 100_000, 25_000_000, 18, 50),
    ("PRD-COMM", "Commercial Property", 0.006, 250_000, 100_000_000, 21, 65),
]

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS applicants (
 applicant_id TEXT PRIMARY KEY, full_name TEXT NOT NULL, age INTEGER NOT NULL CHECK(age BETWEEN 18 AND 100),
 region TEXT NOT NULL, occupation TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS insured_assets (
 asset_id TEXT PRIMARY KEY, applicant_id TEXT NOT NULL REFERENCES applicants(applicant_id), asset_type TEXT NOT NULL,
 asset_value REAL NOT NULL CHECK(asset_value > 0), asset_age_years INTEGER NOT NULL CHECK(asset_age_years >= 0),
 risk_band TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
 product_id TEXT PRIMARY KEY, product_name TEXT NOT NULL UNIQUE, base_rate REAL NOT NULL CHECK(base_rate > 0),
 min_coverage REAL NOT NULL, max_coverage REAL NOT NULL, min_applicant_age INTEGER NOT NULL,
 max_asset_age INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
CREATE TABLE IF NOT EXISTS coverage_options (
 coverage_id TEXT PRIMARY KEY, coverage_name TEXT NOT NULL, coverage_type TEXT NOT NULL,
 default_limit REAL NOT NULL CHECK(default_limit > 0), deductible REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS product_coverage (
 product_id TEXT NOT NULL REFERENCES products(product_id), coverage_id TEXT NOT NULL REFERENCES coverage_options(coverage_id),
 max_limit REAL NOT NULL CHECK(max_limit > 0), PRIMARY KEY(product_id, coverage_id)
);
CREATE TABLE IF NOT EXISTS risk_factors (
 risk_factor_id TEXT PRIMARY KEY, factor_name TEXT NOT NULL UNIQUE, description TEXT NOT NULL,
 factor_value REAL NOT NULL CHECK(factor_value > 0), effective_from TEXT NOT NULL, effective_to TEXT
);
CREATE TABLE IF NOT EXISTS quotes (
 quote_id TEXT PRIMARY KEY, applicant_id TEXT NOT NULL REFERENCES applicants(applicant_id),
 asset_id TEXT NOT NULL REFERENCES insured_assets(asset_id), product_id TEXT NOT NULL REFERENCES products(product_id),
 coverage_id TEXT NOT NULL REFERENCES coverage_options(coverage_id), requested_coverage REAL NOT NULL,
 risk_multiplier REAL NOT NULL, calculated_premium REAL NOT NULL, premium_amount REAL NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('DRAFT','APPROVED','DECLINED','REFERRED','ACCEPTED','EXPIRED')),
 customer_accepted INTEGER NOT NULL CHECK(customer_accepted IN (0,1)), payment_received INTEGER NOT NULL CHECK(payment_received IN (0,1)),
 created_at TEXT NOT NULL, expires_at TEXT NOT NULL, pricing_version TEXT NOT NULL DEFAULT 'RATE-1.0'
);
CREATE TABLE IF NOT EXISTS underwriting_decisions (
 decision_id TEXT PRIMARY KEY, quote_id TEXT NOT NULL UNIQUE REFERENCES quotes(quote_id), outcome TEXT NOT NULL
 CHECK(outcome IN ('APPROVED','DECLINED','REFERRED')), reasons_json TEXT NOT NULL, risk_score REAL NOT NULL,
 rules_version TEXT NOT NULL, decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS policies (
 policy_id TEXT PRIMARY KEY, quote_id TEXT NOT NULL UNIQUE REFERENCES quotes(quote_id), applicant_id TEXT NOT NULL REFERENCES applicants(applicant_id),
 asset_id TEXT NOT NULL REFERENCES insured_assets(asset_id), product_id TEXT NOT NULL REFERENCES products(product_id),
 status TEXT NOT NULL CHECK(status IN ('ACTIVE','CANCELLED','EXPIRED')), start_date TEXT NOT NULL, end_date TEXT NOT NULL,
 premium_amount REAL NOT NULL, issued_at TEXT NOT NULL, CHECK(end_date > start_date)
);
CREATE TABLE IF NOT EXISTS endorsements (
 endorsement_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL REFERENCES policies(policy_id), endorsement_type TEXT NOT NULL,
 old_coverage REAL NOT NULL, new_coverage REAL NOT NULL, effective_date TEXT NOT NULL, status TEXT NOT NULL
 CHECK(status IN ('APPROVED','REFERRED','REJECTED')), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS renewals (
 renewal_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL REFERENCES policies(policy_id), renewal_year INTEGER NOT NULL,
 offered_premium REAL NOT NULL, status TEXT NOT NULL CHECK(status IN ('OFFERED','ACCEPTED','DECLINED','BLOCKED')),
 offer_date TEXT NOT NULL, response_date TEXT, UNIQUE(policy_id, renewal_year)
);
CREATE TABLE IF NOT EXISTS policy_events (
 event_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL REFERENCES policies(policy_id), event_type TEXT NOT NULL,
 from_status TEXT, to_status TEXT, event_date TEXT NOT NULL, details_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
 audit_id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
 action TEXT NOT NULL, actor TEXT NOT NULL, event_time TEXT NOT NULL, details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes(status);
CREATE INDEX IF NOT EXISTS idx_policies_status ON policies(status);
CREATE INDEX IF NOT EXISTS idx_renewals_status ON renewals(status);
"""


def connect(db_path: str | Path = "insurance.db") -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_db(db_path: str | Path = "insurance.db") -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def calculate_premium(asset_value: float, base_rate: float, risk_multiplier: float) -> float:
    """Transparent base premium formula, rounded to two decimals."""
    if asset_value <= 0 or base_rate <= 0 or risk_multiplier <= 0:
        raise ValueError("Asset value, base rate, and risk multiplier must be positive.")
    return round(asset_value * base_rate * risk_multiplier, 2)


def evaluate_underwriting(age: int, asset_age: int, requested_coverage: float,
                          min_coverage: float, max_coverage: float, min_age: int,
                          max_asset_age: int, risk_band: str | None) -> tuple[str, list[str], float]:
    reasons: list[str] = []
    if age < min_age:
        reasons.append(f"Applicant age {age} is below product minimum {min_age}.")
    if requested_coverage < min_coverage or requested_coverage > max_coverage:
        reasons.append(f"Requested coverage must be between {min_coverage:.0f} and {max_coverage:.0f}.")
    if asset_age > max_asset_age:
        reasons.append(f"Asset age {asset_age} exceeds product maximum {max_asset_age} years.")
    if not risk_band:
        return "REFERRED", ["Required risk information is missing; manual review required."], 75.0
    if reasons:
        return "DECLINED", reasons, 85.0
    if risk_band == "HIGH":
        return "REFERRED", ["High-risk asset requires underwriting review."], 70.0
    if risk_band == "MEDIUM":
        return "REFERRED", ["Medium-risk asset requires manual review."], 45.0
    return "APPROVED", ["Eligibility and automatic approval rules satisfied."], 15.0


def _id(prefix: str, n: int) -> str:
    return f"{prefix}-2026-{n:06d}"


def generate_data(db_path: str | Path = "insurance.db", output_dir: str | Path = "data/generated",
                  ground_truth_path: str | Path = "data/ground_truth/ground_truth.csv",
                  seed: int = DEFAULT_SEED, scale: float = 1.0) -> dict[str, Any]:
    """Generate a deterministic synthetic dataset and load it into SQLite.

    scale=1.0 creates the requested baseline. Smaller values support quick demos.
    Deliberate anomalies are documented in a separate ground-truth CSV.
    """
    if scale <= 0:
        raise ValueError("scale must be greater than zero")
    rng = random.Random(seed)
    counts = {"applicants": max(10, int(3000 * scale)), "quotes": max(20, int(4000 * scale)),
              "policies": max(10, int(2000 * scale)), "renewals": max(10, int(1200 * scale))}
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    Path(ground_truth_path).parent.mkdir(parents=True, exist_ok=True)
    if Path(db_path).exists(): Path(db_path).unlink()
    initialize_db(db_path)
    today = date(2026, 11, 2)
    applicants=[]; assets=[]; coverage=[]; risk_factors=[]; quotes=[]; decisions=[]; policies=[]; endorsements=[]; renewals=[]; events=[]; truth=[]
    regions = ["Telangana", "Karnataka", "Maharashtra", "Tamil Nadu", "Delhi", "Kerala"]
    occupations = ["Engineer", "Teacher", "Business owner", "Analyst", "Farmer", "Consultant", "Healthcare"]
    asset_types = {"PRD-MOTOR":"VEHICLE", "PRD-HOME":"HOME", "PRD-COMM":"COMMERCIAL_PROPERTY"}
    for i in range(1, counts["applicants"] + 1):
        applicants.append((_id("APP", i), f"Applicant {i:06d}", rng.randint(18, 75), rng.choice(regions), rng.choice(occupations), today.isoformat()))
        band = rng.choices(["LOW", "MEDIUM", "HIGH", None], [0.50, 0.30, 0.15, 0.05])[0]
        value = round(rng.uniform(250_000, 8_000_000), 2)
        asset_id = f"AST-2026-{i:06d}"
        assets.append((asset_id, _id("APP", i), rng.choice(list(asset_types.values())), value, rng.randint(0, 35), band, today.isoformat()))
    coverage = [("COV-BASIC", "Basic Protection", "BASIC", 1_000_000, 10_000),
                ("COV-STANDARD", "Standard Protection", "STANDARD", 5_000_000, 25_000),
                ("COV-PREMIUM", "Premium Protection", "PREMIUM", 25_000_000, 50_000)]
    risk_factors = [("RSK-LOW", "Low Risk", "Low risk multiplier", 1.0, "2026-01-01", None),
                    ("RSK-MED", "Medium Risk", "Medium risk multiplier", 1.2, "2026-01-01", None),
                    ("RSK-HIGH", "High Risk", "High risk multiplier", 1.8, "2026-01-01", None)]
    product_coverage=[]
    for pid, name, rate, min_cov, max_cov, min_age, max_asset_age in PRODUCTS:
        for cov_id, cov_name, cov_type, default_limit, deductible in coverage:
            product_coverage.append((pid, cov_id, max_cov))
    # Create transaction records. Each quote references a valid applicant and its asset.
    quote_decision_map={}
    for i in range(1, counts["quotes"] + 1):
        applicant_n = rng.randint(1, counts["applicants"])
        applicant = applicants[applicant_n-1]; asset = assets[applicant_n-1]
        product = rng.choice(PRODUCTS)
        cov = rng.choice(coverage)
        requested = round(min(max(asset[3], product[3]), product[4]), 2)
        band = asset[5]
        risk_mult = {"LOW":1.0,"MEDIUM":1.2,"HIGH":1.8,None:1.2}[band]
        premium = calculate_premium(asset[3], product[2], risk_mult)
        outcome, reasons, score = evaluate_underwriting(applicant[2], asset[4], requested, product[3], product[4], product[5], product[6], band)
        accepted = int(outcome == "APPROVED" and rng.random() < 0.75)
        paid = int(accepted and rng.random() < 0.94)
        status = outcome
        if accepted and paid: status = "ACCEPTED"
        qid = _id("QTE", i)
        created = (today - timedelta(days=rng.randint(0, 730))).isoformat()
        expires = (date.fromisoformat(created) + timedelta(days=30)).isoformat()
        quotes.append((qid, applicant[0], asset[0], product[0], cov[0], requested, risk_mult, premium, premium, status, accepted, paid, created, expires, "RATE-1.0"))
        did=f"DEC-2026-{i:06d}"
        decisions.append((did,qid,outcome,json.dumps(reasons),score,"UW-1.0",created))
        quote_decision_map[qid]=(applicant,asset,product,cov,requested,premium,outcome,accepted,paid,created)
    # Select at most one policy candidate per asset so the clean baseline does not
    # accidentally create unlabelled overlapping policies. Fill the required volume
    # by deterministically satisfying acceptance/payment for additional unique assets.
    eligible_quote_ids=[]
    seen_assets=set()
    for q in quotes:
        if q[2] in seen_assets:
            continue
        if q[10] == 1 and q[11] == 1:
            eligible_quote_ids.append(q[0]); seen_assets.add(q[2])
    if len(eligible_quote_ids) < counts["policies"]:
        selected=set(eligible_quote_ids)
        for idx,q in enumerate(quotes):
            if q[2] in seen_assets or q[0] in selected:
                continue
            qlist=list(q); qlist[10]=1; qlist[11]=1; qlist[9]="ACCEPTED"; quotes[idx]=tuple(qlist)
            eligible_quote_ids.append(q[0]); seen_assets.add(q[2]); selected.add(q[0])
            if len(eligible_quote_ids) >= counts["policies"]:
                break
    eligible_quote_ids=eligible_quote_ids[:counts["policies"]]
    start_dates={}
    for i,qid in enumerate(eligible_quote_ids,1):
        q=next(row for row in quotes if row[0]==qid)
        start=date.fromisoformat(q[12]); end=start+timedelta(days=365)
        status="CANCELLED" if i % 29 == 0 else ("EXPIRED" if end < today else "ACTIVE")
        # Required anomaly: first policy issued without customer acceptance/payment.
        if i == 1:
            qidx=next(j for j,row in enumerate(quotes) if row[0]==qid); qlist=list(quotes[qidx]); qlist[10]=0; qlist[11]=0; quotes[qidx]=tuple(qlist)
            truth.append(("ANOM-POLICY-001","POLICY_ISSUED_WITHOUT_ACCEPTANCE",qid,"CRITICAL","Policy must not be issued without acceptance and payment."))
        applicant_id=q[1]; asset_id=q[2]; product_id=q[3]
        premium=q[8]
        pid=_id("POL",i)
        policies.append((pid,qid,applicant_id,asset_id,product_id,status,start.isoformat(),end.isoformat(),premium,start.isoformat()))
        start_dates[pid]=(start,end,asset_id,status,product_id)
        events.append((f"EVT-{i:06d}",pid,"POLICY_ISSUED",None,status,start.isoformat(),json.dumps({"source":"synthetic_generator"})))
    # Required anomaly: a quote premium differs from the documented formula.
    if quotes:
        q=list(quotes[min(1,len(quotes)-1)]); q[8]=round(q[8]*2.75,2); quotes[min(1,len(quotes)-1)]=tuple(q)
        truth.append(("ANOM-PREMIUM-001","PREMIUM_OUTSIDE_FORMULA",q[0],"HIGH","premium_amount must equal calculated_premium under RATE-1.0."))
    # Endorsements: one valid and one over-limit case where the scale allows it.
    product_max = {p[0]: p[4] for p in PRODUCTS}
    for i,p in enumerate(policies[:max(1,min(100,int(100*scale)))],1):
        old_cov=next(q[5] for q in quotes if q[0]==p[1])
        new_cov=min(old_cov*1.05, product_max[p[4]])
        status="APPROVED"
        if i==1:
            new_cov=200_000_000; status="APPROVED"
            truth.append(("ANOM-ENDORSEMENT-001","ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT",p[0],"HIGH","New coverage exceeds the product maximum limit."))
        endorsements.append((f"END-{p[0]}-{i:03d}",p[0],"COVERAGE_CHANGE",old_cov,new_cov,p[6],status,p[9]))
    # Renewals are linked to policies; include one intentionally invalid renewal for a cancelled policy.
    cancelled=[p for p in policies if p[5]=="CANCELLED"]
    anomaly_cancelled = cancelled[0] if cancelled else None
    renewal_pool = [p for p in policies if p[5] != "CANCELLED" and (anomaly_cancelled is None or p[0] != anomaly_cancelled[0])]
    if not renewal_pool:
        renewal_pool = [p for p in policies if anomaly_cancelled is None or p[0] != anomaly_cancelled[0]]
    for i in range(1,counts["renewals"]+1):
        p = anomaly_cancelled if i == 1 and anomaly_cancelled else renewal_pool[(i-2 if i > 1 else 0) % len(renewal_pool)]
        status=rng.choice(["OFFERED","ACCEPTED","DECLINED"])
        if i==1 and anomaly_cancelled:
            status="OFFERED"
            truth.append(("ANOM-RENEWAL-001","RENEWAL_FOR_CANCELLED_POLICY",p[0],"HIGH","Cancelled policies must not receive renewal offers."))
        renewals.append((f"REN-{p[0]}-2027",p[0],2027,round(p[8]*rng.uniform(0.95,1.20),2),status,today.isoformat(),None))
    # Required overlap case: create a second policy on same asset with overlapping dates, if two policies exist.
    if len(policies)>=2:
        p1=policies[0]; p2=policies[1]
        # Keep the relationship internally consistent while deliberately creating a second policy
        # for the same applicant/asset and overlapping term.
        for qi, qrow in enumerate(quotes):
            if qrow[0] == p2[1]:
                qlist=list(qrow); qlist[1]=p1[2]; qlist[2]=p1[3]; quotes[qi]=tuple(qlist); break
        p2list=list(p2); p2list[2]=p1[2]; p2list[3]=p1[3]; p2list[6]=p1[6]; p2list[7]=p1[7]; policies[1]=tuple(p2list)
        truth.append(("ANOM-OVERLAP-001","OVERLAPPING_POLICY_PERIOD",p2[0],"MEDIUM","Overlapping policy periods for the same asset require a permitted reason."))
    with connect(db_path) as conn:
        conn.executemany("INSERT INTO applicants VALUES (?,?,?,?,?,?)", applicants)
        conn.executemany("INSERT INTO insured_assets VALUES (?,?,?,?,?,?,?)", assets)
        conn.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?,1)", PRODUCTS)
        conn.executemany("INSERT INTO coverage_options VALUES (?,?,?,?,?)", coverage)
        conn.executemany("INSERT INTO product_coverage VALUES (?,?,?)", product_coverage)
        conn.executemany("INSERT INTO risk_factors VALUES (?,?,?,?,?,?)", risk_factors)
        conn.executemany("INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", quotes)
        conn.executemany("INSERT INTO underwriting_decisions VALUES (?,?,?,?,?,?,?)", decisions)
        conn.executemany("INSERT INTO policies VALUES (?,?,?,?,?,?,?,?,?,?)", policies)
        conn.executemany("INSERT INTO endorsements VALUES (?,?,?,?,?,?,?,?)", endorsements)
        conn.executemany("INSERT INTO renewals VALUES (?,?,?,?,?,?,?)", renewals)
        conn.executemany("INSERT INTO policy_events VALUES (?,?,?,?,?,?,?)", events)
        conn.executemany("INSERT INTO audit_log(entity_type,entity_id,action,actor,event_time,details_json) VALUES (?,?,?,?,?,?)",
                         [("DATASET","SEED","GENERATED","system",today.isoformat(),json.dumps({"seed":seed,"scale":scale}))])
    tables={"applicants":applicants,"insured_assets":assets,"products":PRODUCTS,"coverage_options":coverage,
            "product_coverage":product_coverage,"risk_factors":risk_factors,"quotes":quotes,"underwriting_decisions":decisions,
            "policies":policies,"endorsements":endorsements,"renewals":renewals}
    # Export CSVs in a stable column order by reading the database.
    with connect(db_path) as conn:
        for table in tables:
            rows=conn.execute(f"SELECT * FROM {table}").fetchall()
            if not rows: continue
            with (out/f"{table}.csv").open("w",newline="",encoding="utf-8") as f:
                writer=csv.writer(f); writer.writerow(rows[0].keys()); writer.writerows([tuple(r) for r in rows])
    with Path(ground_truth_path).open("w",newline="",encoding="utf-8") as f:
        writer=csv.writer(f); writer.writerow(["issue_id","issue_type","record_id","severity","expected_rule"]); writer.writerows(truth)
    summary=validate_data(db_path)
    summary.update({"seed":seed,"scale":scale,"row_counts":{t:len(v) for t,v in tables.items()},"ground_truth_cases":len(truth)})
    (Path("reports")/"validation_summary.json").parent.mkdir(parents=True,exist_ok=True)
    Path("reports/validation_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary


def validate_data(db_path: str | Path = "insurance.db") -> dict[str, Any]:
    checks=[]
    with connect(db_path) as conn:
        fk=conn.execute("PRAGMA foreign_key_check").fetchall()
        checks.append({"check":"foreign_key_integrity","passed":len(fk)==0,"issues":len(fk)})
        for table,pk in [("applicants","applicant_id"),("insured_assets","asset_id"),("quotes","quote_id"),("policies","policy_id")]:
            total=conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            unique=conn.execute(f"SELECT COUNT(DISTINCT {pk}) FROM {table}").fetchone()[0]
            checks.append({"check":f"unique_{table}_pk","passed":total==unique,"rows":total,"unique":unique})
        bad_dates=conn.execute("SELECT COUNT(*) FROM policies WHERE end_date <= start_date").fetchone()[0]
        checks.append({"check":"policy_date_order","passed":bad_dates==0,"issues":bad_dates})
        bad_premiums=conn.execute("SELECT COUNT(*) FROM quotes WHERE ABS(premium_amount-calculated_premium)>0.01").fetchone()[0]
        checks.append({"check":"premium_reconciliation","passed":bad_premiums==0,"issues":bad_premiums,"note":"Deliberate anomaly records are expected and should be found by the exception screen."})
        counts={t:conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ["applicants","insured_assets","quotes","policies","renewals","endorsements"]}
    return {"checks":checks,"passed_checks":sum(1 for c in checks if c["passed"]),"total_checks":len(checks),"all_checks_passed":all(c["passed"] for c in checks),"database_counts":counts}


def detect_anomalies(db_path: str | Path = "insurance.db") -> list[dict[str, Any]]:
    found=[]
    with connect(db_path) as conn:
        for r in conn.execute("SELECT quote_id,calculated_premium,premium_amount FROM quotes WHERE ABS(calculated_premium-premium_amount)>0.01"):
            found.append({"issue_type":"PREMIUM_OUTSIDE_FORMULA","record_id":r["quote_id"],"severity":"HIGH","details":f"Expected {r['calculated_premium']:.2f}; found {r['premium_amount']:.2f}"})
        for r in conn.execute("SELECT p.policy_id,p.quote_id FROM policies p JOIN quotes q ON q.quote_id=p.quote_id WHERE q.customer_accepted=0 OR q.payment_received=0"):
            found.append({"issue_type":"POLICY_ISSUED_WITHOUT_ACCEPTANCE","record_id":r["policy_id"],"severity":"CRITICAL","details":f"Quote {r['quote_id']} lacks acceptance or payment"})
        for r in conn.execute("SELECT e.endorsement_id,e.policy_id,e.new_coverage,p.product_id,pr.max_coverage FROM endorsements e JOIN policies p ON p.policy_id=e.policy_id JOIN products pr ON pr.product_id=p.product_id WHERE e.new_coverage>pr.max_coverage"):
            found.append({"issue_type":"ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT","record_id":r["endorsement_id"],"severity":"HIGH","details":f"Coverage {r['new_coverage']:.2f} exceeds limit {r['max_coverage']:.2f}"})
        for r in conn.execute("SELECT r.renewal_id,r.policy_id FROM renewals r JOIN policies p ON p.policy_id=r.policy_id WHERE p.status='CANCELLED'"):
            found.append({"issue_type":"RENEWAL_FOR_CANCELLED_POLICY","record_id":r["renewal_id"],"severity":"HIGH","details":f"Renewal references cancelled policy {r['policy_id']}"})
        for r in conn.execute("SELECT p1.policy_id AS policy_a,p2.policy_id AS policy_b,p1.asset_id FROM policies p1 JOIN policies p2 ON p1.asset_id=p2.asset_id AND p1.policy_id<p2.policy_id AND p1.start_date<p2.end_date AND p2.start_date<p1.end_date"):
            found.append({"issue_type":"OVERLAPPING_POLICY_PERIOD","record_id":r["policy_b"],"severity":"MEDIUM","details":f"Policy overlaps {r['policy_a']} for asset {r['asset_id']}"})
    return found


def file_checksum(path: str | Path) -> str:
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(65536),b""): h.update(chunk)
    return h.hexdigest()
