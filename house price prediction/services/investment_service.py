import math
from typing import Dict, Any, List

SCENARIO_DISCLAIMER = (
    "Calculated financial scenario based strictly on user-supplied assumptions. "
    "This is an analytical simulation, not a guaranteed market forecast or financial advice."
)


def calculate_emi(
    property_price: float,
    down_payment_pct: float = 20.0,
    annual_interest_rate: float = 8.5,
    tenure_years: int = 20,
    stamp_duty_pct: float = 6.0,
) -> Dict[str, Any]:
    """EMI, Down Payment, and Year-by-Year Amortization Schedule."""
    price = max(float(property_price), 1.0)
    dp_pct = min(max(float(down_payment_pct), 0.0), 95.0)
    rate_annual = max(float(annual_interest_rate), 0.0)
    years = min(max(int(tenure_years), 1), 40)
    stamp_pct = min(max(float(stamp_duty_pct), 0.0), 20.0)

    down_payment = price * (dp_pct / 100.0)
    stamp_duty = price * (stamp_pct / 100.0)
    upfront_cash_needed = down_payment + stamp_duty
    loan_amount = max(price - down_payment, 0.0)

    months = years * 12
    monthly_rate = (rate_annual / 100.0) / 12.0

    if loan_amount == 0:
        emi = 0.0
    elif monthly_rate == 0:
        emi = loan_amount / months
    else:
        factor = (1 + monthly_rate) ** months
        emi = loan_amount * monthly_rate * factor / (factor - 1)

    total_payment = emi * months
    total_interest = max(total_payment - loan_amount, 0.0)

    # Annual amortization schedule
    balance = loan_amount
    schedule: List[Dict[str, Any]] = []
    for yr in range(1, years + 1):
        yr_principal = 0.0
        yr_interest = 0.0
        for _ in range(12):
            if balance <= 0.01:
                break
            interest_part = balance * monthly_rate
            principal_part = min(emi - interest_part, balance) if emi > interest_part else 0.0
            balance = max(balance - principal_part, 0.0)
            yr_principal += principal_part
            yr_interest += interest_part
        schedule.append(
            {
                "year": yr,
                "principal_paid": round(yr_principal, 2),
                "interest_paid": round(yr_interest, 2),
                "remaining_balance": round(balance, 2),
            }
        )

    return {
        "property_price": round(price, 2),
        "down_payment_pct": round(dp_pct, 2),
        "down_payment": round(down_payment, 2),
        "stamp_duty_and_reg": round(stamp_duty, 2),
        "upfront_cash_needed": round(upfront_cash_needed, 2),
        "loan_amount": round(loan_amount, 2),
        "annual_interest_rate": round(rate_annual, 2),
        "tenure_years": years,
        "monthly_emi": round(emi, 2),
        "total_interest": round(total_interest, 2),
        "total_payable": round(total_payment, 2),
        "interest_to_principal_pct": round((total_interest / loan_amount) * 100, 2) if loan_amount > 0 else 0.0,
        "schedule": schedule,
        "disclaimer": SCENARIO_DISCLAIMER,
    }


def calculate_rental_yield(
    property_price: float,
    monthly_rent: float,
    annual_maintenance: float = 36000.0,
    annual_property_tax: float = 12000.0,
    vacancy_rate_pct: float = 5.0,
) -> Dict[str, Any]:
    """Gross & Net Rental Yield with payback years."""
    price = max(float(property_price), 1.0)
    rent = max(float(monthly_rent), 0.0)
    maint = max(float(annual_maintenance), 0.0)
    tax = max(float(annual_property_tax), 0.0)
    vac = min(max(float(vacancy_rate_pct), 0.0), 50.0)

    gross_annual_rent = rent * 12.0
    effective_annual_rent = gross_annual_rent * (1.0 - vac / 100.0)
    net_annual_income = effective_annual_rent - maint - tax

    gross_yield_pct = (gross_annual_rent / price) * 100.0
    net_yield_pct = (net_annual_income / price) * 100.0
    payback_years = round(price / net_annual_income, 1) if net_annual_income > 0 else None

    return {
        "property_price": round(price, 2),
        "monthly_rent": round(rent, 2),
        "gross_annual_rent": round(gross_annual_rent, 2),
        "effective_annual_rent": round(effective_annual_rent, 2),
        "annual_expenses": round(maint + tax, 2),
        "net_annual_income": round(net_annual_income, 2),
        "gross_yield_pct": round(gross_yield_pct, 2),
        "net_yield_pct": round(net_yield_pct, 2),
        "payback_years": payback_years,
        "disclaimer": SCENARIO_DISCLAIMER,
    }


def calculate_roi(
    property_price: float,
    down_payment_pct: float = 20.0,
    closing_costs_pct: float = 6.0,
    monthly_rent: float = 40000.0,
    annual_expenses: float = 60000.0,
    annual_appreciation_pct: float = 6.5,
    annual_interest_rate: float = 8.5,
    tenure_years: int = 20,
    holding_years: int = 7,
) -> Dict[str, Any]:
    """Total ROI, Cash-on-Cash Return, and Leveraged Equity Gain over holding horizon."""
    price = max(float(property_price), 1.0)
    hold = min(max(int(holding_years), 1), 30)
    app_rate = float(annual_appreciation_pct) / 100.0

    emi_data = calculate_emi(price, down_payment_pct, annual_interest_rate, tenure_years, closing_costs_pct)
    initial_cash = max(emi_data["upfront_cash_needed"], 1.0)
    annual_emi = emi_data["monthly_emi"] * 12.0

    # Remaining loan balance after holding_years
    sched = emi_data["schedule"]
    rem_balance = sched[min(hold, len(sched)) - 1]["remaining_balance"] if sched else 0.0

    future_value = price * ((1 + app_rate) ** hold)
    net_sale_equity = future_value - rem_balance

    # Cumulative cash flow with 3% annual rent escalation
    cum_net_cashflow = 0.0
    annual_rent = max(float(monthly_rent), 0.0) * 12.0
    annual_exp = max(float(annual_expenses), 0.0)
    for yr in range(1, hold + 1):
        rent_yr = annual_rent * ((1.03) ** (yr - 1))
        exp_yr = annual_exp * ((1.04) ** (yr - 1))
        debt_service = annual_emi if yr <= tenure_years else 0.0
        cum_net_cashflow += (rent_yr - exp_yr - debt_service)

    total_profit = (net_sale_equity + cum_net_cashflow) - initial_cash
    total_roi_pct = (total_profit / initial_cash) * 100.0
    year1_cashflow = annual_rent - annual_exp - annual_emi
    cash_on_cash_pct = (year1_cashflow / initial_cash) * 100.0

    # Annualized CAGR on equity
    end_wealth = max(initial_cash + total_profit, 1.0)
    cagr_pct = (((end_wealth / initial_cash) ** (1.0 / hold)) - 1.0) * 100.0 if end_wealth > 0 else -100.0

    return {
        "holding_years": hold,
        "initial_cash_invested": round(initial_cash, 2),
        "projected_property_value": round(future_value, 2),
        "remaining_loan_balance": round(rem_balance, 2),
        "projected_net_equity": round(net_sale_equity, 2),
        "cumulative_cashflow": round(cum_net_cashflow, 2),
        "total_net_profit": round(total_profit, 2),
        "total_roi_pct": round(total_roi_pct, 2),
        "annualized_roi_cagr_pct": round(cagr_pct, 2),
        "year1_cash_on_cash_pct": round(cash_on_cash_pct, 2),
        "disclaimer": SCENARIO_DISCLAIMER,
    }


def calculate_loan_affordability(
    monthly_income: float,
    existing_monthly_emis: float = 0.0,
    max_foir_pct: float = 45.0,
    annual_interest_rate: float = 8.5,
    tenure_years: int = 20,
    available_down_payment: float = 2000000.0,
) -> Dict[str, Any]:
    """Maximum eligible home loan & property budget based on FOIR."""
    income = max(float(monthly_income), 0.0)
    existing = max(float(existing_monthly_emis), 0.0)
    foir = min(max(float(max_foir_pct), 10.0), 65.0)
    rate_m = (max(float(annual_interest_rate), 0.1) / 100.0) / 12.0
    months = min(max(int(tenure_years), 1), 35) * 12
    down_pmt = max(float(available_down_payment), 0.0)

    max_emi = max((income * (foir / 100.0)) - existing, 0.0)
    factor = (1 + rate_m) ** months
    max_loan = max_emi * (factor - 1) / (rate_m * factor) if max_emi > 0 else 0.0
    max_property_budget = max_loan + down_pmt
    safe_budget = max_property_budget * 0.85

    return {
        "monthly_income": round(income, 2),
        "existing_monthly_emis": round(existing, 2),
        "max_affordable_emi": round(max_emi, 2),
        "max_eligible_loan": round(max_loan, 2),
        "available_down_payment": round(down_pmt, 2),
        "max_property_budget": round(max_property_budget, 2),
        "conservative_property_budget": round(safe_budget, 2),
        "foir_used_pct": round(foir, 1),
        "disclaimer": SCENARIO_DISCLAIMER,
    }


def calculate_buy_vs_rent(
    property_price: float,
    monthly_rent: float,
    down_payment_pct: float = 20.0,
    annual_interest_rate: float = 8.5,
    tenure_years: int = 20,
    annual_appreciation_pct: float = 6.5,
    annual_rent_increase_pct: float = 5.0,
    investment_return_pct: float = 10.0,
    annual_maintenance_pct: float = 1.0,
    horizon_years: int = 15,
) -> Dict[str, Any]:
    """Year-by-year net wealth comparison: Buying vs Renting + Investing the difference."""
    price = max(float(property_price), 1.0)
    rent0 = max(float(monthly_rent), 1.0)
    horizon = min(max(int(horizon_years), 1), 30)
    app_r = float(annual_appreciation_pct) / 100.0
    rent_g = float(annual_rent_increase_pct) / 100.0
    inv_r = float(investment_return_pct) / 100.0
    maint_r = float(annual_maintenance_pct) / 100.0

    emi_info = calculate_emi(price, down_payment_pct, annual_interest_rate, tenure_years, 6.0)
    annual_emi = emi_info["monthly_emi"] * 12.0
    sched = emi_info["schedule"]

    # Renter invests the upfront cash that buyer spent on down payment + closing costs
    renter_portfolio = emi_info["upfront_cash_needed"]
    buyer_side_portfolio = 0.0
    cum_rent_paid = 0.0
    cum_buy_outflow = emi_info["upfront_cash_needed"]

    timeline = []
    breakeven_year = None

    for yr in range(1, horizon + 1):
        prop_val = price * ((1 + app_r) ** yr)
        rem_loan = sched[yr - 1]["remaining_balance"] if yr <= len(sched) else 0.0
        yr_emi = annual_emi if yr <= tenure_years else 0.0
        yr_maint = prop_val * maint_r
        buy_cost_yr = yr_emi + yr_maint

        rent_cost_yr = (rent0 * 12.0) * ((1 + rent_g) ** (yr - 1))
        cum_rent_paid += rent_cost_yr
        cum_buy_outflow += buy_cost_yr

        # Compound existing portfolios
        renter_portfolio *= (1 + inv_r)
        buyer_side_portfolio *= (1 + inv_r)

        # Invest whoever pays less each year
        if buy_cost_yr > rent_cost_yr:
            renter_portfolio += (buy_cost_yr - rent_cost_yr)
        else:
            buyer_side_portfolio += (rent_cost_yr - buy_cost_yr)

        buyer_net_worth = (prop_val - rem_loan) + buyer_side_portfolio
        renter_net_worth = renter_portfolio

        if breakeven_year is None and buyer_net_worth >= renter_net_worth:
            breakeven_year = yr

        timeline.append(
            {
                "year": yr,
                "property_value": round(prop_val, 0),
                "remaining_loan": round(rem_loan, 0),
                "buyer_net_worth": round(buyer_net_worth, 0),
                "renter_net_worth": round(renter_net_worth, 0),
                "annual_rent": round(rent_cost_yr, 0),
                "annual_buy_outflow": round(buy_cost_yr, 0),
            }
        )

    final = timeline[-1]
    advantage = final["buyer_net_worth"] - final["renter_net_worth"]
    recommendation = "Buying yields higher projected net worth" if advantage > 0 else "Renting + Investing yields higher projected net worth"

    return {
        "horizon_years": horizon,
        "monthly_emi": emi_info["monthly_emi"],
        "initial_monthly_rent": round(rent0, 2),
        "final_buyer_net_worth": final["buyer_net_worth"],
        "final_renter_net_worth": final["renter_net_worth"],
        "net_wealth_difference": round(abs(advantage), 0),
        "winner": "buy" if advantage > 0 else "rent",
        "recommendation": recommendation,
        "breakeven_year": breakeven_year,
        "cumulative_rent_paid": round(cum_rent_paid, 0),
        "cumulative_buy_outflow": round(cum_buy_outflow, 0),
        "timeline": timeline,
        "disclaimer": SCENARIO_DISCLAIMER,
    }


def simulate_appreciation_scenarios(
    current_value: float,
    horizon_years: int = 10,
    conservative_pct: float = 4.0,
    moderate_pct: float = 7.0,
    optimistic_pct: float = 10.5,
) -> Dict[str, Any]:
    """Compound appreciation scenario simulator across three user-configurable growth rates."""
    base = max(float(current_value), 1.0)
    years = min(max(int(horizon_years), 1), 30)
    c_r = float(conservative_pct) / 100.0
    m_r = float(moderate_pct) / 100.0
    o_r = float(optimistic_pct) / 100.0

    series = []
    for yr in range(0, years + 1):
        series.append(
            {
                "year": yr,
                "conservative": round(base * ((1 + c_r) ** yr), 0),
                "moderate": round(base * ((1 + m_r) ** yr), 0),
                "optimistic": round(base * ((1 + o_r) ** yr), 0),
            }
        )

    return {
        "base_value": round(base, 2),
        "horizon_years": years,
        "rates": {
            "conservative_pct": round(conservative_pct, 2),
            "moderate_pct": round(moderate_pct, 2),
            "optimistic_pct": round(optimistic_pct, 2),
        },
        "final_values": series[-1],
        "series": series,
        "disclaimer": SCENARIO_DISCLAIMER,
    }
