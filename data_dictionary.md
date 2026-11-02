# Data Dictionary (Prototype v1.0)

All data is synthetic. Currency is INR (₹). Dates use ISO 8601 `YYYY-MM-DD`. Identifiers are immutable strings. Database constraints are enforced where practical by SQLite; application-level checks are listed below.

| Entity | Field | Type | Required | Allowed values / units | Unique / validation |
|---|---|---|---|---|---|
| Applicant | applicant_id | TEXT | Yes | `APP-2026-######` | PK; immutable |
| Applicant | full_name | TEXT | Yes | Synthetic display name | Non-empty |
| Applicant | age | INTEGER | Yes | Years, 18–100 in master data | Range check |
| Applicant | region | TEXT | Yes | Synthetic region list | Non-empty |
| Applicant | occupation | TEXT | Yes | Synthetic occupation list | Non-empty |
| Applicant | created_at | DATE/TEXT | Yes | ISO date | Valid date |
| InsuredAsset | asset_id | TEXT | Yes | `AST-2026-######` | PK; immutable |
| InsuredAsset | applicant_id | TEXT | Yes | Applicant ID | FK → Applicant; owner must exist |
| InsuredAsset | asset_type | TEXT | Yes | VEHICLE, HOME, COMMERCIAL_PROPERTY | Controlled values |
| InsuredAsset | asset_value | REAL | Yes | INR | Greater than zero |
| InsuredAsset | asset_age_years | INTEGER | Yes | Years | 0 or greater |
| InsuredAsset | risk_band | TEXT | No | LOW, MEDIUM, HIGH, NULL | Missing risk is a referral condition |
| InsuredAsset | created_at | DATE/TEXT | Yes | ISO date | Valid date |
| Product | product_id | TEXT | Yes | PRD-MOTOR, PRD-HOME, PRD-COMM | PK |
| Product | product_name | TEXT | Yes | Product display name | Unique, non-empty |
| Product | base_rate | REAL | Yes | Decimal rate per year | Greater than zero |
| Product | min_coverage / max_coverage | REAL | Yes | INR | Minimum ≤ maximum |
| Product | min_applicant_age | INTEGER | Yes | Years | Positive integer |
| Product | max_asset_age | INTEGER | Yes | Years | 0 or greater |
| Product | active | INTEGER | Yes | 0 or 1 | Boolean constraint |
| CoverageOption | coverage_id | TEXT | Yes | COV-BASIC, COV-STANDARD, COV-PREMIUM | PK |
| CoverageOption | coverage_name | TEXT | Yes | Display name | Non-empty |
| CoverageOption | coverage_type | TEXT | Yes | BASIC, STANDARD, PREMIUM | Controlled values |
| CoverageOption | default_limit | REAL | Yes | INR | Greater than zero |
| CoverageOption | deductible | REAL | Yes | INR | 0 or greater |
| ProductCoverage | product_id | TEXT | Yes | Product ID | Composite PK; FK → Product |
| ProductCoverage | coverage_id | TEXT | Yes | Coverage ID | Composite PK; FK → CoverageOption |
| ProductCoverage | max_limit | REAL | Yes | INR | Greater than zero |
| RiskFactor | risk_factor_id | TEXT | Yes | RSK-LOW, RSK-MED, RSK-HIGH | PK |
| RiskFactor | factor_name | TEXT | Yes | Low/Medium/High Risk | Unique |
| RiskFactor | description | TEXT | Yes | Explanation | Non-empty |
| RiskFactor | factor_value | REAL | Yes | Multiplier | Greater than zero |
| RiskFactor | effective_from / effective_to | DATE/TEXT | Yes / No | ISO dates | End must be on/after start |
| Quote | quote_id | TEXT | Yes | `QTE-2026-######` | PK; immutable |
| Quote | applicant_id / asset_id / product_id / coverage_id | TEXT | Yes | IDs | Foreign keys to parent tables |
| Quote | requested_coverage | REAL | Yes | INR | Within product limits for a clean quote |
| Quote | risk_multiplier | REAL | Yes | Multiplier | Greater than zero; from risk rules |
| Quote | calculated_premium | REAL | Yes | INR | Formula-derived, rounded to 2 decimals |
| Quote | premium_amount | REAL | Yes | INR | Must reconcile to calculated premium except labelled anomaly |
| Quote | status | TEXT | Yes | DRAFT, APPROVED, DECLINED, REFERRED, ACCEPTED, EXPIRED | Enum constraint |
| Quote | customer_accepted / payment_received | INTEGER | Yes | 0 or 1 | Boolean; policy issuance requires both 1 |
| Quote | created_at / expires_at | DATE/TEXT | Yes | ISO dates | Expiry after creation |
| Quote | pricing_version | TEXT | Yes | RATE-1.0 | Rule version for traceability |
| Policy | policy_id | TEXT | Yes | `POL-2026-######` | PK; immutable |
| Policy | quote_id | TEXT | Yes | Quote ID | Unique FK → Quote (one policy per quote) |
| Policy | applicant_id / asset_id / product_id | TEXT | Yes | IDs | Foreign keys |
| Policy | status | TEXT | Yes | ACTIVE, CANCELLED, EXPIRED | Enum constraint |
| Policy | start_date / end_date | DATE/TEXT | Yes | ISO dates | End must be after start |
| Policy | premium_amount | REAL | Yes | INR | Must trace to quote premium |
| Policy | issued_at | DATE/TEXT | Yes | ISO date | Valid date |
| Endorsement | endorsement_id | TEXT | Yes | `END-<policy-id>-###` | PK |
| Endorsement | policy_id | TEXT | Yes | Policy ID | FK → Policy |
| Endorsement | endorsement_type | TEXT | Yes | COVERAGE_CHANGE in prototype | Controlled value |
| Endorsement | old_coverage / new_coverage | REAL | Yes | INR | Positive; new coverage must not exceed product limit |
| Endorsement | effective_date / created_at | DATE/TEXT | Yes | ISO dates | Valid dates |
| Endorsement | status | TEXT | Yes | APPROVED, REFERRED, REJECTED | Enum constraint |
| Renewal | renewal_id | TEXT | Yes | `REN-<policy-id>-2027` | PK |
| Renewal | policy_id | TEXT | Yes | Policy ID | FK → Policy; one per policy/year in prototype |
| Renewal | renewal_year | INTEGER | Yes | Calendar year | 4-digit year |
| Renewal | offered_premium | REAL | Yes | INR | Greater than zero; formula/rule derived in production version |
| Renewal | status | TEXT | Yes | OFFERED, ACCEPTED, DECLINED, BLOCKED | Enum constraint |
| Renewal | offer_date / response_date | DATE/TEXT | Yes / No | ISO dates | Response date cannot precede offer date |
| UnderwritingDecision | decision_id | TEXT | Yes | `DEC-2026-######` | PK |
| UnderwritingDecision | quote_id | TEXT | Yes | Quote ID | Unique FK → Quote |
| UnderwritingDecision | outcome | TEXT | Yes | APPROVED, DECLINED, REFERRED | Enum constraint |
| UnderwritingDecision | reasons_json | TEXT | Yes | JSON list of explanations | Must parse as JSON array |
| UnderwritingDecision | risk_score | REAL | Yes | 0–100 | Range check at application layer |
| UnderwritingDecision | rules_version | TEXT | Yes | UW-1.0 | Versioned rules |
| UnderwritingDecision | decided_at | DATE/TEXT | Yes | ISO date | Valid date |

## Relationships and cardinality
- Applicant 1:N InsuredAsset.
- Applicant 1:N Quote.
- InsuredAsset 1:N Quote over time; one clean issued policy per asset is selected by the baseline generator, with a labelled overlap anomaly injected separately.
- Product 1:N Quote and Product 1:N Policy.
- Product N:M CoverageOption through ProductCoverage.
- Quote 1:0..1 Policy.
- Quote 1:1 UnderwritingDecision in the generated baseline.
- Policy 1:N Endorsement, PolicyEvent and AuditLog records.
- Policy 1:N Renewal across different renewal years; the prototype constrains one record per policy/year.

## Prototype rule notes
- Premium = insured asset value × product base rate × risk multiplier.
- Missing risk data and medium/high risk produce referral outcomes.
- Product age/coverage violations produce a decline outcome.
- Ground-truth labels are stored separately from detection features.
- The prototype uses simplified educational rules; they are not real insurance pricing or advice.
