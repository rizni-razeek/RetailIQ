import io
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from werkzeug.utils import secure_filename


REQUIRED_COLUMNS = {"date", "family", "sales"}
EXPECTED_COLUMNS = ["date", "family", "sales", "onpromotion"]


class CsvValidationError(ValueError):
    pass


@dataclass
class ValidatedCsv:
    data: pd.DataFrame
    content: bytes
    original_filename: str


def _normalise_column_name(column):
    normalised = re.sub(r"[^a-z0-9]+", "_", str(column).strip().casefold())
    return normalised.strip("_")


def validate_sales_csv(file_storage):
    if file_storage is None or not file_storage.filename:
        raise CsvValidationError("A CSV file is required in the 'file' field.")

    if Path(file_storage.filename).suffix.casefold() != ".csv":
        raise CsvValidationError("Only .csv files are accepted.")

    original_filename = secure_filename(file_storage.filename)
    if not original_filename:
        raise CsvValidationError("The uploaded filename is invalid.")

    content = file_storage.read()
    if not content or not content.strip():
        raise CsvValidationError("The uploaded CSV file is empty.")

    try:
        data = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        raise CsvValidationError("The uploaded file is not a valid CSV file.") from None

    normalised_columns = [_normalise_column_name(column) for column in data.columns]
    if len(normalised_columns) != len(set(normalised_columns)):
        raise CsvValidationError("The CSV contains duplicate column names.")
    data.columns = normalised_columns

    missing_columns = sorted(REQUIRED_COLUMNS - set(data.columns))
    if missing_columns:
        raise CsvValidationError(
            f"Missing required columns: {', '.join(missing_columns)}."
        )

    if data.empty:
        raise CsvValidationError("The CSV contains no data rows.")

    cleaned = data[[column for column in EXPECTED_COLUMNS if column in data]].copy()

    parsed_dates = pd.to_datetime(
        cleaned["date"], errors="coerce", format="mixed", utc=True
    )
    if parsed_dates.isna().any():
        raise CsvValidationError("Every date value must be a valid date.")
    cleaned["date"] = parsed_dates.dt.date

    families = cleaned["family"].astype("string").str.strip()
    if families.isna().any() or families.eq("").any():
        raise CsvValidationError("Every family value must be non-empty.")
    cleaned["family"] = families

    sales = pd.to_numeric(cleaned["sales"], errors="coerce")
    if sales.isna().any() or not np.isfinite(sales).all():
        raise CsvValidationError("Every sales value must be numeric.")
    if sales.lt(0).any():
        raise CsvValidationError("Sales values cannot be negative.")
    cleaned["sales"] = sales.astype(float)

    if "onpromotion" not in cleaned:
        cleaned["onpromotion"] = 0.0
    else:
        onpromotion = pd.to_numeric(cleaned["onpromotion"], errors="coerce")
        if onpromotion.isna().any() or not np.isfinite(onpromotion).all():
            raise CsvValidationError("Every onpromotion value must be numeric.")
        if onpromotion.lt(0).any():
            raise CsvValidationError("Onpromotion values cannot be negative.")
        cleaned["onpromotion"] = onpromotion.astype(float)

    if cleaned.empty:
        raise CsvValidationError("The CSV contains no usable rows.")

    return ValidatedCsv(
        data=cleaned[EXPECTED_COLUMNS],
        content=content,
        original_filename=original_filename,
    )
