from dotenv import load_dotenv
load_dotenv()

import logging
from web import start_web

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

if __name__ == "__main__":
    log.info("🌍 Secret Feeds Tweet Rewriter started.")
    start_web()
