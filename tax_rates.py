class TaxRate:
    def __init__(self, threshold, rate):
        self.threshold = threshold
        self.rate = rate / 100


DEDUCTION = {"single": 12950, "married": 25900}


INCOME_TAX_BRACKETS = {
    "married": [
        TaxRate(0, 10),
        TaxRate(20550, 12),
        TaxRate(83550, 22),
        TaxRate(178150, 24),
        TaxRate(340100, 32),
        TaxRate(431900, 35),
        TaxRate(647850, 37),
    ],
    "single": [
        TaxRate(0, 10),
        TaxRate(10275, 12),
        TaxRate(41775, 22),
        TaxRate(89075, 24),
        TaxRate(170050, 32),
        TaxRate(215950, 35),
        TaxRate(539900, 37),
    ],
}


AMT_TAX_BRACKETS = {
    "married": [
        TaxRate(0, 0),
        TaxRate(118100, 26),
        TaxRate(118100 + 206100, 28),
    ],
    "single": [
        TaxRate(0, 0),
        TaxRate(75900, 26),
        TaxRate(118100 + 206100, 28),
    ],
}

CA_AMT_TAX_BRACKETS = {
    "married": [
        TaxRate(0, 0),
        TaxRate(0, 7),
    ],
    "single": [
        TaxRate(0, 0),
        TaxRate(0, 7),
    ],
}

CAPITAL_GAIN_TAX_BRACKETS = {
    "married": [
        TaxRate(0, 0),
        TaxRate(80801, 15),
        TaxRate(501601, 20),
    ],
    "single": [TaxRate(0, 0), TaxRate(40401, 15), TaxRate(445851, 20)],
}

SOCIAL_SECURITY_TAX_BRACKETS = {
    "married": [TaxRate(0, 6.2), TaxRate(147000, 0)],
    "single": [TaxRate(0, 6.2), TaxRate(147000, 0)],
}

MEDICARE_TAX_BRACKETS = {
    "married": [TaxRate(0, 1.45), TaxRate(250000, 2.35)],
    "single": [TaxRate(0, 1.45), TaxRate(200000, 2.35)],
}

NIIT_TAX_BRACKETS = {
    "married": [TaxRate(0, 3.8)],
    "single": [TaxRate(0, 3.8)],
}

STATE_TAX_BRACKETS = {
    "married": [
        TaxRate(0, 1),
        TaxRate(18651, 2),
        TaxRate(44215, 4),
        TaxRate(69785, 6),
        TaxRate(96871, 8),
        TaxRate(122429, 9.3),
        TaxRate(625373, 10.3),
        TaxRate(750443, 11.3),
        TaxRate(1259739, 12.3),
    ],
    "single": [
        TaxRate(0, 1),
        TaxRate(9325, 2),
        TaxRate(22108, 4),
        TaxRate(34893, 6),
        TaxRate(48436, 8),
        TaxRate(61215, 9.3),
        TaxRate(312687, 10.3),
        TaxRate(375222, 11.3),
        TaxRate(625370, 12.3),
    ],
}
