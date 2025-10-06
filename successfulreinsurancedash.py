import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from tempfile import NamedTemporaryFile

# Set Streamlit page configuration
st.set_page_config(page_title="Reinsurance Loss Dashboard", layout="wide")

REQUIRED_COLUMNS = [
    "Region", "Loss Amount", "Policy Type",
    "Year", "Claim Count", "Risk Category", "Premium Collected"
]

# Welcome screen
if "file_uploaded" not in st.session_state:
    st.session_state.file_uploaded = False

if not st.session_state.file_uploaded:
    st.title("📊 Reinsurance Loss Portfolio Dashboard")
    st.image("welcome.gif", use_container_width=True)

    with st.sidebar.expander("📋 Upload Instructions", expanded=True):
        st.markdown("""
        **Please upload a CSV or Excel file with the following columns (case-sensitive):**
        - `Region`
        - `Loss Amount`
        - `Policy Type`
        - `Year`
        - `Claim Count`
        - `Risk Category`
        - `Premium Collected`
        """)

    uploaded_file = st.sidebar.file_uploader("📂 Upload CSV or Excel", type=["csv", "xlsx"])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            if not all(col in df.columns for col in REQUIRED_COLUMNS):
                st.error("❌ Uploaded file is missing one or more required columns.")
                st.stop()

            st.session_state.df = df
            st.session_state.file_uploaded = True
            st.rerun()

        except Exception as e:
            st.error(f"❌ Failed to read file: {e}")

else:
    df = st.session_state.df
    st.sidebar.success("✅ File uploaded")

    theme = st.sidebar.selectbox("🎨 Theme", ["Light", "Dark"])

    # Sidebar Filters
    st.sidebar.header("🔍 Filters")
    region_filter = st.sidebar.multiselect("Region", df["Region"].unique(), default=list(df["Region"].unique()))
    year_filter = st.sidebar.multiselect("Year", df["Year"].unique(), default=list(df["Year"].unique()))
    policy_filter = st.sidebar.multiselect("Policy Type", df["Policy Type"].unique(), default=list(df["Policy Type"].unique()))

    # Apply filters
    filtered_df = df[
        df["Region"].isin(region_filter) &
        df["Year"].isin(year_filter) &
        df["Policy Type"].isin(policy_filter)
    ]

    def format_dollars_short(n):
        abs_n = abs(n)
        if abs_n >= 1_000_000_000:
            return f"${n / 1_000_000_000:.1f}B"
        elif abs_n >= 1_000_000:
            return f"${n / 1_000_000:.1f}M"
        elif abs_n >= 1_000:
            return f"${n / 1_000:.1f}K"
        else:
            return f"${n:,.0f}"

    def format_bar_chart(df, x_col, y_col, title, y_axis_label):
        fig = px.bar(
            df, x=x_col, y=y_col, color=x_col,
            text=y_col,
            color_discrete_sequence=px.colors.qualitative.Vivid
        )
        fig.update_traces(
            marker_line_width=1.5,
            marker_line_color="black",
            texttemplate="$%{text:,.0f}",
            textposition="outside"
        )
        fig.update_layout(
            title=title,
            xaxis_title=x_col,
            yaxis_title=y_axis_label,
            title_font_size=20,
            bargap=0.25,
            height=500,
            plot_bgcolor="black" if theme == "Dark" else "white",
            paper_bgcolor="black" if theme == "Dark" else "white",
            font_color="white" if theme == "Dark" else "black",
            showlegend=False
        )
        return fig

    def generate_pdf_report(kpis):
        temp_file = NamedTemporaryFile(delete=False, suffix=".pdf")
        c = canvas.Canvas(temp_file.name, pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 40, "Reinsurance Loss Portfolio Report")

        c.setFont("Helvetica", 12)
        y = height - 80
        for label, value in kpis.items():
            c.drawString(50, y, f"{label}: {value}")
            y -= 20

        c.save()
        return temp_file.name

    st.markdown("### 📉 Key Metrics")

    total_premium = filtered_df["Premium Collected"].sum()
    total_loss = filtered_df["Loss Amount"].sum()
    claim_count = filtered_df["Claim Count"].sum()
    loss_ratio = total_loss / total_premium if total_premium else 0
    avg_severity = total_loss / claim_count if claim_count else 0
    underwriting_margin = total_premium - total_loss
    margin_percent = underwriting_margin / total_premium if total_premium else 0

    kpis = {
        "Total Premium": format_dollars_short(total_premium),
        "Total Loss": format_dollars_short(total_loss),
        "Loss Ratio": f"{loss_ratio:.2%}",
        "Avg Claim Severity": format_dollars_short(avg_severity),
        "Underwriting Margin": format_dollars_short(underwriting_margin),
        "Margin %": f"{margin_percent:.2%}"
    }

    # Colored KPI boxes
    kpi_cols = st.columns(3)
    kpi_colors = ["#e0f7fa", "#ffe0b2", "#dcedc8", "#f8bbd0", "#c5cae9", "#fff9c4"]

    for (label, value), color, col in zip(kpis.items(), kpi_colors, kpi_cols * 2):
        col.markdown(f"""
        <div style='padding: 15px; border-radius: 10px; background-color: {color}; color: black; text-align: center;'>
            <h4 style='margin-bottom: 5px;'>{label}</h4>
            <h2 style='margin-top: 0;'>{value}</h2>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 📈 Visualizations")

    chart_type = st.selectbox("📊 Select Chart Type", ["Loss by", "Underwriting Margin by"])
    dimension = st.radio("Group by", ["Region", "Year", "Policy Type"], horizontal=True)

    if chart_type == "Loss by":
        group_df = filtered_df.groupby(dimension)["Loss Amount"].sum().reset_index()
        fig = format_bar_chart(group_df, dimension, "Loss Amount", f"Loss by {dimension}", "Loss Amount")
        st.plotly_chart(fig, use_container_width=True)

    elif chart_type == "Underwriting Margin by":
        group_df = filtered_df.groupby(dimension)[["Premium Collected", "Loss Amount"]].sum().reset_index()
        group_df["Underwriting Margin"] = group_df["Premium Collected"] - group_df["Loss Amount"]
        fig = format_bar_chart(group_df, dimension, "Underwriting Margin", f"Margin by {dimension}", "Underwriting Margin")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Loss Distribution Pie Chart")
    pie_group = st.selectbox("Group Loss By", ["Region", "Policy Type", "Risk Category"])
    loss_group = filtered_df.groupby(pie_group)["Loss Amount"].sum().reset_index()

    fig_pie = px.pie(loss_group, names=pie_group, values="Loss Amount",
                     color_discrete_sequence=px.colors.qualitative.Set3,
                     title=f"Loss Distribution by {pie_group}")
    fig_pie.update_traces(textinfo="percent+label")
    st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("### 📋 Filtered Data Table")
    st.dataframe(filtered_df)

    def download_filtered_excel(dataframe):
        towrite = BytesIO()
        with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
            dataframe.to_excel(writer, sheet_name='Filtered Data', index=False)
            towrite.seek(0)
            return towrite
    st.download_button(
        label="📅 Download Filtered Excel",
        data=download_filtered_excel(filtered_df),
        file_name="filtered_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    #st.markdown("✅ This download includes **only the filtered** data shown above.")
    #st.download_button("📅 Download Filtered Excel", convert_df_to_excel(filtered_df), "filtered_data.xlsx", "application/vnd.openxmlformats-  #officedocument.spreadsheetml.sheet")

    pdf_file = generate_pdf_report(kpis)
    with open(pdf_file, "rb") as f:
        st.download_button("📄 Download PDF Report", f, file_name="reinsurance_report.pdf", mime="application/pdf")
