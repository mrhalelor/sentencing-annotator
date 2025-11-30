import streamlit as st
import pandas as pd
from pathlib import Path
from io import BytesIO
import ast

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
    # Always start each row by reviewing sentence_info
    st.session_state.mode = "sentence"

row_idx = st.session_state.row_index
mode = st.session_state.mode

# -------------------------------------------------------------------
# Function: annotation UI
# -------------------------------------------------------------------
def annotation_ui(existing):
    ask_options = ["", "No Ask", "Incarceration", "Probation", "Time Served", "Non-custodial", "Custom"]

    if existing is None or not isinstance(existing, dict):
        existing = {"type": "", "details": ""}

    st.markdown("### Classification")
    ask_type = st.radio(
        "Ask Type:",
        ask_options,
        index=ask_options.index(existing.get("type", "")) if existing.get("type", "") in ask_options else 0
    )
    existing["type"] = ask_type

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

    elif ask_type in ["Non-custodial", "Custom"]:
        txt = st.text_area("Details:", value=existing.get("details", ""), height=80)
        existing["details"] = txt

    elif ask_type in ["Time Served", "No Ask"]:
        existing["details"] = ""

    return existing

# -------------------------------------------------------------------
# Row handling + skipping rows with missing text
# -------------------------------------------------------------------
def advance_to_next_valid_row(start_idx):
    """Return index of next valid row (both fields present), or None if none remain."""
    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        if isinstance(row["sentence_info"], str) and isinstance(row["defense_ask"], str):
            return i
    return None

# Move to next valid row automatically if needed
row_idx = advance_to_next_valid_row(row_idx)
if row_idx is None:
    st.success("🎉 All rows reviewed!")
    st.stop()

st.session_state.row_index = row_idx  # ensure state is clean

row = df.iloc[row_idx]

# -------------------------------------------------------------------
# Header Info
# -------------------------------------------------------------------
st.markdown(f"## Reviewing Row {row_idx+1} / {len(df)}")

st.markdown(f"""
**Case Number:** `{row['case_number']}`  
**Party:** `{row['party']}`  
""")

# Status indicators
sent_done = isinstance(row["reviewed_sentence"], dict)
ask_done = isinstance(row["reviewed_defense_ask"], dict)

st.markdown(f"""
- Sentence Info Reviewed: {'✅' if sent_done else '❌'}  
- Defense Ask Reviewed: {'✅' if ask_done else '❌'}
""")

# -------------------------------------------------------------------
# Select which text to show based on mode
# -------------------------------------------------------------------
if mode == "sentence":
    raw_text = row["sentence_info"]
    existing_ann = row["reviewed_sentence"]
    st.subheader("Reviewing: Sentence Info")
else:
    raw_text = row["defense_ask"]
    existing_ann = row["reviewed_defense_ask"]
    st.subheader("Reviewing: Defense Ask")

st.markdown("### Raw Text")
st.write(raw_text)

# Load stored annotation (string/dict)
if isinstance(existing_ann, str):
    try:
        existing_ann = ast.literal_eval(existing_ann)
    except:
        existing_ann = {"type": "", "details": ""}

annotation = annotation_ui(existing_ann)

# -------------------------------------------------------------------
# Finalization Logic
# -------------------------------------------------------------------
if st.button("💾 Finalize This Section"):

    # Save data
    if mode == "sentence":
        df.at[row_idx, "reviewed_sentence"] = annotation
        st.session_state.mode = "defense"     # move automatically
    else:
        df.at[row_idx, "reviewed_defense_ask"] = annotation

        # If both sections done → move forward
        sent_done = isinstance(df.at[row_idx, "reviewed_sentence"], dict)
        ask_done = isinstance(df.at[row_idx, "reviewed_defense_ask"], dict)

        if sent_done and ask_done:
            next_row = advance_to_next_valid_row(row_idx + 1)
            if next_row is None:
                st.success("🎉 All rows reviewed!")
                st.stop()

            st.session_state.row_index = next_row
            st.session_state.mode = "sentence"  # reset mode for next row

# -------------------------------------------------------------------
# Export
# -------------------------------------------------------------------
st.markdown("---")
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
