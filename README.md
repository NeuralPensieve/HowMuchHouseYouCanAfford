# HowMuchHouseYouCanAfford

Set the house price, available assets, take-home income, expenses and economic
assumptions. The notebook reports year-by-year finances while making only regular
mortgage payments, investing all surplus, and paying off the remaining principal
at retirement. There is no strategy-comparison table.

## Use it

Open `HowMuchHouseYouCanAfford.ipynb`, edit the input cell, then run all cells.
After a calculation-code update, restart the kernel before running all cells.
Your financial inputs are preserved when updating the report. All initial money
inputs are today's dollars; annual rates are decimals.

Set `show_today_dollars = True` (the notebook default) to display today's
purchasing power. Set it to `False` for nominal amounts at each future date.
This only changes the report, not the calculation or retirement date.

| Input | Meaning |
| --- | --- |
| `assets` | Available investments before down payment and closing costs; exclude home equity and inaccessible accounts |
| `yearlyIncomeAfterTax` | Annual take-home income before living/housing expenses |
| `yearlyExpensesWithoutHouse` | Annual nonhousing budget, reused in retirement; exclude rent that will stop |
| `withdrawalRate` | Annual withdrawals / invested retirement balance; 3% means a target of 33.3 times annual spending |
| `investmentReturn` | Assumed nominal annual investment growth, net of fees and annual tax drag |
| `interest_rate` | Contractual fixed annual mortgage interest rate, not APR |
| `inflation_rate` | Annual growth of living costs and, by default, ongoing home costs |
| `income_growth_rate` | Annual growth of take-home income; 0 means fixed nominal income |
| `realEstateTax`, `insuranceRatio` | Starting annual property tax and homeowners insurance as fractions of house price |
| `down_payment_ratio` | Fraction of house price paid from starting assets |
| `closing_cost_ratio` | Fraction of house price paid for closing; default 4% |
| `maintenance_cost_ratio` | Starting annual maintenance budget / house price |
| `loan_years` | Original mortgage term |

## Reading the annual report

| Column | Definition |
| --- | --- |
| Period end | At purchase, each completed year, and any final partial year |
| Liquid assets | Investments plus cash, excluding the house; mortgage has not yet been deducted |
| Liquid net worth | Liquid assets minus remaining mortgage principal, before any additional liquidation tax |
| Total net worth | Includes the home, held at purchase price before converting to the selected dollar basis; no appreciation is assumed |
| Total expenses in period | Actual living costs, ongoing home costs and required mortgage principal/interest paid during the elapsed period |
| Principal remaining | Loan capital still owed at that period's end |

Annual expenses include property taxes, homeowners insurance, maintenance and
any configured HOA, utilities or mortgage insurance. Principal repayment is a cash
outflow, not consumption: it reduces the loan and builds equity. The expense
column describes these household cash outflows, not income taxes (income is
already after tax) or any optional tax on investment withdrawals.

Down payment and closing costs are shown separately above the table. The
purchase row is after those payments, with zero elapsed-period expenses. The last
working row may cover fewer than 12 months and is labeled accordingly; its
expenses are not annualized. They are not the same as the forward annual
mortgage-free spending budget printed at retirement.

The report shows the final mortgage payoff separately and then adds an
**After retirement payoff** balance row. The payoff is not counted as a recurring
annual expense. With no withdrawal taxes, liquid assets fall by the principal
paid, debt falls by the same amount, and both net-worth measures are unchanged.

## Monthly calculation and retirement rule

The underlying projection always uses nominal dollars. For today's-dollar
reporting, each balance, mortgage payoff and retirement-summary amount is divided
by `(1 + inflation_rate) ** (elapsed_months / 12)`. Annual expenses are converted
one monthly payment at a time using the month used to price each payment, then
summed. They are not divided by a single year-end inflation factor. The nominal
house value is still fixed at purchase price, so its real value declines; the
display option does not introduce an appreciation assumption.

For example, $5 million in 21.5 years at 3.5% inflation is about $2.39 million in
today's purchasing power. `investmentReturn` remains nominal in either view.

Each month, existing investments earn their monthly return. Take-home income pays
living expenses, ongoing home costs and the required mortgage payment. All surplus
is invested, starting to earn returns the following month. No extra principal is
paid before retirement. If the mortgage reaches its normal maturity first, its
payments stop and the freed money is invested.

The mortgage formula uses annual interest / 12 and loan years * 12. It supports
a zero-interest loan and caps the final payment. Internal calculations are not
rounded; a balance under $0.000001 is treated as zero.

At each month boundary:

```text
investments after final payoff = investments - remaining mortgage principal
annual mortgage-free expenses = living expenses + ongoing home costs
required investments = annual mortgage-free expenses / withdrawalRate
```

The report stops at the first month when investments after payoff meet the target.
It does not project future retirement years. Property taxes, homeowners insurance
and maintenance continue in the target; mortgage payments do not. Home equity is
included in total net worth but never used to fund retirement spending.

There is a 60-year search limit. If the purchase cannot be funded, the report
explains why. Optional tax/reserve settings below adjust the basic formulas.

## Inflation and assumptions

Inflation increases expenses; income grows at its separately specified rate.
The contractual mortgage payment stays fixed. Do not subtract inflation from
`investmentReturn` too: 7% nominal growth with 2.5% inflation implies about
4.39% real growth.

The basic notebook assumes no extra emergency reserve, minimum savings buffer,
withdrawal tax or mortgage-interest tax benefit. It reuses the same nonhousing
budget in retirement. Actual taxes and unexpected costs can change the outcome.
The return and withdrawal rate are planning assumptions, not guarantees.

The model assumes a fixed-rate fully amortizing loan, no prepayment penalties,
refinancing, recasts, Social Security, pension, sale or downsizing. Maintenance is
a smooth budget rather than irregular repair bills. It is not a lender
qualification calculation.

## Optional code settings

These are not required by the notebook:

- `emergency_fund_months`: default 0; optional separate cash reserve that earns
  zero and grows with its required spending coverage.
- `minimum_monthly_surplus`: default 0; optional initial purchase savings buffer.
- `effective_withdrawal_tax_rate`: default 0; a uniform tax haircut on investment
  withdrawals for purchase/reserve funding, shortfalls, mortgage payoff and
  retirement spending. It does not track basis, brackets or account types.
- `retirement_yearly_expenses_without_house`: default None, reusing the working
  budget. If supplied, enter today's dollars; inflation is applied automatically.
- `housing_cost_growth_rate`: defaults to inflation; optionally use a different
  growth rate for home costs.
- `mortgage_interest_tax_benefit`: default 0; actual incremental tax savings per
  dollar of interest, not automatically your tax bracket.
- `hoa_annual`, `utilities_annual`: optional annual home budgets. Do not include
  the same costs in the nonhousing budget too.
- `mortgage_insurance_annual`, `mortgage_insurance_months`: loan-specific premium
  and duration, stopping earlier at payoff. Below 20% down, explicitly supply
  a premium (0 if exempt); a positive premium requires a positive duration.
- `retirement_scenarios`: optional explicit return paths with `retirement_years`;
  these add a spending-through-retirement check only when explicitly supplied.
  With None (the default), there is no retirement-path check. Paths restart at
  each candidate date and are not probabilities or historical backtests.
- `accumulation_returns`: optional annual working-year returns covering exactly
  `max_work_years`; otherwise `investmentReturn` is used throughout accumulation.

## Code and validation

`House` calculates costs and mortgage payments; `Buyer.project()` tracks monthly
cash flows and the retirement target; `Buyer.compare_strategies()` runs independent
strategies. Inputs are immutable, so repeated comparisons start with the same
assets. Results include a monthly history for inspecting the calculations.

The original `APR` argument became `interest_rate`; the original print-and-mutate
retirement method was replaced by `project()` and `compare_strategies()`.

Run checks with `python3 -m unittest -v`. The calculation module uses only the
Python standard library. The notebook uses IPython to display its report table.
