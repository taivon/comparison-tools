"""
CSV import utilities for importing homes from Redfin exports.
"""

import csv
import io
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import BinaryIO

logger = logging.getLogger(__name__)

# Known Redfin CSV column names (uppercase, as they appear in exports)
REDFIN_COLUMNS = {
    # Address components
    "ADDRESS": "address",
    "CITY": "city",
    "STATE OR PROVINCE": "state",
    "ZIP OR POSTAL CODE": "zip_code",
    # Core property fields
    "PRICE": "price",
    "BEDS": "bedrooms",
    "BATHS": "bathrooms",
    "SQUARE FEET": "square_footage",
    "LOT SIZE": "lot_size_sqft",
    "YEAR BUILT": "year_built",
    "HOA/MONTH": "hoa_fees",
    # Location (included in Redfin favorites export)
    "LATITUDE": "latitude",
    "LONGITUDE": "longitude",
    # Redfin-specific
    "URL (SEE HTTPS://WWW.REDFIN.COM/BUY-A-HOME/COMPARATIVE-MARKET-ANALYSIS FOR INFO ON PRICING)": "redfin_url",
    "URL (REDFIN)": "redfin_url",
    "MLS#": "mls_number",
    "PROPERTY TYPE": "property_type",
    "SOLD DATE": "sold_date",
    "STATUS": "status",
    "SALE TYPE": "sale_type",
    "LOCATION": "location",  # Neighborhood/subdivision name
}


@dataclass
class ImportedHomeData:
    """Parsed home data from CSV row."""

    name: str
    address: str
    price: Decimal
    square_footage: int
    bedrooms: Decimal = Decimal("1")
    bathrooms: Decimal = Decimal("1")
    hoa_fees: Decimal = Decimal("0")
    property_taxes: Decimal = Decimal("0")
    year_built: int | None = None
    lot_size_sqft: int | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    redfin_id: str = ""
    mls_number: str = ""
    source: str = "redfin"


@dataclass
class ImportResult:
    """Result of parsing a single CSV row."""

    success: bool
    data: ImportedHomeData | None = None
    error: str | None = None
    row_number: int = 0
    raw_address: str = ""


def normalize_column_name(name: str) -> str:
    """Normalize column name for matching."""
    return name.strip().upper()


def detect_columns(headers: list[str]) -> dict[str, int]:
    """
    Detect which columns are present and their indices.
    Returns a mapping of our field names to column indices.
    """
    column_map = {}
    normalized_headers = [normalize_column_name(h) for h in headers]

    for i, header in enumerate(normalized_headers):
        if header in REDFIN_COLUMNS:
            field_name = REDFIN_COLUMNS[header]
            column_map[field_name] = i

    return column_map


def parse_price(value: str) -> Decimal | None:
    """Parse price from string, handling currency symbols and commas."""
    if not value or value.strip() == "":
        return None

    # Remove currency symbols, commas, and whitespace
    cleaned = re.sub(r"[$,\s]", "", value.strip())

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_int(value: str) -> int | None:
    """Parse integer from string, handling commas."""
    if not value or value.strip() == "":
        return None

    # Remove commas and whitespace
    cleaned = re.sub(r"[,\s]", "", value.strip())

    # Handle values like "1,234 sqft" by taking just the numeric part
    match = re.match(r"^[\d.]+", cleaned)
    if match:
        try:
            return int(float(match.group()))
        except (ValueError, TypeError):
            return None

    return None


def parse_decimal(value: str) -> Decimal | None:
    """Parse decimal from string."""
    if not value or value.strip() == "":
        return None

    # Remove commas and whitespace
    cleaned = re.sub(r"[,\s]", "", value.strip())

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_coordinate(value: str) -> Decimal | None:
    """Parse latitude/longitude coordinate."""
    if not value or value.strip() == "":
        return None

    try:
        return Decimal(value.strip())
    except InvalidOperation:
        return None


def extract_redfin_id(url: str) -> str:
    """Extract Redfin property ID from URL."""
    if not url:
        return ""

    # Redfin URLs look like: https://www.redfin.com/CA/San-Francisco/123-Main-St-94102/home/12345678
    # The ID is typically the last numeric segment
    match = re.search(r"/home/(\d+)", url)
    if match:
        return match.group(1)

    return ""


def generate_home_name(address: str) -> str:
    """Generate a short home name from full address."""
    if not address:
        return "Imported Home"

    # Take just the street address part (before the first comma)
    parts = address.split(",")
    street = parts[0].strip()

    # Truncate if too long
    if len(street) > 50:
        street = street[:47] + "..."

    return street


def build_full_address(row: dict, column_map: dict[str, int], headers: list[str]) -> str:
    """Build full address from components."""
    parts = []

    # Get address components
    for field in ["address", "city", "state", "zip_code"]:
        if field in column_map:
            idx = column_map[field]
            value = row.get(headers[idx], "").strip()
            if value:
                parts.append(value)

    if parts:
        # Format as: "123 Main St, City, ST 12345"
        address = parts[0]
        if len(parts) > 1:
            address += ", " + ", ".join(parts[1:])
        return address

    return ""


def parse_row(row: dict, column_map: dict[str, int], headers: list[str], row_number: int) -> ImportResult:
    """Parse a single CSV row into ImportedHomeData."""
    # Build full address
    full_address = build_full_address(row, column_map, headers)

    if not full_address:
        return ImportResult(
            success=False,
            error="Missing address",
            row_number=row_number,
            raw_address="",
        )

    # Parse price (required)
    price = None
    if "price" in column_map:
        price = parse_price(row.get(headers[column_map["price"]], ""))

    if price is None or price <= 0:
        return ImportResult(
            success=False,
            error="Missing or invalid price",
            row_number=row_number,
            raw_address=full_address,
        )

    # Parse square footage (required, but default to 0 if missing)
    square_footage = 0
    if "square_footage" in column_map:
        sf = parse_int(row.get(headers[column_map["square_footage"]], ""))
        if sf is not None and sf > 0:
            square_footage = sf

    if square_footage == 0:
        return ImportResult(
            success=False,
            error="Missing or invalid square footage",
            row_number=row_number,
            raw_address=full_address,
        )

    # Parse optional fields
    bedrooms = Decimal("1")
    if "bedrooms" in column_map:
        beds = parse_decimal(row.get(headers[column_map["bedrooms"]], ""))
        if beds is not None and beds >= 0:
            bedrooms = beds

    bathrooms = Decimal("1")
    if "bathrooms" in column_map:
        baths = parse_decimal(row.get(headers[column_map["bathrooms"]], ""))
        if baths is not None and baths >= Decimal("0.5"):
            bathrooms = baths

    hoa_fees = Decimal("0")
    if "hoa_fees" in column_map:
        hoa = parse_price(row.get(headers[column_map["hoa_fees"]], ""))
        if hoa is not None and hoa >= 0:
            hoa_fees = hoa

    year_built = None
    if "year_built" in column_map:
        yb = parse_int(row.get(headers[column_map["year_built"]], ""))
        if yb is not None and 1800 <= yb <= 2100:
            year_built = yb

    lot_size_sqft = None
    if "lot_size_sqft" in column_map:
        lot = parse_int(row.get(headers[column_map["lot_size_sqft"]], ""))
        if lot is not None and lot >= 0:
            lot_size_sqft = lot

    latitude = None
    if "latitude" in column_map:
        latitude = parse_coordinate(row.get(headers[column_map["latitude"]], ""))

    longitude = None
    if "longitude" in column_map:
        longitude = parse_coordinate(row.get(headers[column_map["longitude"]], ""))

    redfin_id = ""
    if "redfin_url" in column_map:
        url = row.get(headers[column_map["redfin_url"]], "")
        redfin_id = extract_redfin_id(url)

    mls_number = ""
    if "mls_number" in column_map:
        mls_number = row.get(headers[column_map["mls_number"]], "").strip()

    # Build the result
    home_data = ImportedHomeData(
        name=generate_home_name(full_address),
        address=full_address,
        price=price,
        square_footage=square_footage,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        hoa_fees=hoa_fees,
        property_taxes=Decimal("0"),  # Not in Redfin exports
        year_built=year_built,
        lot_size_sqft=lot_size_sqft,
        latitude=latitude,
        longitude=longitude,
        redfin_id=redfin_id,
        mls_number=mls_number,
        source="redfin",
    )

    return ImportResult(
        success=True,
        data=home_data,
        row_number=row_number,
        raw_address=full_address,
    )


def parse_redfin_csv(file: BinaryIO) -> tuple[list[ImportResult], list[str]]:
    """
    Parse a Redfin CSV file and return parsed home data.

    Args:
        file: File-like object containing CSV data

    Returns:
        Tuple of (list of ImportResult, list of detected column names)
    """
    results = []
    detected_columns = []

    try:
        # Read file content and decode
        content = file.read()

        # Try UTF-8 first, fall back to latin-1
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        # Parse CSV
        reader = csv.DictReader(io.StringIO(text))

        if reader.fieldnames is None:
            return [], []

        headers = list(reader.fieldnames)
        column_map = detect_columns(headers)
        detected_columns = list(column_map.keys())

        # Check for required columns
        if "price" not in column_map:
            logger.warning("CSV missing PRICE column")
        if "address" not in column_map:
            logger.warning("CSV missing ADDRESS column")

        # Parse each row
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
            result = parse_row(row, column_map, headers, row_num)
            results.append(result)

    except csv.Error as e:
        logger.error(f"CSV parsing error: {e}")
        results.append(
            ImportResult(
                success=False,
                error=f"CSV parsing error: {e}",
                row_number=0,
            )
        )

    return results, detected_columns
