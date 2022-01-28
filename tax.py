from datetime import datetime
import streamlit as st
from typing import List
import pandas as pd
from tax_rates import (
    AMT_TAX_BRACKETS,
    CA_AMT_TAX_BRACKETS,
    CAPITAL_GAIN_TAX_BRACKETS,
    DEDUCTION,
    INCOME_TAX_BRACKETS,
    MEDICARE_TAX_BRACKETS,
    NIIT_TAX_BRACKETS,
    SOCIAL_SECURITY_TAX_BRACKETS,
    STATE_TAX_BRACKETS,
    TaxRate,
)

st.title("2022 - 2025 Income and Tax Projection")

STRIKE_PRICE = 15.68
FMV_AT_EXERCISE = 19.95

GRANT_MONTH = 0
MOVE_MONTH = 12
TOTAL_MONTH = 48

MOVE_MONTH_PRICE = 60
END_MONTH_PRICE = 140


class Event:
    def __init__(
        self, quantity, month, txn_type, option_type="iso", exercise_price=None
    ):
        self.option_type = option_type
        self.quantity = quantity
        self.price = (END_MONTH_PRICE - MOVE_MONTH_PRICE) * (month - MOVE_MONTH) / (
            TOTAL_MONTH - MOVE_MONTH
        ) + MOVE_MONTH_PRICE
        self.txn_type = txn_type
        self.exercise_price = exercise_price
        self.month = month

    def income(self):
        if self.option_type == "iso" or self.txn_type == "sale":
            return 0

        return (self.price - STRIKE_PRICE) * self.quantity

    def capital_gain(self):
        if self.txn_type == "exercise":
            return 0

        if self.option_type == "iso":
            return (self.price - STRIKE_PRICE) * self.quantity

        return (self.price - self.exercise_price) * self.quantity

    def ca_ratio(self):
        if self.txn_type == "sale":
            return 0

        return (MOVE_MONTH - GRANT_MONTH) * 1.0 / (self.month - GRANT_MONTH)

    def cost(self):
        return STRIKE_PRICE * self.quantity if self.txn_type == "exercise" else 0

    def cash(self):
        return self.price * self.quantity if self.txn_type == "sale" else 0


class FY:
    def __init__(
        self,
        month,
        salary,
        spouse_salary,
        vested_rsu,
        spouse_vested_rsu,
    ):
        self.month = month
        self.salary = salary
        self.spouse_salary = spouse_salary
        self.vested_rsu = vested_rsu
        self.spouse_vested_rsu = spouse_vested_rsu
        pass


FYS = [
    None,
    None,
    FY(24, 238050, 127710 + 37500, 300000 * 9 / 48, 0),
    FY(
        36,
        238050,
        127710 * 1.1,
        300000 * (1 / 4 + 9 / 48),
        220000 * (1 / 4 + 3 / 16) + 90000 * (3 / 16),
    ),
    FY(
        48,
        238050,
        127710 * 1.1 * 1.1,
        300000 * (1 / 4 + 1 / 4 + 9 / 48),
        220000 * (1 / 4) + 90000 * (1 / 4 + 3 / 16),
    ),
]


class Model:
    def __init__(self, married) -> None:
        self.married = married
        pass

    def get_tax(self, tax_brackets_map, amount: float):
        tax = 0
        tax_brackets: List[TaxRate] = tax_brackets_map[
            "married" if self.married else "single"
        ]
        for idx in range(len(tax_brackets)):
            if amount == 0.0:
                return tax

            upper = (
                tax_brackets[idx + 1].threshold
                if idx < len(tax_brackets) - 1
                else float("inf")
            )
            diff = min(amount, upper - tax_brackets[idx].threshold)
            amount -= diff
            tax += diff * tax_brackets[idx].rate
        return tax

    def get_fica_tax(self, amount):
        return self.get_tax(SOCIAL_SECURITY_TAX_BRACKETS, amount) + self.get_tax(
            MEDICARE_TAX_BRACKETS, amount
        )

    def get_federal_income_tax(self, amount):
        taxable = amount - DEDUCTION["married" if self.married else "single"]
        return self.get_fica_tax(taxable) + self.get_tax(INCOME_TAX_BRACKETS, taxable)

    def get_federal_capital_gain_tax(self, amount):
        return self.get_tax(CAPITAL_GAIN_TAX_BRACKETS, amount) + self.get_tax(
            NIIT_TAX_BRACKETS, amount
        )

    def get_state_tax(self, amount):
        return self.get_tax(STATE_TAX_BRACKETS, amount)


def get_fy_projection(married, fy: FY, events: List[Event]):
    m = Model(married)

    self_income = fy.salary + fy.vested_rsu + sum(e.income() for e in events)

    # ignore 3 months of allocation for salary
    self_ca_income = sum(e.income() * e.ca_ratio() for e in events)
    if fy.month == 24:
        self_ca_income += fy.salary * 3 / 12 + 37500 + 127710 * 2 / 12

    spouse_income = fy.spouse_salary + fy.spouse_vested_rsu

    federal_income_tax = 0
    iso_exercises = [
        e for e in events if e.option_type == "iso" and e.txn_type == "exercise"
    ]
    iso_spreads = sum((e.price - STRIKE_PRICE) * e.quantity for e in iso_exercises)

    ca_income_tax = m.get_state_tax(self_ca_income)
    ca_amt_tax = max(
        0,
        m.get_tax(
            CA_AMT_TAX_BRACKETS,
            sum(
                (e.price - STRIKE_PRICE) * e.quantity * e.ca_ratio()
                for e in iso_exercises
            )
            + self_ca_income,
        )
        - ca_income_tax,
    )

    amt_tax = 0
    if married:
        federal_income_tax = m.get_federal_income_tax(self_income + spouse_income)
        amt_tax = m.get_tax(
            AMT_TAX_BRACKETS,
            self_income
            + spouse_income
            + sum((e.price - STRIKE_PRICE) * e.quantity for e in iso_exercises),
        )
    else:
        federal_income_tax = m.get_federal_income_tax(
            self_income
        ) + m.get_federal_income_tax(spouse_income)
        amt_tax = m.get_tax(
            AMT_TAX_BRACKETS,
            self_income + iso_spreads,
        )

    federal_amt_tax = max(0, amt_tax - federal_income_tax)

    capital_gain = sum(e.capital_gain() for e in events)
    first_part = 0
    if married:
        first_part = max(
            0,
            CAPITAL_GAIN_TAX_BRACKETS["married"][2].threshold
            - self_income
            - spouse_income,
        )
    else:
        first_part = max(
            0, CAPITAL_GAIN_TAX_BRACKETS["single"][2].threshold - self_income
        )

    first_part = min(capital_gain, first_part)
    second_part = max(0, capital_gain - first_part)

    capital_gain_tax = (
        second_part * CAPITAL_GAIN_TAX_BRACKETS["single"][2].rate
        + first_part * CAPITAL_GAIN_TAX_BRACKETS["single"][1].rate
    )

    cash = (
        fy.salary
        + fy.vested_rsu
        + spouse_income
        + sum(e.cash() for e in events)
        - sum(e.cost() for e in events)
        - federal_income_tax
        - federal_amt_tax
        - capital_gain_tax
        - ca_income_tax
        - ca_amt_tax
    )
    return {
        "year": str(int(fy.month / 12 + 2020)),
        "cash": int(cash),
        "status": "married" if married else "single",
        "family_income": int(self_income + spouse_income),
        "capital_gain": int(capital_gain),
        "federal_income_tax": int(federal_income_tax),
        "ca_income_tax": int(ca_income_tax),
        "capital_gain_tax": int(capital_gain_tax),
        "federal_amt_tax": int(federal_amt_tax),
        "ca_amt_tax": int(ca_amt_tax),
    }


first = Event(3000, 15, "exercise", "iso")
second = Event(3377, 27, "exercise", "iso")
events = [
    first,
    second,
    Event(3000, 15 + 12, "sale", "iso", first.price),
    Event(20500, 30, "sale", "nso", FMV_AT_EXERCISE),
]

pd.DataFrame(
    [
        get_fy_projection(True, FYS[2], events[0:1]),
        get_fy_projection(False, FYS[2], events[0:1]),
        get_fy_projection(True, FYS[3], events[1:]),
        get_fy_projection(False, FYS[3], events[1:]),
    ]
)

# def get_average_price(events, low, needed):
#     balance = 0
#     total = 0
#     for event in events:
#         new_balance = min(balance + event.quantity, low + needed)
#         if new_balance > low:
#             total += event.price * (new_balance - max(low, balance))

#     return total / needed


# def get_max_cash():
#     ISOS = 6377
#     NSOS = 77000 - ISOS

#     early_exercise = Event(20500, 2, "exercise", "nso", FMV_AT_EXERCISE)
#     early_exercise.price = FMV_AT_EXERCISE
#     events = [early_exercise]
#     max_cash = 0
#     max_events = []
#     fy_events = []

#     def traverse(
#         current_month,
#         cash,
#     ):
#         nonlocal events, max_cash, max_events, fy_events
#         print(current_month, int(cash))

#         if current_month > TOTAL_MONTH:
#             if cash > max_cash:
#                 max_cash = cash
#                 max_events = events.copy()
#             return

#         if current_month % 12 == 0 and current_month // 12 > 1:
#             index = current_month // 12
#             fy_events.append("married")
#             traverse(
#                 current_month + 6,
#                 cash
#                 + get_fy_projection(
#                     True, FYS[index], [e for e in events if e.month > (index - 1) * 12]
#                 )["cash"],
#             )
#             fy_events.pop()

#             fy_events.append("single")
#             traverse(
#                 current_month + 6,
#                 cash
#                 + get_fy_projection(
#                     False, FYS[index], [e for e in events if e.month > (index - 1) * 12]
#                 )["cash"],
#             )
#             fy_events.pop()
#             return

#         percentages = [0.5, 1]

#         # do nothing this month
#         traverse(
#             current_month + 6,
#             cash,
#         )

#         options = []

#         iso_exercises = [
#             e
#             for e in events
#             if e.option_type == "iso"
#             and e.txn_type == "exercise"
#             and (current_month - e.month) >= 12
#         ]
#         iso_sales = [
#             e for e in events if e.option_type == "iso" and e.txn_type == "sale"
#         ]

#         unexercised_iso = ISOS - sum(e.quantity for e in iso_exercises)
#         if unexercised_iso > 0:
#             if unexercised_iso <= 1000:
#                 options.append(
#                     Event(unexercised_iso, current_month, "exercise", "iso", None)
#                 )
#             else:
#                 options += [
#                     Event(
#                         unexercised_iso * percentage,
#                         current_month,
#                         "exercise",
#                         "iso",
#                         None,
#                     )
#                     for percentage in percentages
#                 ]

#         exercised_iso = sum(e.quantity for e in iso_exercises) - sum(
#             e.quantity for e in iso_sales
#         )
#         if current_month >= 24 and exercised_iso > 0:
#             if exercised_iso <= 1000:
#                 avg = get_average_price(
#                     iso_exercises, sum(e.quantity for e in iso_sales), exercised_iso
#                 )
#                 options.append(Event(exercised_iso, current_month, "sale", "iso", avg))
#             else:
#                 options += [
#                     Event(
#                         exercised_iso * percentage,
#                         current_month,
#                         "sale",
#                         "iso",
#                         get_average_price(
#                             iso_exercises,
#                             sum(e.quantity for e in iso_sales),
#                             exercised_iso * percentage,
#                         ),
#                     )
#                     for percentage in percentages
#                 ]

#         nso_exercises = [
#             e
#             for e in events
#             if e.option_type == "nso"
#             and e.txn_type == "exercise"
#             and (current_month - e.month) >= 12
#         ]
#         nso_sales = [
#             e for e in events if e.option_type == "nso" and e.txn_type == "sale"
#         ]

#         unexercised_nso = NSOS - sum(e.quantity for e in nso_exercises)
#         if unexercised_nso > 0:
#             if unexercised_nso <= 1000:
#                 options.append(
#                     Event(unexercised_nso, current_month, "exercise", "nso", None)
#                 )
#             else:
#                 options += [
#                     Event(
#                         unexercised_nso * percentage,
#                         current_month,
#                         "exercise",
#                         "nso",
#                         None,
#                     )
#                     for percentage in percentages
#                 ]

#         exercised_nso = sum(e.quantity for e in nso_exercises) - sum(
#             e.quantity for e in nso_sales
#         )
#         if exercised_nso > 0:
#             if exercised_nso <= 1000:
#                 avg = get_average_price(
#                     nso_exercises, sum(e.quantity for e in nso_sales), exercised_nso
#                 )
#                 options.append(Event(exercised_nso, current_month, "sale", "nso", avg))
#             else:
#                 options += [
#                     Event(
#                         exercised_nso * percentage,
#                         current_month,
#                         "sale",
#                         "nso",
#                         get_average_price(
#                             nso_exercises,
#                             sum(e.quantity for e in nso_sales),
#                             exercised_nso * percentage,
#                         ),
#                     )
#                     for percentage in percentages
#                 ]

#         for event in options:
#             if cash + event.cash() - event.cost() < 0:
#                 continue

#             events.append(event)
#             traverse(current_month, cash + event.cash() - event.cost())
#             events.pop()

#     traverse(16, 0)
#     print(max_events)
#     return max_cash


# get_max_cash()
