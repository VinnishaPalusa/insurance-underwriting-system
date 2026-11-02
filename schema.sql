
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

