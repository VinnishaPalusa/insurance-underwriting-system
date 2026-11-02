# Insurance Underwriting & Policy Management System

A local educational prototype built with Python, Streamlit, SQLite, Pandas and Plotly. It demonstrates synthetic-data generation, transparent underwriting rules, policy lifecycle records, anomaly detection, validation, and exports.

## Requirements
- Windows 10/11
- Python 3.11 or 3.12 recommended
- Internet access for the initial package installation

## Quick start (Windows PowerShell)

1. Extract the project ZIP to a folder such as `C:\Projects\insurance-underwriting-system`.
2. Open PowerShell in that folder.
3. Create and activate a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use this for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

4. Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. Launch the application:

```powershell
python -m streamlit run app.py
```

Streamlit will show a local address, usually `http://localhost:8501`, and may open it automatically in your browser.

6. In the left sidebar, select **Starter demo (10%)** and click **Generate / Reset dataset**. This creates a smaller dataset for quick testing. Choose **Full baseline (100%)** to generate the requested baseline volumes: 3,000 applicants, 4,000 quotes, 2,000 policies, and 1,200 renewals.

## Run tests

```powershell
python -m pytest -q
```

## Generate data without the UI

```powershell
python -c "from src.core import generate_data; print(generate_data(seed=20261022, scale=1.0))"
```

## Main screens
- Executive Dashboard
- Quote Evaluation
- Policies & Renewals
- Risk Exceptions
- Data Quality & Exports
- About Project

## Business rules in this prototype
- Premium = insured asset value × product base rate × risk multiplier.
- Eligibility checks applicant age, requested coverage, asset age and risk data.
- High/medium risk or missing risk data can be referred.
- Policy lifecycle records are linked to quotes and applicants through SQLite foreign keys.
- Deliberate test anomalies are separately documented in `data/ground_truth/ground_truth.csv`.

The pricing and eligibility rules are illustrative, fictional project rules and are not intended for real insurance decisions.

## Data and reproducibility
- Fixed default seed: `20261022`.
- Data generator accepts `seed` and `scale` arguments.
- CSV exports are written to `data/generated/`.
- Ground-truth labels are written separately to `data/ground_truth/ground_truth.csv`.
- A validation summary is written to `reports/validation_summary.json`.

## Known prototype limitations
This is a strong starter implementation, not a production-ready insurance platform. Before a final academic submission, continue hardening the generator and validations, add lifecycle action forms with transactional enforcement, expand the data dictionary, verify all requested counts and anomaly cases at both scales, and add full reproducibility checksum tests. The dashboard's manual quote evaluation is an evaluation preview; it does not yet persist a newly submitted quote from the UI.
