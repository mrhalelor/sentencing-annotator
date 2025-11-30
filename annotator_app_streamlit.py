import streamlit as st
import pandas as pd
from pathlib import Path
from io import BytesIO

st.write("App loaded")


st.set_page_config(layout="wide", page_title="Sentencing Review Annotator")

# -------------------------------------------------------------------
# Load master Excel
# -------------------------------------------------------------------
st.sidebar.header("Load Master Excel (sentencing2.xlsx)")
uploaded = st.sidebar.file_uploader("Upload Excel", type=["xlsx", "xls"])

if uploaded is None:
    st.warning("Upload the master Excel to begin.")
    st.stop()

df = pd.read_excel(uploaded)

required_cols = ["case_number", "party", "sentence_info", "defense_ask"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"Missing required columns: {missing}")
    st.stop()

# Prepare output columns
if "reviewed_sentence" not in df.columns:
    df["reviewed_sentence"] = None
if "reviewed_defense_ask" not in df.columns:
    df["reviewed_defense_ask"] = None

# -------------------------------------------------------------------
# Session state initialization
# -------------------------------------------------------------------
if "row_index" not in st.session_state:
    st.session_state.row_index = 0

if "mode" not in st.session_state:
    # mode = "sentence" or "defense"
    st.session_state.mode = "sentence"

# Convenience access
row_idx = st.session_state.row_index
mode = st.session_state.mode

# -------------------------------------------------------------------
# Annotation UI (reused for both fields)
# -------------------------------------------------------------------
def annotation_ui(existing):
    """
    existing: dict or None
    Returns updated annotation dict.
    """
    ask_options = ["", "No Ask", "Incarceration", "Probation", "Time Served", "Non-custodial", "Custom"]

    if existing is None:
        existing = {"type": "", "details": ""}

    st.markdown("### Classification")
    ask_type = st.radio(
        "Ask Type:",
        ask_options,
        index=ask_options.index(existing.get("type", "")) if existing.get("type", "") in ask_options else 0
    )
    existing["type"] = ask_type

    # Incarceration flow
    if ask_type == "Incarceration":
        unit = st.radio("Unit", ["months", "years"], horizontal=True)
        col_a, col_b = st.columns(2)
        with col_a:
            num_min = st.number_input("Min", min_value=0, step=1, value=existing.get("num_min", 0))
        with col_b:
            num_max = st.number_input("Max", min_value=0, step=1, value=existing.get("num_max", 0))

        existing["unit"] = unit
        existing["num_min"] = int(num_min)
        existing["num_max"] = int(num_max)
        existing["details"] = f"{num_min}-{num_max} {unit}" if num_max else f"{num_min} {unit}"

    elif ask_type == "Non-custodial":
        txt = st.text_area("Details:", value=existing.get("details", ""), height=80)
        existing["details"] = txt

    elif ask_type == "Custom":
        txt = st.text_area("Custom Ask Text:", value=existing.get("details", ""), height=100)
        existing["details"] = txt

    elif ask_type == "Time Served":
        existing["details"] = ""

    elif ask_type == "No Ask":
        existing["details"] = ""

    return existing

# -------------------------------------------------------------------
# Row display
# -------------------------------------------------------------------
if row_idx < 0:
    st.session_state.row_index = 0
    row_idx = 0
if row_idx >= len(df):
    st.success("🎉 All rows reviewed!")
    st.stop()

row = df.iloc[row_idx]
st.markdown(f"## Reviewing Row {row_idx+1} / {len(df)}")

st.markdown(f"""
**Case Number:** `{row['case_number']}`  
**Party:** `{row['party']}`  
**Reviewing:** **{'Sentence Info' if mode=='sentence' else 'Defense Ask'}**
""")

# -------------------------------------------------------------------
# Text display
# -------------------------------------------------------------------
if mode == "sentence":
    raw_text = row["sentence_info"]
    existing_ann = row["reviewed_sentence"]
else:
    raw_text = row["defense_ask"]
    existing_ann = row["reviewed_defense_ask"]

st.markdown("### Raw Text")
st.write(raw_text if isinstance(raw_text, str) else "(empty)")

# Convert stored JSON-like dicts
if isinstance(existing_ann, str):
    # If it was stored as string, try literal_eval or fallback
    try:
        import ast
        existing_ann = ast.literal_eval(existing_ann)
    except:
        existing_ann = {"type": "", "details": ""}

annotation = annotation_ui(existing_ann)

# -------------------------------------------------------------------
# Buttons: save, navigation, mode toggle
# -------------------------------------------------------------------
save_col, next_col, back_col, skip_col = st.columns([2,1,1,1])

with save_col:
    if st.button("💾 Set Final for This Row"):
        if mode == "sentence":
            df.at[row_idx, "reviewed_sentence"] = annotation
        else:
            df.at[row_idx, "reviewed_defense_ask"] = annotation
        st.success("Saved!")

with next_col:
    if st.button("Next"):
        st.session_state.row_index += 1

with back_col:
    if st.button("Back") and row_idx > 0:
        st.session_state.row_index -= 1

with skip_col:
    if st.button("Skip"):
        if mode == "sentence":
            df.at[row_idx, "reviewed_sentence"] = {"type": "No Ask", "details": ""}
        else:
            df.at[row_idx, "reviewed_defense_ask"] = {"type": "No Ask", "details": ""}
        st.session_state.row_index += 1

st.markdown("---")

# Switch between reviewing sentence / defense ask
if st.button("Switch to Reviewing Defense Ask" if mode=="sentence" else "Switch to Reviewing Sentence Info"):
    st.session_state.mode = "defense" if mode=="sentence" else "sentence"

# -------------------------------------------------------------------
# Export
# -------------------------------------------------------------------
st.markdown("## Export Results")

if st.button("Export Annotated Excel"):
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    st.download_button(
        "Download Results",
        data=output,
        file_name="sentencing2_reviewed.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

