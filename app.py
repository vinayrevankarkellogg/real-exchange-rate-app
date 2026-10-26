import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="RER Calculator", layout="wide")

# Common IMF ISO3 Codes + Euro Area
COUNTRIES = {
    "United States": "USA", "Euro Area": "G163", "United Kingdom": "GBR", 
    "Japan": "JPN", "Canada": "CAN", "Switzerland": "CHE", "Australia": "AUS"
}

@st.cache_data(ttl=3600, show_spinner=False)
def _request_imf_series(series_key):
    """Requests and parses time series data from the IMF SDMX 3.0 API."""
    dataflow = "ER" if "XDC_USD" in series_key else "CPI"
    headers = {"Accept": "application/vnd.sdmx.data+json;version=2.0.0"}

    keys_to_try = [series_key]
    if dataflow == "CPI" and ".CPI." in series_key:
        keys_to_try.append(series_key.replace(".CPI.", ".HICP."))

    for key in keys_to_try:
        url = f"https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/{dataflow}/+/{key}"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        datasets = data.get("data", {}).get("dataSets", [])
        if not datasets or "series" not in datasets[0] or not datasets[0]["series"]:
            continue

        series_dict = datasets[0]["series"]
        first_series = next(iter(series_dict.values()))
        obs = first_series.get("observations", {})
        if not obs:
            continue

        structures = data.get("data", {}).get("structures", [])
        obs_dims = structures[0]["dimensions"]["observation"][0]["values"]

        dates = []
        values = []
        for idx_str, val_list in obs.items():
            if not val_list or val_list[0] is None:
                continue
            period_info = obs_dims[int(idx_str)]
            period_str = period_info.get("value") or period_info.get("id")
            dates.append(pd.to_datetime(period_str, format="%Y-M%m"))
            values.append(float(val_list[0]))

        df = pd.DataFrame({"Date": dates, "Value": values})
        df.set_index("Date", inplace=True)
        df.sort_index(inplace=True)
        return df

    return pd.DataFrame()


def fetch_imf_data(series_key):
    """Fetches time series data from IMF SDMX 3.0 API."""
    try:
        return _request_imf_series(series_key)
    except Exception as e:
        st.error(f"Error fetching {series_key}: {e}")
        return pd.DataFrame()

st.title("Bilateral Real Exchange Rate (RER) Calculator")
st.markdown("Calculates monthly RER using IMF CPI and Exchange Rate data.")

col1, col2 = st.columns(2)
with col1:
    c1_name = st.selectbox("Country 1 (Base)", list(COUNTRIES.keys()), index=0)
with col2:
    c2_name = st.selectbox("Country 2 (Target)", list(COUNTRIES.keys()), index=1)

c1_code = COUNTRIES[c1_name]
c2_code = COUNTRIES[c2_name]

# Date selection
st.sidebar.header("Sample Period")
min_date = pd.to_datetime("1976-01-01").date()
max_date = pd.to_datetime("today").date()
start_date = st.sidebar.date_input(
    "Start Date",
    value=min_date,
    min_value=min_date,
    max_value=max_date,
)
end_date = st.sidebar.date_input(
    "End Date",
    value=max_date,
    min_value=min_date,
    max_value=max_date,
)

chart_type = st.sidebar.radio("Display Data", ["Real", "Nominal", "Both"])

if st.button("Fetch and Calculate Data"):
    st.session_state["calculated"] = True

if st.session_state.get("calculated", False):
    if start_date > end_date:
        st.error("Start Date must be on or before End Date.")
        st.stop()

    with st.spinner('Fetching IMF Data...'):
        # Construct keys
        cpi_key1 = f"{c1_code}.CPI._T.IX.M"
        cpi_key2 = f"{c2_code}.CPI._T.IX.M"
        fx_key1 = f"{c1_code}.XDC_USD.PA_RT.M"
        fx_key2 = f"{c2_code}.XDC_USD.PA_RT.M"
        
        # Fetch Data
        df_cpi1 = fetch_imf_data(cpi_key1)
        df_cpi2 = fetch_imf_data(cpi_key2)
        df_fx1 = fetch_imf_data(fx_key1)
        df_fx2 = fetch_imf_data(fx_key2)
        
        if not all(df is not None and not df.empty for df in [df_cpi1, df_cpi2, df_fx1, df_fx2]):
            st.error("Insufficient data returned from IMF for these countries.")
            st.stop()
            
        # Combine into a single DataFrame
        df = pd.concat([df_cpi1, df_cpi2, df_fx1, df_fx2], axis=1).dropna()
        df.columns = ['P1', 'P2', 'FX1_USD', 'FX2_USD']
        df.sort_index(inplace=True)
        
        # Filter dates
        df = df.loc[pd.Timestamp(start_date):pd.Timestamp(end_date)].copy()
        if df.empty:
            st.error("No overlapping data available for the selected date range.")
            st.stop()
        
        # S(t): Units of Country 2 currency per one unit of Country 1 currency
        # Since FX is Local per USD: Country 1 to USD = 1/FX1. Then USD to Country 2 = FX2.
        df['S'] = df['FX2_USD'] / df['FX1_USD']
        
        # RER(t) = S(t) * P1(t) / P2(t)
        df['RER'] = df['S'] * df['P1'] / df['P2']
        
        # Calculate RER* (Average) and Index
        rer_star = df['RER'].mean()
        df['Real Index'] = 100 * df['RER'] / rer_star
        
        st.success(f"Calculation complete. RER* = {rer_star:.4f}")
        
        # Plotting
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        if chart_type in ["Real", "Both"]:
            fig.add_trace(
                go.Scatter(x=df.index, y=df['Real Index'], name="Real Index (RER)", line=dict(color="#6750A4", width=2)),
                secondary_y=False,
            )
        
        if chart_type in ["Nominal", "Both"]:
            fig.add_trace(
                go.Scatter(x=df.index, y=df['S'], name=f"Nominal S(t) ({c2_code}/{c1_code})", line=dict(color="#21005D", width=2, dash='dot')),
                secondary_y=True if chart_type == "Both" else False,
            )
            
        fig.update_layout(title="Exchange Rate Dynamics", template="plotly_white")
        if chart_type == "Both":
            fig.update_yaxes(title_text="Real Index (Base 100)", secondary_y=False)
            fig.update_yaxes(title_text="Nominal Exchange Rate", secondary_y=True)
            
        st.plotly_chart(fig, use_container_width=True)
        
        # CSV Download
        csv = df.to_csv().encode('utf-8')
        st.download_button(
            label="Download Data as CSV",
            data=csv,
            file_name=f"exchange_rate_{c1_code}_{c2_code}.csv",
            mime="text/csv",
        )