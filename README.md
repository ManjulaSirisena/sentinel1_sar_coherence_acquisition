# SAR Coherence Data Acquisition Workflow

A Python workflow for automating Sentinel-1 SAR coherence data acquisition using the ASF Search API and ASF HyP3 processing services.

The workflow searches for Sentinel-1 IW SLC scenes over a user-defined area of interest, submits consecutive-pair InSAR coherence processing jobs to HyP3, monitors job status, and downloads the completed products. It was developed to support an MSc research project investigating Sentinel-1 SAR coherence decay modelling for slope disturbance assessment.

---

## Why this workflow?

Large multi-temporal SAR studies often require the submission and management of dozens of InSAR processing jobs. Performing these tasks manually through the HyP3 web interface can be repetitive, time-consuming, and prone to error.

This workflow automates the complete data acquisition stage by:

- Searching Sentinel-1 IW SLC scenes within a specified area and date range
- Creating an ordered scene list for processing
- Submitting consecutive-pair InSAR jobs to HyP3
- Monitoring processing status
- Downloading completed coherence products automatically

The workflow is intended as a reproducible research tool and serves as the data acquisition component of a larger SAR coherence analysis framework.

---

## Workflow

```
        ASF Search API
              │
              ▼
      Search Sentinel-1 SLC scenes
              │
              ▼
      Generate ordered scene list
              │
              ▼
 Submit consecutive-pair HyP3 jobs
              │
              ▼
     Monitor processing status
              │
              ▼
 Download completed InSAR products
```

---

## Requirements

- Python 3.8 or later
- A NASA Earthdata account (used for both ASF Search and HyP3 authentication)

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

Edit the `CONFIG` block at the beginning of `sar_coherence_acquisition.py`.

| Parameter | Description |
|------------|-------------|
| `AOI_WKT` | Area of interest as a WKT polygon (EPSG:4326) |
| `START_DATE` / `END_DATE` | Temporal search window |
| `SCENE_LIST_PATH` | Path to save or read the ordered scene list |
| `DOWNLOAD_DIR` | Output directory for downloaded HyP3 products |
| `INSAR_*` | HyP3 InSAR processing parameters (looks, filtering, etc.) |
| `DOWNLOAD_JOB_SLICE` | Download a subset of completed jobs (`slice(start, end)`) or `None` for all |

---

## Authentication

Credentials are never stored within the source code.

Set them as environment variables:

```bash
export EARTHDATA_USERNAME=your_username
export EARTHDATA_PASSWORD=your_password
```

Alternatively, create a local `.env` file (excluded via `.gitignore`):

```bash
export EARTHDATA_USERNAME=your_username
export EARTHDATA_PASSWORD=your_password
```

Then load it before execution:

```bash
source .env
```

If no credentials are found, the script prompts for them interactively.

---

## Usage

The workflow consists of four sequential stages.

### 1. Search

Search the ASF catalogue and create an ordered Sentinel-1 scene list.

```bash
python sar_coherence_acquisition.py --stage search
```

---

### 2. Submit

Submit consecutive-pair InSAR coherence processing jobs to HyP3.

```bash
python sar_coherence_acquisition.py --stage submit
```

Each processing pair consists of scene *i* and scene *i + 1* in the ordered scene list.

The pairing strategy can be modified within `submit_jobs()` to support alternative temporal baseline selection methods.

---

### 3. Check

Display the processing status of submitted HyP3 jobs.

```bash
python sar_coherence_acquisition.py --stage check
```

Re-run this stage until the required jobs reach the `SUCCEEDED` state.

---

### 4. Download

Download all completed products.

```bash
python sar_coherence_acquisition.py --stage download
```

Downloaded products are written to `DOWNLOAD_DIR`.

---

## Output

Each downloaded HyP3 product is provided as a compressed archive containing, depending on the selected processing options:

- `*_corr.tif` — SAR coherence raster
- `*_unw_phase.tif` — Unwrapped interferometric phase
- `*_amp.tif` — SAR backscatter amplitude

---

## Current limitations

The current implementation is designed specifically for the requirements of the associated MSc research project.

- Sentinel-1A IW SLC imagery
- Ascending orbit direction
- VV + VH polarisation
- Consecutive-pair processing strategy
- Single user-defined area of interest

These assumptions can be modified within the source code to support alternative acquisition strategies.

---

## Future improvements

Potential future enhancements include:

- Configurable temporal baseline selection
- Support for Sentinel-1B acquisitions
- Parallel job submission
- Logging and progress reporting
- Additional command-line configuration options

---

## Dependencies

| Package | Purpose |
|----------|---------|
| `asf_search` | Sentinel-1 scene discovery using the ASF Search API |
| `hyp3_sdk` | HyP3 job submission, monitoring, and product download |

