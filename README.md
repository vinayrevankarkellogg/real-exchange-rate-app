# real-exchange-rate-app

# IMF Real Exchange Rate Calculator

A Streamlit web application to calculate and plot the Bilateral Real Exchange Rate (RER) between two countries using IMF SDMX 3.0 API data.

## Features
- Fetches monthly CPI and Exchange Rate data from January 1976.
- Calculates $S(t)$ and $RER(t)$.
- Dynamically rebases the Real Index to 100 based on the selected sample period average ($RER^*$).
- Styled using a Google Material Design 3 configuration theme.
- Interactive Plotly visualizations and CSV data export.

## Deployment
This app can be deployed directly to [Streamlit Community Cloud](https://streamlit.io/cloud) by connecting the GitHub repository and specifying `app.py` as the main file path.