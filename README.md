# RetailIQ: An AI-Powered Demand Forecasting and Stock Intelligence Platform for Small and Medium Retail Businesses

RetailIQ is a multi-tenant retail decision-support web application developed with
Flask. It allows a business to upload category-level historical sales data,
generate demand forecasts with a trained scikit-learn pipeline, record current
inventory, assess stock position, detect unusual historical observations, and
review operational analytics through a responsive web interface.

## Main features

- User registration and JWT-based login with hashed passwords.
- Server-side business membership and tenant-scoped data access.
- POS-style CSV upload and validation for `date`, `family`, and `sales`, with
  optional `onpromotion` data.
- Recursive 7-, 14-, and 30-day demand forecasts at category level.
- Category-level current inventory creation and updates.
- Configurable understock, sufficient-stock, and overstock classification.
- Historical anomaly detection using per-category residual Z-scores.
- Tenant-owned dashboard and analytics views for sales, forecasts, stock, and
  anomaly summaries.

## Technology stack

- **Backend:** Python 3.11, Flask, Flask-SQLAlchemy, Flask-Migrate, and
  Flask-JWT-Extended
- **Machine learning and data:** scikit-learn, pandas, NumPy, and joblib
- **Frontend:** HTML, CSS, vanilla JavaScript, and Chart.js
- **Databases:** SQLite for local development and PostgreSQL for production
- **Production server:** Gunicorn
- **Testing:** pytest

Exact package versions are pinned in [`requirements.txt`](requirements.txt).

## Repository structure

```text
app/          Flask application, API routes, models, services, templates and assets
tests/        Automated backend, frontend-route and end-to-end tests
model/        Trained model and its recorded software environment
notebooks/    Model development and evaluation notebook
migrations/   Flask-Migrate/Alembic database migration history
docs/         Deployment, design-system and demonstration-data documentation
config.py     Environment-driven application configuration
run.py        Local Flask entry point and WSGI application export
```

## Machine learning artefacts

- `model/retailiq_final_model.pkl` - trained scikit-learn forecasting pipeline,
  tracked using Git LFS.
- `model/model_environment.json` - model-development package versions.
- `notebooks/retailiq-final-category-forecasting.ipynb` - category forecasting
  notebook used during model development.

The application loads the existing model artefact and does not retrain or alter
it at runtime.

## Dataset

Model development used the Kaggle competition dataset
[Store Sales - Time Series Forecasting](https://www.kaggle.com/competitions/store-sales-time-series-forecasting).

## Local setup

1. Clone the repository and enter it:

   ```bash
   git clone https://github.com/rizni-razeek/RetailIQ.git
   cd RetailIQ
   ```

2. Ensure [Git LFS](https://git-lfs.com/) is installed, then retrieve the model:

   ```bash
   git lfs install
   git lfs pull
   ```

3. Create and activate a Python 3.11 virtual environment:

   ```bash
   python -m venv .venv
   ```

   Windows PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   macOS/Linux:

   ```bash
   source .venv/bin/activate
   ```

4. Install the pinned dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

5. Copy `.env.example` to `.env` and replace the example Flask and JWT secrets
   with development values. Leave `DATABASE_URL` empty to use local SQLite and
   keep `MODEL_PATH=model/retailiq_final_model.pkl` for the Git LFS model.

   Windows PowerShell:

   ```powershell
   Copy-Item .env.example .env
   ```

   macOS/Linux:

   ```bash
   cp .env.example .env
   ```

6. Apply database migrations when setting up a new database:

   ```bash
   python -m flask --app run.py db upgrade
   ```

7. Start the local Flask application:

   ```bash
   python run.py
   ```

   The application is normally available at `http://127.0.0.1:5000/`.

Never commit `.env`, database credentials, access tokens, or other secrets.

## Running tests

Run the complete automated suite from the repository root:

```bash
python -m pytest -q --basetemp=test_temp -p no:cacheprovider
```

Tests use isolated databases and mocked lightweight models where appropriate;
they do not require an external PostgreSQL server or network download.

## Deployment note

The repository includes configuration for a Gunicorn-hosted Flask application
on Render with a Neon PostgreSQL `DATABASE_URL`. If the configured `MODEL_PATH`
is missing, production startup can provision the private model from Hugging Face
using environment-only configuration. See
[`docs/deployment.md`](docs/deployment.md) for the required variables and start
command.

This is not a claim of full production readiness. Complete cloud end-to-end
operation is constrained by free-tier memory limits because the trained model is
large in memory, and Render's temporary filesystem is ephemeral.

## Important limitations

- The forecasting model was trained on an external retail dataset; performance
  may not transfer directly to every business or operating context.
- Forecasting and inventory comparison operate at category/family level, not at
  SKU or individual-product level.
- Historical sales data must be uploaded manually as a compatible CSV file;
  there is no direct POS integration.
- Future promotion values are not supplied, so recursive forecasts assume
  `onpromotion = 0` for future dates.
- The available evaluation does not establish independently validated fixed-origin
  7-, 14-, or 30-day forecast accuracy.
- Stock classification uses a configurable prototype rule and assumes inventory
  and forecast demand use compatible units; it is not an industry standard.
- Residual Z-score anomalies identify unusual observations but do not establish
  fraud, data errors, stock issues, or any other cause.

## Academic project

This repository contains the software artefact developed for a BSc (Hons)
Software Engineering final development project.
