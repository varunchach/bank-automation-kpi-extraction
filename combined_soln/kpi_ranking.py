"""KPI Ranking — higher vs lower is better."""

LOWER_IS_BETTER = {
    "Gross_NPA_Pct", "Net_NPA_Pct", "Gross_NPA_Amount", "Net_NPA_Amount",
    "Cost_of_Deposits", "Cost_to_Income_Ratio", "Other_Expenditure",
}

def get_rank_direction(kpi_key: str) -> str:
    return "lower" if kpi_key in LOWER_IS_BETTER else "higher"

def compute_rank(values: list, kpi_key: str) -> list:
    higher_better = get_rank_direction(kpi_key) == "higher"
    indexed = [(i, v) for i, v in enumerate(values)]
    def sort_key(item):
        i, v = item
        if v is None:
            return (1, 0, i)
        return (0, -v if higher_better else v, i)
    indexed.sort(key=sort_key)
    ranks = [0] * len(values)
    for rank, (i, _) in enumerate(indexed, start=1):
        ranks[i] = rank
    return ranks
