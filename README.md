# SAR Coherence Data Acquisition Workflow

A Python workflow for searching Sentinel-1A SLC scenes via the [ASF Search API](https://docs.asf.alaska.edu/api/keywords/) and submitting consecutive-pair InSAR jobs to [HyP3](https://hyp3-docs.asf.alaska.edu/) for SAR coherence processing.

Developed as part of an MSc research project on Sentinel-1 SAR coherence decay modelling for surface disturbance characterisation in gem mining terrain, Ratnapura District, Sri Lanka.

---

## Requirements

- Python ≥ 3.8
- A [NASA Earthdata](https://urs.earthdata.nasa.gov/) account (used for both ASF search and HyP3 authentication)

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

Edit the `CONFIG` block at the top of `sar_coherence_acquisition.py`:

| Parameter | Description |
|---|---|
| `AOI_WKT` | Area of interest as a WKT polygon (EPSG:4326) |
| `START_DATE` / `END_DATE` | Temporal search window |
| `SCENE_LIST_PATH` | Path to write/read the scene list file |
| `DOWNLOAD_DIR` | Directory for downloaded InSAR products |
| `INSAR_*` | HyP3 InSAR processing options (looks, phase filter, etc.) |
| `DOWNLOAD_JOB_SLICE` | `slice(start, end)` of succeeded jobs to download, or `None` for all |

---

## Credentials

Credentials are never hard-coded. Set them as environment variables before running:

```bash
export EARTHDATA_USERNAME=your_username
export EARTHDATA_PASSWORD=your_password
```

Or create a `.env` file (excluded from version control by `.gitignore`) and source it:

```bash
# .env
export EARTHDATA_USERNAME=your_username
export EARTHDATA_PASSWORD=your_password
```

```bash
source .env
```

If environment variables are not set, the script will prompt interactively.

---

## Usage

The workflow is split into four sequential stages.

### 1. Search

Search the ASF catalogue and write matching scene names to `slc_scenes.txt`:

```bash
python sar_coherence_acquisition.py --stage search
```

### 2. Submit

Submit consecutive-pair InSAR jobs to HyP3:

```bash
python sar_coherence_acquisition.py --stage submit
```

Each pair consists of scene `i` and scene `i+1` in the ordered scene list. Adjust the pairing logic in `submit_jobs()` if a different temporal baseline strategy is required.

### 3. Check

Report the status of submitted jobs:

```bash
python sar_coherence_acquisition.py --stage check
```

Re-run until all required jobs show `SUCCEEDED` before proceeding to download.

### 4. Download

Download all succeeded jobs to `DOWNLOAD_DIR`:

```bash
python sar_coherence_acquisition.py --stage download
```

---

## Output

Each downloaded HyP3 InSAR product is a `.zip` archive containing (depending on job options):

- `*_corr.tif` — SAR coherence raster
- `*_unw_phase.tif` — Unwrapped interferometric phase
- `*_amp.tif` — Backscatter amplitude

---

## Notes

- This workflow targets **Sentinel-1A IW SLC** data with **VV+VH** polarisation and **ascending** flight direction. Modify `asf.search()` parameters in `search_scenes()` for other configurations.
- HyP3 processing is subject to [usage quotas](https://hyp3-docs.asf.alaska.edu/using/quota/). Check your remaining quota before bulk submission.
- `DOWNLOAD_JOB_SLICE` allows partial downloads (e.g., `slice(0, 50)`) without re-submitting jobs.

---

## Dependencies

| Package | Purpose |
|---|---|
| [`asf_search`](https://github.com/asfadmin/Discovery-asf_search) | ASF catalogue search |
| [`hyp3_sdk`](https://github.com/ASFHyP3/hyp3-sdk) | HyP3 job submission and download |
