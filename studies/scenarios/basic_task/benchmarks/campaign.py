"""./ariadne campaign studies/scenarios/basic_task/benchmarks/campaign.py — execuções independentes do mesmo cenário."""
from ariadne_sdk import Campaign

campaign = Campaign("../scenario.py", repeat=3, name="echo-repetitions")
