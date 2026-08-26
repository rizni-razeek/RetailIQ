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
- `MODEL_PATH`: absolute path to the provisioned model artifact
- `UPLOAD_FOLDER`: writable raw-upload directory
- `MAX_UPLOAD_SIZE_MB`: maximum CSV upload size in megabytes
- `STOCK_OVERSTOCK_MULTIPLIER`: prototype stock rule, currently `1.5`
- `ANOMALY_Z_THRESHOLD`: residual Z-score threshold, currently `2.0`

Production startup fails when `DATABASE_URL`, `SECRET_KEY`, or
`JWT_SECRET_KEY` is missing. Debug mode is disabled in production. Store all
credentials in the platform environment; do not add a real `.env` file to Git.

## Model provisioning

The trained `retailiq_final_model.pkl` is approximately 145 MB and remains
Git-ignored. Provision it separately, such as through a deployment volume or a
private build artifact, and set `MODEL_PATH` to that file. RetailIQ does not
download the model or require cloud-storage credentials. A missing or unloadable
model is reported safely by the health endpoint and model-dependent APIs remain
unavailable until it is provisioned.

## Database and startup

Apply migrations as a deployment/release step:

```bash
python -m flask --app run.py db upgrade
```

Start the Linux production service with Gunicorn:

```bash
gunicorn run:app
```

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
