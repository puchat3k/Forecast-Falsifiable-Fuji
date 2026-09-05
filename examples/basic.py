from datetime import datetime, timezone
from forecast_fuji import Fuji

fuji = Fuji(":memory:")
experiment = fuji.create_experiment(
    "Launch forecast",
    mode="SHADOW",
    hypothesis="Independent pre-action forecasts beat a simple 50% baseline.",
)
case = fuji.create_case(experiment, "launch-001", datetime.now(timezone.utc).isoformat())
prop = fuji.add_proposition(
    case,
    "SUCCESS_30D",
    "The launch will reach the predefined success threshold within 30 days.",
    "30D",
    "Resolve TRUE iff the threshold defined in case metadata is met by day 30.",
)
fuji.add_baseline(prop, "NAIVE_50", 0.50, derivation="Uninformative baseline")
fuji.add_forecast(prop, "GENERALIST", 0.64, evidence_basis="Base rate plus current traction")
fuji.add_forecast(prop, "DOMAIN", 0.71, evidence_basis="Product-specific signals")
fuji.add_forecast(prop, "REDTEAM", 0.49, evidence_basis="Execution and distribution risks")
print(fuji.lock_case(case))
print(fuji.resolve(prop, True))
print(fuji.leaderboard(experiment))
