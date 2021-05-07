import streamlit as st
from typing import List
import pandas as pd


class TaxRate:
    def __init__(self, threshold, rate):
        self.threshold = threshold
        self.rate = rate / 100


st.title('Option Exercise Modeling')


# Main Model class
class Model:
    INCOME_TAX_BRACKETS = [
        TaxRate(0, 10),
        TaxRate(9876, 12),
        TaxRate(40126, 22),
        TaxRate(85526, 24),
        TaxRate(163301, 32),
        TaxRate(207351, 35),
        TaxRate(518401, 37)
    ]

    AMT_TAX_BRACKETS = [
        TaxRate(0, 0),
        # TODO this is for singles not married couples
        TaxRate(72900, 26),
        TaxRate(72900 + 197900, 28)
        # TODO this doesnt consider phase out https://www.taxpolicycenter.org/briefing-book/what-amt
    ]

    # TODO this assumes the highest bracket given income
    CAPITAL_GAIN_BRACKETS = [
        TaxRate(0, 20)
    ]

    def get_tax(self, tax_brackets: List[TaxRate], amount: float):
        tax = 0
        for idx in range(len(tax_brackets)):
            if amount == 0.0:
                return tax

            upper = tax_brackets[idx + 1].threshold if idx < len(tax_brackets) - 1 else float('inf')
            diff = min(amount, upper - tax_brackets[idx].threshold)
            amount -= diff
            tax += diff * tax_brackets[idx].rate
        return tax

    def compute(self, iso_exercise_units, nso_exercise_units):
        # amt_tax_now =
        spread = self.fmv - self.strike_price
        income_tax_total = self.get_tax(
            self.INCOME_TAX_BRACKETS, self.taxable_income + nso_exercise_units * spread
        )
        income_tax_without = self.get_tax(
            self.INCOME_TAX_BRACKETS, self.taxable_income
        )
        income_tax_now = income_tax_total - income_tax_without

        amt_tax_total = self.get_tax(
            self.AMT_TAX_BRACKETS, self.taxable_income + iso_exercise_units * spread
        )
        amt_tax_due = max(0, amt_tax_total - income_tax_total)

        tax_due_now = amt_tax_due + income_tax_now

        tax_after = self.get_tax(
            self.CAPITAL_GAIN_BRACKETS,
            (iso_exercise_units + nso_exercise_units) * (self.sell_price - self.strike_price)
        )
        cost_now = (iso_exercise_units + nso_exercise_units) * self.strike_price + tax_due_now

        long_term_profit = (iso_exercise_units + nso_exercise_units) * self.sell_price - cost_now - tax_after

        tax_for_exercise_after_public = self.get_tax(
            self.INCOME_TAX_BRACKETS,
            self.taxable_income + (iso_exercise_units + nso_exercise_units) *
            (self.sell_price - self.strike_price)
        ) - self.get_tax(self.INCOME_TAX_BRACKETS, self.taxable_income)

        tax_savings = tax_for_exercise_after_public - tax_after - tax_due_now

        nso_units_first_vest = (
            self.nso_total_units + self.iso_total_units) / 4 - iso_exercise_units

        sellable_iso = self.iso_total_units - iso_exercise_units
        sellable_nso = max(nso_units_first_vest - nso_exercise_units, 0)

        sellable_stock_value = (sellable_iso + sellable_nso) * (
            self.sell_price - self.strike_price)

        sellable_stock_value_after_tax = sellable_stock_value - self.get_tax(
            self.INCOME_TAX_BRACKETS, sellable_stock_value + self.taxable_income)

        return {
            "cost_now": int(cost_now),
            "tax_savings": int(tax_savings),
            "long_term_profit_after_tax": int(long_term_profit),
            "sellable_stock_value_after_tax": int(sellable_stock_value_after_tax)
        }



if __name__ == '__main__':
    model = Model()
    model.taxable_income = st.sidebar.slider(
        'Taxable income without option', 100000, 500000, 200000, 5000
    )

    model.iso_total_units = st.sidebar.slider(
        'Total exercisable ISO units', 5000, 200000, 10000, 10,
    )
    model.nso_total_units = st.sidebar.slider(
        'Total exercisable NSO units', 5000, 500000, 50000, 10,
    )

    model.strike_price = st.sidebar.slider('Strike price', 0.0, 30.0, 15.0, 0.1)
    model.fmv = st.sidebar.slider('Fair market value', 0.0, 30.0, 15.0, 0.1)
    model.sell_price = st.sidebar.slider('Sell price', 0.0, 200.0, 60.0, 0.1)

    iso_exercise_units = st.sidebar.slider(
        'Number of ISO units to exercise', 0, model.iso_total_units, 0, 10,
    )

    nso_exercise_units = st.sidebar.slider(
        'Number of NSO units to exercise', 0, model.nso_total_units, 0, 10,
    )

    st.markdown('### This does not count FICA or state tax, questionable?')
    st.markdown('### This assumes first vest happens next year')
    st.text('Otherwise it may have implications on your tax bracket unless you are already in highest bracket')
    st.markdown('### This assumes you sell all exercised options in the same year after holding period required by long term capital gain')

    output = model.compute(iso_exercise_units, nso_exercise_units)
    df = pd.DataFrame(
        [output.values()],
        columns=output.keys(),
    )

    st.table(df)
