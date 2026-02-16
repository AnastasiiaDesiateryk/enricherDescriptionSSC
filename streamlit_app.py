import io
import streamlit as st
import pandas as pd

from dotenv import load_dotenv
load_dotenv()

from enricher import enrich_dataframe
from error_logging import extract_errors_table


st.set_page_config(
    page_title="Company Description Enricher",
    page_icon="🏢",
    layout="centered",
)

st.title("🏢 Company Description Enricher")
st.write(
    "Upload an Excel file with a **Database** sheet "
    "(columns **Company** and **Website** are required). "
    "You will receive a file with up-to-date company descriptions."
)

uploaded_file = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx", "xlsm"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, sheet_name="Database")
        st.success(f"File uploaded successfully. Rows found: {len(df)}")
        st.dataframe(df.head(5))
    except Exception:
        st.error("Failed to read the Database sheet")
        st.stop()

    if st.button("🚀 Generate descriptions"):
        with st.spinner("Processing websites..."):
            df_out = enrich_dataframe(df)

        # --- UI: show technical details ---
        err_df = extract_errors_table(df_out)
        total = len(df_out)
        failed = len(err_df)
        st.write(f"Total: **{total}** | With issues: **{failed}**")

        if failed > 0:
            st.subheader("Website issues")
            st.dataframe(err_df)
            csv_bytes = err_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download issues (CSV)",
                data=csv_bytes,
                file_name="errors.csv",
                mime="text/csv",
            )
        else:
            st.info("No issues detected.")

        # --- Excel: business columns only ---
        # The description is aligned with Company -> this is the Description column.
        excel_cols = [c for c in ["Company", "Website", "Description"] if c in df_out.columns]
        df_excel = df_out[excel_cols].copy()

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_excel.to_excel(writer, sheet_name="Database", index=False)
        output.seek(0)

        st.success("Done!")
        st.download_button(
            label="⬇️ Download Excel with descriptions",
            data=output,
            file_name="Database_enriched.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
