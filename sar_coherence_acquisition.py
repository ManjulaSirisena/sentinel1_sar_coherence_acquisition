"""
SAR Coherence Data Acquisition Workflow
========================================
Searches for Sentinel-1A SLC scenes over a user-defined AOI using the ASF Search API,
submits consecutive-pair InSAR jobs to HyP3 for coherence processing, and downloads
completed products.

Requirements
------------
    pip install asf_search hyp3_sdk

Usage
-----
1. Set the configuration parameters in the CONFIG section below.
2. Authenticate with your NASA Earthdata credentials (used by both ASF and HyP3).
3. Run the script sequentially or in stages using the --stage flag.

Stages
------
    search   : Search ASF catalogue and write scene list to file.
    submit   : Submit consecutive-pair InSAR jobs to HyP3.
    check    : Report job status.
    download : Download all succeeded jobs.

Example
-------
    python sar_coherence_acquisition.py --stage search
    python sar_coherence_acquisition.py --stage submit
    python sar_coherence_acquisition.py --stage check
    python sar_coherence_acquisition.py --stage download

Notes
-----
- Credentials are read from environment variables (EARTHDATA_USERNAME / EARTHDATA_PASSWORD)
  or prompted interactively; never hard-code them.
- The script submits consecutive (i, i+1) scene pairs. Adjust pair logic in submit_jobs()
  if a different pairing strategy is required.
- HyP3 InSAR parameters (looks, phase_filter_parameter, etc.) are set to the values used
  in the original study; adjust as needed for your application.
- Job submission failures are logged and skipped rather than halting the run; a summary
  of failed pairs is printed at the end and written to a log file for review.
"""

import argparse
import getpass
import logging
import os
import sys
from datetime import datetime

try:
    import asf_search as asf
except ImportError:
    print("ERROR: asf_search is not installed. Run: pip install asf_search", file=sys.stderr)
    sys.exit(1)

try:
    from hyp3_sdk import HyP3
    from hyp3_sdk.exceptions import HyP3Error
except ImportError:
    print("ERROR: hyp3_sdk is not installed. Run: pip install hyp3_sdk", file=sys.stderr)
    sys.exit(1)

# =============================================================================
# CONFIG — edit these values for your study
# =============================================================================

# Area of interest as a WKT polygon (EPSG:4326)
AOI_WKT = "POLYGON((...))"  # Replace with your AOI polygon

# Temporal search window
START_DATE = datetime(2019, 1, 1)
END_DATE   = datetime(2024, 12, 31)

# Path to write/read the scene list
SCENE_LIST_PATH = "slc_scenes.txt"

# Directory for downloaded InSAR products
DOWNLOAD_DIR = "downloads"

# Log file for submission/download errors
LOG_FILE_PATH = "workflow_errors.log"

# HyP3 job options
INSAR_LOOKS               = "10x2"
INSAR_PHASE_FILTER        = 0.6
INSAR_INCLUDE_DEM         = False
INSAR_INCLUDE_INC_MAP     = False
INSAR_INCLUDE_WRAPPED     = False
INSAR_INCLUDE_DISP_MAPS   = False
INSAR_APPLY_WATER_MASK    = False

# Slice of succeeded jobs to download (set to None to download all)
DOWNLOAD_JOB_SLICE = slice(0, 190)

# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def get_credentials():
    """Read Earthdata credentials from environment variables or prompt the user."""
    username = os.environ.get("EARTHDATA_USERNAME") or input("Earthdata username: ")
    password = os.environ.get("EARTHDATA_PASSWORD") or getpass.getpass("Earthdata password: ")

    if not username or not password:
        logger.error("Username and password must not be empty.")
        sys.exit(1)

    return username, password


def connect_hyp3(username, password):
    """Authenticate with HyP3 and return a client, exiting cleanly on failure."""
    try:
        hyp3 = HyP3(username=username, password=password)
    except HyP3Error as exc:
        logger.error(f"HyP3 authentication failed: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Unexpected error connecting to HyP3: {exc}")
        sys.exit(1)
    return hyp3


def search_scenes():
    """Search the ASF catalogue for Sentinel-1A IW SLC scenes and write a scene list."""
    if "..." in AOI_WKT:
        logger.error(
            "AOI_WKT is still set to the placeholder value. "
            "Edit the CONFIG section with your actual polygon coordinates."
        )
        sys.exit(1)

    logger.info("Searching ASF catalogue …")
    try:
        results = asf.search(
            platform=asf.PLATFORM.SENTINEL1A,
            processingLevel=asf.PRODUCT_TYPE.SLC,
            beamMode=asf.BEAMMODE.IW,
            polarization=["VV+VH"],
            flightDirection=asf.FLIGHT_DIRECTION.ASCENDING,
            start=START_DATE,
            end=END_DATE,
            intersectsWith=AOI_WKT,
        )
    except ValueError as exc:
        logger.error(f"Invalid search parameters (check AOI_WKT format): {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"ASF search failed: {exc}")
        sys.exit(1)

    if len(results) == 0:
        logger.warning(
            "Search returned 0 results. Check AOI_WKT, START_DATE/END_DATE, "
            "and that Sentinel-1A scenes exist for this combination."
        )
        return

    logger.info(f"Found {len(results)} matching product(s).")

    try:
        os.makedirs(os.path.dirname(SCENE_LIST_PATH) or ".", exist_ok=True)
        with open(SCENE_LIST_PATH, "w") as fh:
            for scene in results:
                fh.write(f"{scene.properties['sceneName']}\n")
    except OSError as exc:
        logger.error(f"Failed to write scene list to {SCENE_LIST_PATH}: {exc}")
        sys.exit(1)

    logger.info(f"Scene list written to: {SCENE_LIST_PATH}")


def load_scene_list():
    """Load scene names from the scene list file, exiting cleanly if missing or empty."""
    if not os.path.exists(SCENE_LIST_PATH):
        logger.error(
            f"Scene list not found at {SCENE_LIST_PATH}. "
            "Run with --stage search first."
        )
        sys.exit(1)

    with open(SCENE_LIST_PATH, "r") as fh:
        scene_list = [line.rstrip("\n") for line in fh if line.strip()]

    if len(scene_list) < 2:
        logger.error(
            f"Scene list has {len(scene_list)} scene(s); at least 2 are required to form a pair."
        )
        sys.exit(1)

    return scene_list


def submit_jobs(username, password):
    """Submit consecutive-pair InSAR jobs to HyP3. Failed submissions are logged and skipped."""
    scene_list = load_scene_list()
    hyp3 = connect_hyp3(username, password)

    total_pairs = len(scene_list) - 1
    failed_pairs = []

    logger.info(f"Submitting {total_pairs} InSAR job(s) …")
    for i in range(total_pairs):
        j = i + 1
        pair_label = f"{i+1}&{j+1}"
        try:
            hyp3.submit_insar_job(
                granule1=scene_list[i],
                granule2=scene_list[j],
                name=f"coherence_{i+1}_{pair_label}",
                looks=INSAR_LOOKS,
                include_dem=INSAR_INCLUDE_DEM,
                include_inc_map=INSAR_INCLUDE_INC_MAP,
                include_wrapped_phase=INSAR_INCLUDE_WRAPPED,
                include_displacement_maps=INSAR_INCLUDE_DISP_MAPS,
                apply_water_mask=INSAR_APPLY_WATER_MASK,
                phase_filter_parameter=INSAR_PHASE_FILTER,
            )
        except HyP3Error as exc:
            logger.warning(f"Pair {pair_label} failed (HyP3 error): {exc}")
            failed_pairs.append((pair_label, str(exc)))
        except Exception as exc:
            logger.warning(f"Pair {pair_label} failed (unexpected error): {exc}")
            failed_pairs.append((pair_label, str(exc)))

    submitted = total_pairs - len(failed_pairs)
    logger.info(f"Submission complete: {submitted}/{total_pairs} job(s) submitted successfully.")

    if failed_pairs:
        logger.warning(f"{len(failed_pairs)} pair(s) failed to submit. See {LOG_FILE_PATH} for details.")
        for pair_label, reason in failed_pairs:
            logger.info(f"  Failed pair {pair_label}: {reason}")


def check_jobs(username, password):
    """Print a summary of HyP3 job statuses."""
    hyp3 = connect_hyp3(username, password)
    try:
        jobs = hyp3.find_jobs()
    except HyP3Error as exc:
        logger.error(f"Failed to retrieve jobs: {exc}")
        sys.exit(1)

    if len(jobs) == 0:
        logger.info("No jobs found for this account.")
        return

    print(jobs)


def download_jobs(username, password):
    """Download succeeded HyP3 jobs to DOWNLOAD_DIR."""
    hyp3 = connect_hyp3(username, password)

    try:
        jobs = hyp3.find_jobs()
    except HyP3Error as exc:
        logger.error(f"Failed to retrieve jobs: {exc}")
        sys.exit(1)

    succeeded = jobs.filter_jobs(succeeded=True)
    logger.info(f"Found {len(succeeded)} succeeded job(s).")

    if len(succeeded) == 0:
        logger.warning("No succeeded jobs available to download. Run --stage check to review status.")
        return

    target = succeeded[DOWNLOAD_JOB_SLICE] if DOWNLOAD_JOB_SLICE is not None else succeeded
    logger.info(f"Downloading {len(target)} job(s) …")

    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    except OSError as exc:
        logger.error(f"Failed to create download directory {DOWNLOAD_DIR}: {exc}")
        sys.exit(1)

    try:
        target.download_files(DOWNLOAD_DIR)
    except Exception as exc:
        logger.error(f"Download failed partway through: {exc}")
        logger.info("Re-run --stage download to resume; already-downloaded files will be skipped if supported by HyP3 SDK.")
        sys.exit(1)

    logger.info(f"Download complete. Files saved to: {DOWNLOAD_DIR}")


def main():
    parser = argparse.ArgumentParser(
        description="SAR coherence data acquisition workflow (ASF + HyP3)."
    )
    parser.add_argument(
        "--stage",
        choices=["search", "submit", "check", "download"],
        required=True,
        help="Workflow stage to execute.",
    )
    args = parser.parse_args()

    try:
        if args.stage == "search":
            search_scenes()
        else:
            username, password = get_credentials()
            if args.stage == "submit":
                submit_jobs(username, password)
            elif args.stage == "check":
                check_jobs(username, password)
            elif args.stage == "download":
                download_jobs(username, password)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user. Exiting.")
        sys.exit(130)


if __name__ == "__main__":
    main()