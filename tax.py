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


def to_date(date_expr) -> datetime:
    return datetime.strptime(date_expr, "%b %d %Y")  # "Mar 21 2021"


st.title("2022 - 2025 Financial Planning")

STRIKE_PRICE = 15.68
FMV_AT_EXERCISE = 19.95

GRANT_DATE = to_date("Mar 19 2021")
MOVE_DATE = to_date("Feb 01 2022")
END_DATE = to_date("Mar 15 2025")

MOVE_DATE_PRICE = 60.0
END_DATE_PRICE = 140.0


class Event:
    def __init__(self, date: str, txn_type, option_type, quantity, exercise_price=None):
        self.option_type = option_type
        self.quantity = quantity
        self.date = to_date(date)
        self.price = round(
            (END_DATE_PRICE - MOVE_DATE_PRICE)
            * (self.date - MOVE_DATE).days
            / (END_DATE - MOVE_DATE).days
            + MOVE_DATE_PRICE,
            2,
        )
        self.txn_type = txn_type
        self.exercise_price = exercise_price

    def income(self):
        if self.option_type == "iso" or self.txn_type == "sale":
            return 0

        return (self.price - STRIKE_PRICE) * self.quantity

    def capital_gain(self):
        if "exercise" in self.txn_type:
            return 0

        if self.option_type == "iso":
            return (self.price - STRIKE_PRICE) * self.quantity

        return (self.price - self.exercise_price) * self.quantity

    def ca_ratio(self):
        if self.txn_type == "sale":
            return 0

        return (MOVE_DATE - GRANT_DATE).days * 1.0 / (self.date - GRANT_DATE).days

    def cost(self):
        return int(STRIKE_PRICE * self.quantity if "exercise" in self.txn_type else 0)

    def cash(self):
        return int(self.price * self.quantity if "sale" in self.txn_type else 0)

    def json(self):
        return {**self.__dict__, "cash": self.cash(), "cost": self.cost()}


class FY:
    def __init__(
        self,
        date: str,
        salary,
        spouse_salary,
        vested_rsu,
        spouse_vested_rsu,
    ):
        self.date = to_date(date)
        self.salary = salary
        self.spouse_salary = spouse_salary
        self.vested_rsu = vested_rsu
        self.spouse_vested_rsu = spouse_vested_rsu
        pass


FYS = {
    "2022": FY("Dec 31 2022", 238050, 127710 + 37500, 300000 * 9 / 48, 0),
    "2023": FY(
        "Dec 31 2023",
        238050,
        127710 * 1.1,
        300000 * (1 / 4 + 9 / 48),
        220000 * (1 / 4 + 3 / 16) + 90000 * (3 / 16),
    ),
    "2024": FY(
        "Dec 31 2024",
        238050,
        127710 * 1.1 * 1.1,
        300000 * (1 / 4 + 1 / 4 + 9 / 48),
        220000 * (1 / 4) + 90000 * (1 / 4 + 3 / 16),
    ),
}


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

    def get_niit_tax(self, amount):
        return self.get_tax(NIIT_TAX_BRACKETS, amount)

    def get_state_tax(self, amount):
        return self.get_tax(STATE_TAX_BRACKETS, amount)


def get_fy_projection(married, fy: FY, events: List[Event]):
    events = [e for e in events if e.date.year == fy.date.year]
    m = Model(married)

    self_income = fy.salary + fy.vested_rsu + sum(e.income() for e in events)

    # ignore 3 months of allocation for salary
    self_ca_income = sum(e.income() * e.ca_ratio() for e in events)
    if fy.date.year == 2022:
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
    ) + m.get_niit_tax(capital_gain)

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
        "year": str(fy.date.year),
        "cash": int(cash),
        "status": "married" if married else "single",
        "family_income": int(self_income + spouse_income),
        "capital_gain": int(capital_gain),
        "eff_tax_rate": round(
            (
                federal_income_tax
                + federal_amt_tax
                + capital_gain_tax
                + ca_income_tax
                + ca_amt_tax
            )
            / (self_income + spouse_income + capital_gain),
            2,
        ),
        "federal_income_tax": int(federal_income_tax),
        "ca_income_tax": int(ca_income_tax),
        "capital_gain_tax": int(capital_gain_tax),
        "federal_amt_tax": int(federal_amt_tax),
        "ca_amt_tax": int(ca_amt_tax),
    }


# first = Event(6377, 27, "exercise", "iso")

# nso_1st_exercise = Event(10000, 30, "exercise", "nso")
# nso_1st_sell = Event(10000, 30, "sale", "nso", nso_1st_exercise.price)

# nso_exercise = Event(10000, 40, "exercise", "nso")
# nso_sell = Event(10000, 40, "sale", "nso", nso_exercise.price)

# events = [
#     Event(10500, 18, "sale", "nso", FMV_AT_EXERCISE),
#     first,
#     Event(10000, 18 + 9, "sale", "nso", FMV_AT_EXERCISE),
#     nso_1st_exercise,
#     nso_1st_sell,
#     Event(6377, 27 + 12, "sale", "iso", first.price),
#     nso_exercise,
#     nso_sell,
# ]

# pd.DataFrame(
#     [
#         get_fy_projection(True, FYS[2], events),
#         get_fy_projection(False, FYS[2], events),
#         get_fy_projection(True, FYS[3], events),
#         get_fy_projection(False, FYS[3], events),
#         get_fy_projection(True, FYS[4], events),
#         get_fy_projection(False, FYS[4], events),
#     ]
# )

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
