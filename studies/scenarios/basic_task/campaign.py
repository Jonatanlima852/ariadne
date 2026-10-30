"""./ariadne campaign studies/scenarios/basic_task/campaign.py — três execuções independentes do eco."""
from ariadne_sdk import Campaign

campaign = Campaign("scenario.py", repeat=3, name="echo-repetitions")
