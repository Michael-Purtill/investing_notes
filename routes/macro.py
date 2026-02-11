# import pandas as pd
# from sqlmodel import Session, create_engine, text
from fastapi import APIRouter
import os
from fredapi import Fred
# from datetime import date
# from jinja2 import Template

# engine = create_engine("postgresql://", echo=False)

# You can define a prefix and tags here to keep main.py clean
router = APIRouter(
    prefix="/macro",
    tags=["macro"]
)

FRED_API_KEY = os.environ.get('FRED_API_KEY')

try:
    fred = Fred(api_key=FRED_API_KEY)
except Exception as e:
    print(e)

def get_latest_fred_data(series_id: str, description: str = ""):
    """
    Fetches the most recent data point for a given FRED series.
    """
    try:
        # Fetch last 1 year to ensure we find a valid data point (some series lag)
        data = fred.get_series(series_id, limit=5)
        if data.empty:
            raise ValueError("No data returned")
        
        latest_date = data.index[-1]
        latest_value = float(data.iloc[-1])
        
        return {
            'name': series_id,
            'symbol': series_id,
            'latest_value': latest_value,
            'date': latest_date.strftime('%Y-%m-%d'),
            'description': description
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch {series_id}: {str(e)}")

@router.get("/interest_rates")
def get_interest_rates():
    """
    Returns key rates: Fed Funds, 10Y Treasury, 2Y Treasury.
    Crucial for calculating the Risk-Free Rate and Discount Rates.
    """
    return {
        "fed_funds": get_latest_fred_data("FEDFUNDS", "Federal Funds Effective Rate"),
        "10y_treasury": get_latest_fred_data("DGS10", "10-Year Treasury Constant Maturity Rate"),
        "2y_treasury": get_latest_fred_data("DGS2", "2-Year Treasury Constant Maturity Rate"),
        "30y_mortgage": get_latest_fred_data("MORTGAGE30US", "30-Year Fixed Rate Mortgage Average")
    }

@router.get("/credit_spreads")
def get_credit_spreads():
    """
    Returns the 'Fear Gauge' of the bond market.
    """
    return {
        "high_yield_oas": get_latest_fred_data("BAMLH0A0HYM2", "ICE BofA US High Yield Index Option-Adjusted Spread"),
        "baa_spread": get_latest_fred_data("BAA10Y", "Moody's Seasoned Baa Corporate Bond Yield Relative to Yield on 10-Year Treasury")
    }

@router.get("/inflation")
def get_inflation_data():
    """
    Returns CPI and Breakeven Inflation (Market expectations).
    """
    return {
        "cpi_yoy": get_latest_fred_data("CPIAUCSL", "Consumer Price Index for All Urban Consumers"),
        "10y_breakeven": get_latest_fred_data("T10YIE", "10-Year Breakeven Inflation Rate")
    }

@router.get("/business_cycle")
def estimate_business_cycle():
    """
    Synthesizes multiple indicators to estimate the current Business Cycle Phase.
    Logic:
    1. Yield Curve (10Y-2Y): Inversion signals Late Cycle/Recession.
    2. High Yield Spread: Widening signals Recession/Fear.
    3. Sahm Rule (Unemployment): Rapid rise signals Recession.
    """
    
    # 1. Fetch Key Inputs
    # T10Y2Y: 10-Year Minus 2-Year Treasury (The classic recession predictor)
    yield_curve = get_latest_fred_data("T10Y2Y", "10-Year Minus 2-Year Treasury").latest_value
    
    # BAMLH0A0HYM2: High Yield Spread
    credit_spread = get_latest_fred_data("BAMLH0A0HYM2", "High Yield OAS").latest_value
    
    # SAHMREALTIME: Sahm Rule Recession Indicator
    sahm_rule = get_latest_fred_data("SAHMREALTIME", "Sahm Rule Recession Indicator").latest_value

    # 2. Logic Engine
    phase = "Unknown"
    signal = "Neutral"
    rationale = []

    # Check Yield Curve
    if yield_curve < 0:
        rationale.append("Yield Curve is Inverted (Predicts future recession).")
        phase = "Late Cycle / Warning"
        signal = "Caution"
    elif yield_curve < 0.5:
        rationale.append("Yield Curve is flattening.")
        phase = "Mid-to-Late Cycle"
    else:
        rationale.append("Yield Curve is positive (Normal growth).")
        phase = "Early/Mid Cycle"
        signal = "Bullish"

    # Check Credit Spreads (Historical avg is roughly 3.5% - 4.0%)
    if credit_spread > 5.0:
        rationale.append("Credit Spreads are widening significantly (Financial Stress).")
        phase = "Recession / Contraction"
        signal = "Bearish"
    elif credit_spread < 3.5:
        rationale.append("Credit Spreads are tight (Market is complacent/risk-on).")
        if phase != "Recession / Contraction":
            signal = "Bullish"

    # Check Sahm Rule (Value > 0.50 usually indicates active recession)
    if sahm_rule >= 0.50:
        phase = "Recession (Confirmed)"
        signal = "Bearish"
        rationale.append("Sahm Rule triggered (Unemployment rising fast).")

    # Final Synthesis
    full_rationale = " | ".join(rationale)

    return {
        'phase_estimate': phase,
        'signal_strength': signal,
        'rationale': full_rationale,
        'indicators':{
            "yield_curve_10y_2y": yield_curve,
            "high_yield_spread": credit_spread,
            "sahm_rule_indicator": sahm_rule
        }
    }
