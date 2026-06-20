import logging
import time

from app.config import get_settings
from app.database import SessionLocal, create_all
from app.services.scheduler import execute_due_call, get_due_calls
from app.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)


def run_once() -> int:
    settings = get_settings()
    twilio = TwilioService(settings)
    processed = 0
    with SessionLocal() as db:
        for call in get_due_calls(db):
            execute_due_call(db, settings, twilio, call)
            processed += 1
    return processed


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    create_all()
    logger.info("WhatsApp call worker started")
    while True:
        processed = run_once()
        if processed:
            logger.info("Processed %s scheduled call(s)", processed)
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
