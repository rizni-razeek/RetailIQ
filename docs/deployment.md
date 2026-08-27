# Backend deployment

RetailIQ targets Python 3.11 and a PostgreSQL database in production. Local
development can continue to use SQLite by leaving `DATABASE_URL` unset.

## Install and configure

Install the pinned dependencies:

```bash
python -m pip install -r requirements.txt
```

Set these environment variables in the deployment platform:

- `APP_ENV=production`
- `DATABASE_URL`: PostgreSQL connection URL
- `SECRET_KEY`: long, random Flask secret
- `JWT_SECRET_KEY`: separate long, random JWT signing secret
- `MODEL_PATH`: absolute destination for the model artifact
- `HF_MODEL_REPO`: private Hugging Face repository name
- `HF_MODEL_FILENAME`: model filename within that repository
- `HF_TOKEN`: Hugging Face read token, stored as a secret environment variable
- `UPLOAD_FOLDER`: writable raw-upload directory
- `MAX_UPLOAD_SIZE_MB`: maximum CSV upload size in megabytes
- `STOCK_OVERSTOCK_MULTIPLIER`: prototype stock rule, currently `1.5`
- `ANOMALY_Z_THRESHOLD`: residual Z-score threshold, currently `2.0`

Production startup fails when `DATABASE_URL`, `SECRET_KEY`, or
`JWT_SECRET_KEY` is missing. Debug mode is disabled in production. Store all
credentials in the platform environment; do not add a real `.env` file to Git.

## Model provisioning

The trained `retailiq_final_model.pkl` is a large artifact and remains
Git-ignored. RetailIQ first checks `MODEL_PATH`. If that file exists, it is used
without a network request. If it is missing and all three Hugging Face variables
are configured, startup downloads the private artifact in chunks, writes it to a
temporary file, and moves it atomically into place before the cached model loader
uses it. Failed downloads do not become the production model, and a configured
download failure stops startup with a sanitized error.

For Render, configure:

```text
MODEL_PATH=/tmp/retailiq_final_model.pkl
HF_MODEL_REPO=RRizni/retailiq-demand-forecast-model
HF_MODEL_FILENAME=retailiq_final_model.pkl
HF_TOKEN=<secret environment variable>
```

Set `HF_TOKEN` only through Render's secret environment settings. Never put it
in `.env.example`, deployment manifests, logs, or Git. The token needs read
access to the private model repository.

Render's `/tmp` storage is ephemeral, so the model may be downloaded again after
a restart, redeploy, or replacement instance. This avoids committing the model
but makes startup dependent on Hugging Face availability and the configured
token. A persistent disk can instead hold `MODEL_PATH` if one is available.

## Database and startup

Apply migrations as a deployment/release step:

```bash
python -m flask --app run.py db upgrade
```

Start the Linux production service with Gunicorn:

```bash
gunicorn --workers 1 --timeout 180 run:app
```

The longer worker timeout allows for a cold model download on an ephemeral
instance. One worker also avoids loading a separate copy of the large model into
memory on the free service tier.

Use `GET /api/health` for health verification. It reports application and model
availability without exposing paths or secrets.

## Upload storage

Raw CSV files are still written to `UPLOAD_FOLDER`. Render, Railway, and similar
services may provide an ephemeral filesystem. Use a persistent mounted volume if
raw-file retention is required. Object-storage integration is outside the
current milestone; the database sales records remain the important application
data.

For local development, copy `.env.example` to `.env`, use appropriate local
values, omit `DATABASE_URL` to use SQLite, and run:

```bash
python run.py
```
