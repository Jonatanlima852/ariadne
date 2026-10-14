"""./ariadne campaign examples/campaign.py — execuções independentes do mesmo cenário."""
from ariadne_sdk import Campaign

campaign = Campaign("echo.py", repeat=3, name="echo-repetitions")
