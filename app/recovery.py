"""Recovery utilities for stuck pipeline runs."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.models import Run, RunStatus

logger = logging.getLogger(__name__)


def recover_stuck_runs(
    db: Session,
    timeout_minutes: Optional[int] = None
) -> int:
    """
    Recover runs stuck in intermediate states.

    A run is considered stuck if:
    - Status is SEARCHING, SCORING, CONTENT_GENERATING, or APPLYING
    - started_at is older than timeout_minutes
    - completed_at is None

    Args:
        db: Database session
        timeout_minutes: How long before run considered stuck (default from config)

    Returns:
        Number of runs recovered
    """
    if timeout_minutes is None:
        try:
            from app.config import config
            import yaml
            with open("config.yaml", "r") as f:
                yaml_config = yaml.safe_load(f) or {}
            recovery_config = yaml_config.get("pipeline", {}).get("recovery", {})
            timeout_minutes = recovery_config.get("timeout_minutes", 120)
        except Exception as e:
            logger.warning(f"Error loading recovery config, using default timeout: {e}")
            timeout_minutes = 120

    timeout = datetime.utcnow() - timedelta(minutes=timeout_minutes)

    stuck_runs = db.query(Run).filter(
        Run.status.in_([
            RunStatus.SEARCHING,
            RunStatus.SCORING,
            RunStatus.CONTENT_GENERATING,
            RunStatus.APPLYING
        ]),
        Run.started_at < timeout,
        Run.completed_at.is_(None)
    ).all()

    recovered_count = 0
    for run in stuck_runs:
        stuck_duration_minutes = (datetime.utcnow() - run.started_at).total_seconds() / 60
        logger.warning(
            f"Recovering stuck run {run.id}: "
            f"status={run.status.value}, started={run.started_at}, "
            f"stuck for {stuck_duration_minutes:.1f} minutes"
        )

        run.status = RunStatus.COMPLETED
        run.completed_at = datetime.utcnow()

        # Note in error_message that this was recovered
        if run.error_message:
            run.error_message = f"{run.error_message}; Recovered from stuck state"
        else:
            run.error_message = f"Recovered from stuck {run.status.value} state"

        recovered_count += 1

    if recovered_count > 0:
        db.commit()
        logger.info(f"Successfully recovered {recovered_count} stuck runs")

    return recovered_count
