from pathlib import Path
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from src.core import (DEFAULT_SEED, connect, initialize_db, generate_data, calculate_premium,
                      evaluate_underwriting, detect_anomalies, validate_data)

ROOT = Path(__file__).parent
DB_PATH = ROOT / "insurance.db"
DATA_DIR = ROOT / "data" / "generated"
TRUTH_PATH = ROOT / "data" / "ground_truth" / "ground_truth.csv"

st.set_page_config(page_title="Underwrite | Insurance Operations", page_icon="🛡️", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {
    background: #f5f7fb;
    border: 1px solid #e5eaf2;
    padding: 14px;
    border-radius: 12px;
    color: #111827 !important;
}
/* Explicitly set metric text colours: Streamlit's dark theme otherwise
   makes the text white on our light KPI cards. */
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] p,
[data-testid="stMetricLabel"] label {
    color: #334155 !important;
    opacity: 1 !important;
}
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] div,
[data-testid="stMetricValue"] p {
    color: #111827 !important;
    opacity: 1 !important;
}
[data-testid="stMetricDelta"] {
    color: #334155 !important;
}
.hero {padding: 22px 26px; border-radius: 16px; background: linear-gradient(120deg,#10243a,#1c5273); color: white; margin-bottom: 18px;}
.hero h1 {margin: 0 0 6px 0; font-size: 2rem; color: white;}
.hero p {margin: 0; color: #d8e8f3;}
</style>
""", unsafe_allow_html=True)


def db_ready():
    if not DB_PATH.exists():
        initialize_db(DB_PATH)
        return False
    try:
        with connect(DB_PATH) as c:
            c.execute("SELECT 1 FROM applicants LIMIT 1")
        return True
    except Exception:
        initialize_db(DB_PATH)
        return False


def read_df(sql, params=()):
    with connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def count(table):
    with connect(DB_PATH) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

st.sidebar.title("🛡️ Underwrite")
st.sidebar.caption("Insurance underwriting & policy operations")
page = st.sidebar.radio("Workspace", ["Executive Dashboard", "Quote Evaluation", "Policies & Renewals", "Risk Exceptions", "Data Quality & Exports", "About Project"])
st.sidebar.divider()
st.sidebar.subheader("Synthetic dataset")
scale_label = st.sidebar.selectbox("Dataset size", ["Starter demo (10%)", "Full baseline (100%)"], index=0)
scale = 0.1 if scale_label.startswith("Starter") else 1.0
seed = st.sidebar.number_input("Fixed random seed", min_value=1, max_value=999999999, value=DEFAULT_SEED, step=1)
if st.sidebar.button("Generate / Reset dataset", type="primary", use_container_width=True):
    with st.spinner("Generating linked records and running validation..."):
        summary = generate_data(DB_PATH, DATA_DIR, TRUTH_PATH, int(seed), scale)
    st.sidebar.success(f"Dataset generated. {summary['database_counts']['quotes']:,} quotes created.")
    st.rerun()

ready = db_ready()
if not ready or count("applicants") == 0:
    st.markdown('<div class="hero"><h1>Insurance Underwriting & Policy Management</h1><p>Evaluate risk. Explain decisions. Preserve every important event.</p></div>', unsafe_allow_html=True)
    st.info("Welcome! Generate the starter dataset from the left sidebar to initialise the demo. The starter dataset is smaller and faster; use the full baseline for the specified project volumes.")
    st.markdown("### Included workflows")
    c1,c2,c3 = st.columns(3)
    c1.markdown("**01 · Underwriting**\n\nEligibility, transparent premium calculation, approval, decline and referral.")
    c2.markdown("**02 · Policy lifecycle**\n\nIssuance checks, cancellation, endorsements and renewals.")
    c3.markdown("**03 · Assurance**\n\nAnomaly detection, data quality checks, ground truth and exports.")
    st.stop()

if page == "Executive Dashboard":
    st.markdown('<div class="hero"><h1>Insurance Operations Overview</h1><p>One place to monitor underwriting performance, policy lifecycle and data exceptions.</p></div>', unsafe_allow_html=True)
    applicants, quotes, policies, renewals = [count(t) for t in ["applicants","quotes","policies","renewals"]]
    active = read_df("SELECT COUNT(*) n FROM policies WHERE status='ACTIVE'").iloc[0,0]
    exceptions = len(detect_anomalies(DB_PATH))
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    for col,label,value in [(c1,"Applicants",applicants),(c2,"Quotes",quotes),(c3,"Policies",policies),(c4,"Active policies",active),(c5,"Renewals",renewals),(c6,"Detected exceptions",exceptions)]:
        col.metric(label, f"{value:,}")
    left,right=st.columns(2)
    with left:
        outcomes=read_df("SELECT status, COUNT(*) AS records FROM quotes GROUP BY status ORDER BY records DESC")
        st.subheader("Quote status distribution")
        st.plotly_chart(px.bar(outcomes,x="status",y="records",color="status",text_auto=True),use_container_width=True)
    with right:
        product=read_df("SELECT pr.product_name, COUNT(q.quote_id) AS quotes FROM products pr LEFT JOIN quotes q ON q.product_id=pr.product_id GROUP BY pr.product_id")
        st.subheader("Quotes by product")
        st.plotly_chart(px.pie(product,names="product_name",values="quotes",hole=0.55),use_container_width=True)
    st.subheader("Latest underwriting decisions")
    st.dataframe(read_df("SELECT d.decision_id,d.quote_id,d.outcome,d.risk_score,d.reasons_json,d.decided_at FROM underwriting_decisions d ORDER BY d.decided_at DESC LIMIT 12"),use_container_width=True,hide_index=True)

elif page == "Quote Evaluation":
    st.title("Quote Evaluation")
    st.caption("Evaluate a proposed quote using the documented rule set. The demo uses synthetic records.")
    applicants_df=read_df("SELECT applicant_id,full_name,age FROM applicants ORDER BY applicant_id LIMIT 500")
    assets_df=read_df("SELECT asset_id,applicant_id,asset_type,asset_value,asset_age_years,risk_band FROM insured_assets ORDER BY asset_id LIMIT 500")
    products_df=read_df("SELECT * FROM products WHERE active=1")
    with st.form("quote_form"):
        applicant_id=st.selectbox("Applicant",applicants_df.applicant_id.tolist(),format_func=lambda x: f"{x} — {applicants_df.loc[applicants_df.applicant_id==x,'full_name'].iloc[0]}")
        own_assets=assets_df[assets_df.applicant_id==applicant_id]
        asset_id=st.selectbox("Insured asset",own_assets.asset_id.tolist(),format_func=lambda x: f"{x} — {own_assets.loc[own_assets.asset_id==x,'asset_type'].iloc[0]}")
        product_id=st.selectbox("Product",products_df.product_id.tolist(),format_func=lambda x: products_df.loc[products_df.product_id==x,'product_name'].iloc[0])
        prod=products_df[products_df.product_id==product_id].iloc[0]
        asset=own_assets[own_assets.asset_id==asset_id].iloc[0]
        coverage=st.number_input("Requested coverage (₹)",min_value=1.0,value=float(min(max(asset.asset_value,prod.min_coverage),prod.max_coverage)),step=10000.0)
        submitted=st.form_submit_button("Evaluate quote",type="primary")
    if submitted:
        applicant=applicants_df[applicants_df.applicant_id==applicant_id].iloc[0]
        outcome,reasons,score=evaluate_underwriting(int(applicant.age),int(asset.asset_age_years),float(coverage),float(prod.min_coverage),float(prod.max_coverage),int(prod.min_applicant_age),int(prod.max_asset_age),asset.risk_band)
        multiplier={"LOW":1.0,"MEDIUM":1.2,"HIGH":1.8}.get(asset.risk_band,1.2)
        premium=calculate_premium(float(asset.asset_value),float(prod.base_rate),multiplier)
        a,b,c=st.columns(3)
        a.metric("Recommendation",outcome)
        b.metric("Indicative annual premium",f"₹{premium:,.2f}")
        c.metric("Risk score",f"{score:.0f}/100")
        st.markdown("#### Decision explanation")
        for reason in reasons: st.write(f"- {reason}")
        st.caption(f"Pricing formula: asset value × base rate ({prod.base_rate:.3%}) × risk multiplier ({multiplier:.1f}). This is a synthetic educational rule, not a real insurance quote.")

elif page == "Policies & Renewals":
    st.title("Policies & Renewals")
    tab1,tab2,tab3=st.tabs(["Policies","Endorsements","Renewals"])
    with tab1:
        df=read_df("SELECT p.policy_id,p.status,p.start_date,p.end_date,p.premium_amount,pr.product_name,p.applicant_id,p.asset_id FROM policies p JOIN products pr ON pr.product_id=p.product_id ORDER BY p.issued_at DESC LIMIT 1000")
        status_filter=st.multiselect("Filter policy status",sorted(df.status.unique()),default=sorted(df.status.unique()))
        st.dataframe(df[df.status.isin(status_filter)],use_container_width=True,hide_index=True)
        st.download_button("Export displayed policies",df[df.status.isin(status_filter)].to_csv(index=False),"policies_export.csv","text/csv")
    with tab2:
        st.dataframe(read_df("SELECT e.*,p.status AS policy_status FROM endorsements e JOIN policies p ON p.policy_id=e.policy_id ORDER BY e.created_at DESC LIMIT 500"),use_container_width=True,hide_index=True)
    with tab3:
        st.dataframe(read_df("SELECT r.*,p.status AS policy_status FROM renewals r JOIN policies p ON p.policy_id=r.policy_id ORDER BY r.offer_date DESC LIMIT 1000"),use_container_width=True,hide_index=True)
        st.caption("This demo shows generated lifecycle records. Use the exception workspace to review renewal offers linked to cancelled policies.")

elif page == "Risk Exceptions":
    st.title("Risk & Exception Review")
    st.caption("Detected issues are derived from the actual records and rules, not just copied from the ground-truth file.")
    anomalies=detect_anomalies(DB_PATH)
    if anomalies:
        df=pd.DataFrame(anomalies)
        c1,c2=st.columns(2)
        with c1: severity=st.multiselect("Severity",sorted(df.severity.unique()),default=sorted(df.severity.unique()))
        with c2: types=st.multiselect("Issue type",sorted(df.issue_type.unique()),default=sorted(df.issue_type.unique()))
        view=df[df.severity.isin(severity)&df.issue_type.isin(types)]
        st.dataframe(view,use_container_width=True,hide_index=True)
        st.download_button("Export exception report",view.to_csv(index=False),"exception_report.csv","text/csv")
        st.metric("Detected issue records",len(df))
    else: st.success("No anomalies detected in the current dataset.")
    if TRUTH_PATH.exists():
        with st.expander("Ground-truth labels (evaluation only)"):
            st.warning("Ground truth is for evaluation. Do not use these labels as input features for detection.")
            st.dataframe(pd.read_csv(TRUTH_PATH),use_container_width=True,hide_index=True)

elif page == "Data Quality & Exports":
    st.title("Data Quality & Exports")
    summary=validate_data(DB_PATH)
    c1,c2,c3=st.columns(3)
    c1.metric("Checks passed",f"{summary['passed_checks']}/{summary['total_checks']}")
    c2.metric("Database integrity", "PASS" if summary['all_checks_passed'] else "REVIEW")
    c3.metric("Foreign-key issues",summary['checks'][0]['issues'])
    st.dataframe(pd.DataFrame(summary["checks"]),use_container_width=True,hide_index=True)
    st.subheader("Export datasets")
    with connect(DB_PATH) as conn:
        tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    selected=st.selectbox("Choose table",tables)
    export_df=read_df(f"SELECT * FROM {selected}")
    st.caption(f"{len(export_df):,} rows · {len(export_df.columns)} columns")
    st.download_button("Download CSV",export_df.to_csv(index=False),f"{selected}.csv","text/csv")
    st.json(summary)

else:
    st.title("About this project")
    st.markdown("""
    **Purpose:** Demonstrate a traceable, rule-based insurance underwriting and policy lifecycle workflow using synthetic data.

    **Rules:** Pricing is reproducible from an explicit formula; underwriting outcomes include reason codes; policy and renewal records are linked with foreign keys; known test anomalies are labelled separately.

    **Limitations:** This is an educational prototype, not a real insurance decisioning service. The generated people, assets and prices are fictional. Production deployment would require authentication, role-based access, stronger audit controls, migrations, monitoring, legal/compliance review and a formal pricing/risk model.
    """)
