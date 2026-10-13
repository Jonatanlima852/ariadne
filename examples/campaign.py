"""./tg campaign examples/campaign.py — execuções independentes do mesmo cenário."""
from tg_sdk import Campaign

campaign = Campaign("echo.py", repeat=3, name="echo-repetitions")
