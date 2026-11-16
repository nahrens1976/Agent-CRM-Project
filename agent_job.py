"""Railway cron entry point. It drafts follow-ups only; it never sends email."""
from app import run_follow_up_agent

if __name__ == "__main__":
    created = run_follow_up_agent()
    print(f"Created {created} follow-up draft(s) for human review.")

