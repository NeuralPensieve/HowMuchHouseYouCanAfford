"""Monthly, nominal-dollar housing/retirement scenarios; no external dependencies.

Results are conditional projections, not retirement guarantees or lender approvals.
See README.md for timing, taxes, account-access and return assumptions.
"""

from dataclasses import dataclass
import math
from typing import Mapping, Optional, Sequence, Tuple


def _number(name, value, minimum=0.0, maximum=None, strict_minimum=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < minimum or (strict_minimum and value == minimum):
        raise ValueError(f"{name} must be {'greater than' if strict_minimum else 'at least'} {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be at most {maximum}")


def _integer(name, value, minimum):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _monthly_rate(annual_return):
    return math.expm1(math.log1p(annual_return) / 12)


def _gross_withdrawal(net_cash, tax_rate):
    return net_cash / (1 - tax_rate)


def to_today_dollars(amount, month, inflation_rate):
    """Convert a nominal amount at an elapsed month to purchase-date purchasing power."""
    return amount / (1 + inflation_rate) ** (month / 12)


def _rebalance_reserve(investments, cash, required_cash, tax_rate):
    """Cash earns zero; investment withdrawals pay the supplied effective tax."""
    change = required_cash - cash
    if change > 0:
        investments -= _gross_withdrawal(change, tax_rate)
    else:
        investments -= change
    return investments, required_cash


@dataclass(frozen=True)
class Economy:
    investmentReturn: float  # Nominal annual return, net of fees and annual tax drag.
    interest_rate: float  # Contractual annual mortgage interest rate, NOT APR.
    realEstateTax: float
    insuranceRatio: float
    inflation_rate: float = 0.025
    income_growth_rate: float = 0.025  # Nominal growth of AFTER-tax income.
    housing_cost_growth_rate: Optional[float] = None  # Defaults to inflation.
    mortgage_interest_tax_benefit: float = 0.0  # Actual incremental benefit / interest.

    def __post_init__(self):
        for name in ("investmentReturn", "inflation_rate", "income_growth_rate"):
            _number(name, getattr(self, name), -1, strict_minimum=True)
        if self.housing_cost_growth_rate is not None:
            _number("housing_cost_growth_rate", self.housing_cost_growth_rate, -1, strict_minimum=True)
        for name in ("interest_rate", "realEstateTax", "insuranceRatio"):
            _number(name, getattr(self, name))
        _number("mortgage_interest_tax_benefit", self.mortgage_interest_tax_benefit, 0, 1)


@dataclass(frozen=True)
class House:
    price: float
    economy: Economy
    down_payment_ratio: float = 0.2
    loan_years: int = 30
    maintenance_cost_ratio: float = 0.01
    closing_cost_ratio: float = 0.04  # Fraction of purchase price, separate from down payment.
    hoa_annual: float = 0.0
    utilities_annual: float = 0.0
    mortgage_insurance_annual: Optional[float] = None
    mortgage_insurance_months: int = 0  # Explicit loan-specific duration; no LTV guess.

    def __post_init__(self):
        _number("price", self.price, 0, strict_minimum=True)
        _number("down_payment_ratio", self.down_payment_ratio, 0, 1)
        _integer("loan_years", self.loan_years, 1)
        for name in ("maintenance_cost_ratio", "closing_cost_ratio", "hoa_annual", "utilities_annual"):
            _number(name, getattr(self, name))
        _integer("mortgage_insurance_months", self.mortgage_insurance_months, 0)
        if self.mortgage_insurance_annual is None and self.down_payment_ratio < 0.2:
            raise ValueError("Specify mortgage_insurance_annual for <20% down (0 if exempt)")
        if self.mortgage_insurance_annual is not None:
            _number("mortgage_insurance_annual", self.mortgage_insurance_annual)
        if bool(self.mortgage_insurance_annual) != bool(self.mortgage_insurance_months):
            raise ValueError("Positive mortgage insurance requires a positive duration, and vice versa")
        if self.mortgage_insurance_months > 12 * self.loan_years:
            raise ValueError("Mortgage insurance duration cannot exceed the loan term")

    @property
    def down_payment(self):
        return self.price * self.down_payment_ratio

    @property
    def closing_costs(self):
        return self.price * self.closing_cost_ratio

    @property
    def initial_loan(self):
        return self.price - self.down_payment

    @property
    def monthly_payment(self):
        if self.initial_loan == 0:
            return 0.0
        rate = self.economy.interest_rate / 12
        months = 12 * self.loan_years
        if rate == 0:
            return self.initial_loan / months
        return self.initial_loan * rate / -math.expm1(-months * math.log1p(rate))

    def ongoing_monthly_cost(self, month):
        """Taxes, insurance, maintenance, HOA, utilities survive mortgage payoff."""
        annual = self.price * (self.economy.realEstateTax + self.economy.insuranceRatio
                               + self.maintenance_cost_ratio) + self.hoa_annual + self.utilities_annual
        growth = self.economy.housing_cost_growth_rate
        if growth is None:
            growth = self.economy.inflation_rate
        return annual / 12 * (1 + growth) ** (month / 12)

    def mortgage_insurance(self, month, balance):
        if balance > 0 and month < self.mortgage_insurance_months:
            return (self.mortgage_insurance_annual or 0.0) / 12
        return 0.0

    def scheduled_payment(self, balance):
        """Return payment and interest; cap the final payment at the amount owed."""
        interest = balance * self.economy.interest_rate / 12
        return min(self.monthly_payment, balance + interest), interest


@dataclass(frozen=True)
class Strategy:
    name: str
    extra_payment_fraction: float  # Fraction of surplus, after reserve top-ups.

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("A strategy needs a nonempty name")
        _number("extra_payment_fraction", self.extra_payment_fraction, 0, 1)


DEFAULT_STRATEGIES = (
    Strategy("Invest surplus", 0.0),
    Strategy("Split surplus 50/50", 0.5),
    Strategy("Prepay mortgage", 1.0),
)


@dataclass(frozen=True)
class Affordability:
    affordable: bool
    reasons: Tuple[str, ...]
    required_initial_assets: float
    initial_cash_reserve: float
    initial_monthly_surplus: float


@dataclass(frozen=True)
class RetirementScenario:
    name: str
    funded: bool
    ending_investments: float
    ending_cash_reserve: float
    months_funded: int


@dataclass(frozen=True)
class Snapshot:
    month: int
    investments: float
    cash_reserve: float
    mortgage_balance: float
    interest_paid: float  # Cumulative nominal dollars, not present value.
    mortgage_free_annual_spending: float
    gross_payoff_withdrawal: float
    investments_after_payoff: float  # Also adjusts to the mortgage-free cash reserve.
    spending_target: float  # Includes withdrawal taxes, excludes cash reserve.


@dataclass(frozen=True)
class AnnualRow:
    # Amounts use the dollar basis selected by annual_report(today_dollars=...).
    month: int  # Elapsed months at the end of the period.
    months_in_period: int
    liquid_assets: float  # Investments + cash, before settling the mortgage.
    liquid_net_worth: float  # Liquid assets minus remaining mortgage principal.
    total_net_worth: float  # Liquid net worth + home at purchase price.
    total_expenses: float  # Actual period cash outflows, including required mortgage payments.
    mortgage_balance: float


@dataclass(frozen=True)
class Projection:
    strategy: Strategy
    status: str
    months_to_retirement: Optional[int]
    affordability: Affordability
    history: Tuple[Snapshot, ...]
    retirement_scenarios: Tuple[RetirementScenario, ...]

    @property
    def years_to_retirement(self):
        return None if self.months_to_retirement is None else self.months_to_retirement / 12


@dataclass(frozen=True)
class Buyer:
    assets: float  # Accessible investment market value; see the effective-tax convention.
    yearlyIncomeAfterTax: float
    yearlyExpensesWithoutHouse: float
    withdrawalRate: float = 0.04
    emergency_fund_months: float = 0.0  # Optional; no reserve assumption unless requested.
    minimum_monthly_surplus: float = 0.0
    effective_withdrawal_tax_rate: float = 0.0
    retirement_yearly_expenses_without_house: Optional[float] = None  # Today's dollars.

    def __post_init__(self):
        for name in ("assets", "yearlyIncomeAfterTax", "yearlyExpensesWithoutHouse",
                     "emergency_fund_months", "minimum_monthly_surplus"):
            _number(name, getattr(self, name))
        _number("withdrawalRate", self.withdrawalRate, 0, 1, strict_minimum=True)
        _number("effective_withdrawal_tax_rate", self.effective_withdrawal_tax_rate, 0, 1)
        if self.effective_withdrawal_tax_rate == 1:
            raise ValueError("effective_withdrawal_tax_rate must be less than 1")
        if self.retirement_yearly_expenses_without_house is not None:
            _number("retirement_yearly_expenses_without_house", self.retirement_yearly_expenses_without_house)

    def monthly_spending(self, house, month, retirement=False):
        other = self.yearlyExpensesWithoutHouse
        if retirement and self.retirement_yearly_expenses_without_house is not None:
            other = self.retirement_yearly_expenses_without_house
        return (other / 12 * (1 + house.economy.inflation_rate) ** (month / 12)
                + house.ongoing_monthly_cost(month))

    def _working_reserve(self, house, month, balance):
        payment, _ = house.scheduled_payment(balance)
        return self.emergency_fund_months * (self.monthly_spending(house, month)
                   + payment + house.mortgage_insurance(month, balance))

    def assess_affordability(self, house):
        reserve = self._working_reserve(house, 0, house.initial_loan)
        required = _gross_withdrawal(house.down_payment + house.closing_costs + reserve,
                                     self.effective_withdrawal_tax_rate)
        payment, interest = house.scheduled_payment(house.initial_loan)
        surplus = (self.yearlyIncomeAfterTax / 12
                   + interest * house.economy.mortgage_interest_tax_benefit
                   - self.monthly_spending(house, 0) - payment
                   - house.mortgage_insurance(0, house.initial_loan))
        reasons = []
        if self.assets < required:
            reasons.append("Insufficient accessible assets for down payment, closing costs, taxes and cash reserve")
        if surplus < self.minimum_monthly_surplus:
            reasons.append("Initial monthly surplus is below the requested savings buffer")
        return Affordability(not reasons, tuple(reasons), required, reserve, surplus)

    def _snapshot(self, house, month, investments, cash, balance, interest_paid):
        spending = self.monthly_spending(house, month, retirement=True)
        adjusted, _ = _rebalance_reserve(investments, cash,
                      self.emergency_fund_months * spending, self.effective_withdrawal_tax_rate)
        payoff = _gross_withdrawal(balance, self.effective_withdrawal_tax_rate)
        target = _gross_withdrawal(spending * 12, self.effective_withdrawal_tax_rate) / self.withdrawalRate
        return Snapshot(month, investments, cash, balance, interest_paid, spending * 12,
                        payoff, adjusted - payoff, target)

    def _test_retirement(self, house, snapshot, name, returns):
        investments = snapshot.investments_after_payoff
        cash = self.emergency_fund_months * snapshot.mortgage_free_annual_spending / 12
        for elapsed in range(len(returns) * 12):
            spending = self.monthly_spending(house, snapshot.month + elapsed, retirement=True)
            investments, cash = _rebalance_reserve(investments, cash,
                self.emergency_fund_months * spending, self.effective_withdrawal_tax_rate)
            withdrawal = _gross_withdrawal(spending, self.effective_withdrawal_tax_rate)
            if investments < withdrawal:
                return RetirementScenario(name, False, investments, cash, elapsed)
            # Retirement withdrawals occur at the START of the month; reserves stay intact.
            investments = (investments - withdrawal) * (1 + _monthly_rate(returns[elapsed // 12]))
        return RetirementScenario(name, True, investments, cash, len(returns) * 12)

    def project(self, house, strategy=DEFAULT_STRATEGIES[0], *, max_work_years=60,
                retirement_years=40, retirement_scenarios: Optional[Mapping[str, Sequence[float]]] = None,
                accumulation_returns: Optional[Sequence[float]] = None):
        """Find the first month meeting the mortgage-free spending target.

        Optional retirement paths add a stress check ONLY when explicitly supplied.
        Paths restart at each candidate date; they are not probabilities/backtests.
        """
        _integer("max_work_years", max_work_years, 0)
        _integer("retirement_years", retirement_years, 1)
        scenarios = ({} if retirement_scenarios is None else
                     {k: tuple(v) for k, v in retirement_scenarios.items()})
        if retirement_scenarios is not None and not scenarios:
            raise ValueError("Supply at least one retirement scenario")
        accumulation = ((house.economy.investmentReturn,) * max_work_years
                        if accumulation_returns is None else tuple(accumulation_returns))
        if len(accumulation) != max_work_years:
            raise ValueError("accumulation_returns must cover exactly max_work_years")
        for name, path in scenarios.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Scenarios need nonempty names")
            if len(path) != retirement_years:
                raise ValueError("Each retirement scenario must cover exactly retirement_years")
        for path in list(scenarios.values()) + [accumulation]:
            for annual_return in path:
                _number("scenario return", annual_return, -1, strict_minimum=True)

        affordability = self.assess_affordability(house)
        if not affordability.affordable:
            return Projection(strategy, "purchase_not_affordable", None, affordability, (), ())
        investments = self.assets - affordability.required_initial_assets
        cash = affordability.initial_cash_reserve
        balance = house.initial_loan
        history = []
        interest_paid = 0.0
        last_tests = ()

        for month in range(max_work_years * 12 + 1):
            snapshot = self._snapshot(house, month, investments, cash, balance, interest_paid)
            history.append(snapshot)
            last_tests = ()
            if snapshot.investments_after_payoff >= snapshot.spending_target:
                last_tests = tuple(self._test_retirement(house, snapshot, name, path)
                                   for name, path in scenarios.items())
                if all(result.funded for result in last_tests):
                    status = "scenario_target_reached" if scenarios else "spending_target_reached"
                    return Projection(strategy, status, month, affordability,
                                      tuple(history), last_tests)
            if month == max_work_years * 12:
                break

            # Work-month order: growth, income/costs, reserve top-up,
            # extra principal, contribution. Saved income grows next month.
            investments *= 1 + _monthly_rate(accumulation[month // 12])
            payment, interest = house.scheduled_payment(balance)
            income = self.yearlyIncomeAfterTax / 12 * (1 + house.economy.income_growth_rate) ** (month / 12)
            surplus = (income + interest * house.economy.mortgage_interest_tax_benefit
                       - self.monthly_spending(house, month) - payment
                       - house.mortgage_insurance(month, balance))
            balance = max(0.0, balance + interest - payment)
            interest_paid += interest
            next_reserve = self._working_reserve(house, month + 1, balance)
            top_up = min(max(surplus, 0.0), max(next_reserve - cash, 0.0))
            cash += top_up
            surplus -= top_up
            extra = min(balance, max(surplus, 0.0) * strategy.extra_payment_fraction)
            balance -= extra
            # Floating arithmetic can leave a fraction of a cent at contractual payoff.
            if balance < 1e-6:
                balance = 0.0
            if surplus >= 0:
                investments += surplus - extra
            else:
                investments -= _gross_withdrawal(-surplus, self.effective_withdrawal_tax_rate)
            investments, cash = _rebalance_reserve(investments, cash,
                self._working_reserve(house, month + 1, balance), self.effective_withdrawal_tax_rate)
            if investments < 0:
                history.append(self._snapshot(house, month + 1, investments, cash, balance, interest_paid))
                return Projection(strategy, "cash_reserve_shortfall", None, affordability, tuple(history), ())

        return Projection(strategy, "target_not_reached_within_horizon", None, affordability,
                          tuple(history), last_tests)

    def compare_strategies(self, house, strategies=DEFAULT_STRATEGIES, **projection_options):
        return tuple(self.project(house, strategy, **projection_options) for strategy in strategies)

    def annual_report(self, house, projection, *, today_dollars=False):
        """Summarize regular-payment history at purchase, yearly, and the final month.

        Liquid net worth deducts the mortgage once; total net worth then adds the
        home at its purchase price (no assumed appreciation). Expenses are cash
        outflows for the elapsed period, not a future annual spending estimate.
        The retirement balloon payoff is separate, not hidden in recurring costs.
        In today's-dollar mode, balances use period-end CPI. Expense flows are
        deflated individually at the month used to price them, then summed.
        This changes reporting only, never the projection or retirement date.
        """
        if not isinstance(today_dollars, bool):
            raise ValueError("today_dollars must be True or False")
        if projection.strategy.extra_payment_fraction != 0:
            raise ValueError("Annual report expects regular payments and no extra principal")
        def amount(value, month):
            return (to_today_dollars(value, month, house.economy.inflation_rate)
                    if today_dollars else value)
        rows = []
        expenses = 0.0
        period_start = 0
        last_month = projection.history[-1].month if projection.history else 0
        for index, snapshot in enumerate(projection.history):
            if index:
                previous = projection.history[index - 1]
                payment, _ = house.scheduled_payment(previous.mortgage_balance)
                monthly_expenses = (self.monthly_spending(house, previous.month) + payment
                                    + house.mortgage_insurance(previous.month, previous.mortgage_balance))
                expenses += amount(monthly_expenses, previous.month)
            if snapshot.month == 0 or snapshot.month % 12 == 0 or snapshot.month == last_month:
                liquid_assets = snapshot.investments + snapshot.cash_reserve
                liquid_net = liquid_assets - snapshot.mortgage_balance
                rows.append(AnnualRow(snapshot.month, snapshot.month - period_start,
                    amount(liquid_assets, snapshot.month), amount(liquid_net, snapshot.month),
                    amount(liquid_net + house.price, snapshot.month),
                    expenses, amount(snapshot.mortgage_balance, snapshot.month)))
                expenses = 0.0
                period_start = snapshot.month
        return tuple(rows)
