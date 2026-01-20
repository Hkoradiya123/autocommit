import logging
import time
import random
import argparse
import sys
from datetime import datetime, timezone, timedelta
from git import InvalidGitRepositoryError, NoSuchPathError, GitCommandError, Repo
from pathlib import Path

# Configuration
REPO_ROOT = Path(__file__).resolve().parent
FILE_TO_COMMIT = REPO_ROOT / "update_me.yaml"
LOG_FILE = REPO_ROOT / "git_commit.log"
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def write_current_time():
    """Write the current UTC time to the file."""
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        FILE_TO_COMMIT.write_text(f"LAST_UPDATE: {ts}\n")
        logger.info(f"Updated {FILE_TO_COMMIT} with timestamp {ts}")
        return ts
    except Exception as e:
        logger.error(f"Failed to write timestamp: {e}")
        return None


def push_with_retry(repo, max_retries=MAX_RETRIES):
    """Push to remote with retry logic for transient failures."""
    for attempt in range(1, max_retries + 1):
        try:
            repo.remote("origin").push()
            logger.info("Push to origin succeeded")
            return True
        except GitCommandError as e:
            if attempt < max_retries:
                logger.warning(f"Push failed (attempt {attempt}/{max_retries}): {e}. Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Push failed after {max_retries} attempts: {e}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error during push: {e}")
            return False
    return False


def commit_repo(ts):
    """Commit and push the timestamp update with retry logic."""
    if not ts:
        logger.warning("No timestamp provided, skipping commit.")
        return False
    
    try:
        repo = Repo(REPO_ROOT)
    except (InvalidGitRepositoryError, NoSuchPathError) as e:
        logger.error(f"No git repo found at {REPO_ROOT}: {e}")
        return False
    
    try:
        # Stage and commit
        repo.index.add([str(FILE_TO_COMMIT)])
        commit_obj = repo.index.commit(f"Auto commit at {ts}")
        logger.info(f"Created commit {commit_obj.hexsha[:7]}")
        
        # Push with retry logic
        return push_with_retry(repo, max_retries=MAX_RETRIES)
    
    except GitCommandError as e:
        logger.error(f"Git command failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during commit: {e}")
        return False


def run_once():
    """Execute one commit cycle."""
    logger.info("Starting commit cycle...")
    timestamp = write_current_time()
    success = commit_repo(timestamp)
    logger.info(f"Commit cycle completed. Status: {'SUCCESS' if success else 'FAILED'}")
    return success


def get_random_schedule(min_commits=3, max_commits=6):
    """Generate random future times for commits within the next 24 hours."""
    now = datetime.now()
    end_of_day = now.replace(hour=23, minute=59, second=59)
    
    # Logic: Pick N random seconds from now until end of day
    # If end of day is too close, plan for tomorrow? 
    # For simplicity, let's just pick times in the next 12-16 hours and wrap around.
    # Actually, simpler: just wait random intervals.
    
    num_commits = random.randint(min_commits, max_commits)
    logger.info(f"Planning {num_commits} random commits for the upcoming cycle.")
    
    delays = []
    # Distribute commits roughly over 18 hours (active day) or 24 hours
    total_seconds_in_day = 24 * 60 * 60
    
    # Generate random points in time
    points = sorted([random.randint(1, total_seconds_in_day) for _ in range(num_commits)])
    
    # Convert points to delays relative to previous
    current_offset = 0
    for p in points:
        delays.append(p - current_offset)
        current_offset = p
        
    return delays


def run_continuous_random_schedule():
    """Run continuously, committing at random intervals."""
    logger.info("Starting continuous random schedule mode.")
    
    # 1. Commit immediately on start as requested
    logger.info("Executing immediate startup commit...")
    run_once()
    
    while True:
        # Generate a fresh schedule for "roughly" a day
        delays = get_random_schedule()
        
        for delay in delays:
            next_run = datetime.now() + timedelta(seconds=delay)
            logger.info(f"Next commit scheduled in {timedelta(seconds=delay)} at {next_run.strftime('%H:%M:%S')}")
            
            # Sleep until next commit
            time.sleep(delay)
            
            # Execute commit
            run_once()
            
        logger.info("Daily cycle finished, generating new schedule...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Git Auto Commit Bot")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    try:
        if args.once:
            run_once()
        else:
            run_continuous_random_schedule()
            
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.critical(f"Critical error: {e}", exc_info=True)