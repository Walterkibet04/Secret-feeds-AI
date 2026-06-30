from dotenv import load_dotenv
load_dotenv()

import schedule
import time
import logging
from fetcher import fetch_headlines
from generator import generate_drafts
from mailer import send_email
from web import run_web_in_background, store_drafts

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


def run():
    log.info("── Secret Feeds cycle starting ──")
    try:
        headlines = fetch_headlines()
        if not headlines:
            log.warning("No fresh headlines this cycle — skipping.")
            return

        log.info(f"Fetched {len(headlines)} headlines. Generating drafts...")
        drafts = generate_drafts(headlines)

        if not drafts:
            log.warning("No drafts generated.")
            return

        # Store in web UI (always works)
        store_drafts(drafts)

        # Send email (may fail on some platforms — UI is the backup)
        try:
            send_email(drafts)
        except Exception as e:
            log.warning(f"Email failed: {e} — drafts still visible in web UI")

        log.info(f"✅ {len(drafts)} drafts ready — check web UI or email")

    except Exception as e:
        log.error(f"Cycle failed: {e}")


if __name__ == "__main__":
    log.info("🌍 Secret Feeds Bot started — running every 30 minutes.")
    log.info("🌐 Starting web interface...")

    run_web_in_background()
    run()

    schedule.every(30).minutes.do(run)

    log.info("Scheduler active. Next cycle in 30 minutes...")
    while True:
        schedule.run_pending()
        time.sleep(30)
