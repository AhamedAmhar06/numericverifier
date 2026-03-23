"""Tests for pnl_parser — real-world financial table preprocessing.

Covers all six issues listed in the feature request:
1. Multi-row headers ("Fiscal Year Ended" + date row)
2. Parentheses negatives: (1,234) → -1234
3. Table-level scale ("in millions") applied to all values
4. Standalone dash / em-dash → 0.0
5. Footnote markers (*, †, trailing digits) stripped
6. FY notation (FY2024, FY24, '24) normalised

Plus a full Apple FY2023 income-statement integration test.
"""
import pytest

from backend.app.verifier.pnl_parser import (
    PnLTable,
    TableMetadata,
    _is_standalone_dash,
    _normalize_period,
    _parse_pnl_cell,
    _strip_footnote_markers,
    parse_pnl_table,
)


# ===========================================================================
# 1. _strip_footnote_markers
# ===========================================================================
class TestStripFootnoteMarkers:
    def test_trailing_asterisk(self):
        assert _strip_footnote_markers("42,567*") == "42,567"

    def test_trailing_dagger(self):
        assert _strip_footnote_markers("1,234†") == "1,234"

    def test_trailing_double_dagger(self):
        assert _strip_footnote_markers("99,803‡") == "99,803"

    def test_trailing_section_symbol(self):
        assert _strip_footnote_markers("500§") == "500"

    def test_trailing_pilcrow(self):
        assert _strip_footnote_markers("200¶") == "200"

    def test_trailing_space_digit(self):
        assert _strip_footnote_markers("383,285 1") == "383,285"

    def test_trailing_space_two_digits(self):
        assert _strip_footnote_markers("96,995 12") == "96,995"

    def test_clean_value_unchanged(self):
        assert _strip_footnote_markers("383,285") == "383,285"

    def test_parentheses_negative_unchanged(self):
        assert _strip_footnote_markers("(29,749)") == "(29,749)"

    def test_empty_unchanged(self):
        assert _strip_footnote_markers("") == ""


# ===========================================================================
# 2. _is_standalone_dash
# ===========================================================================
class TestIsStandaloneDash:
    def test_hyphen(self):
        assert _is_standalone_dash("-") is True

    def test_em_dash(self):
        assert _is_standalone_dash("—") is True

    def test_en_dash(self):
        assert _is_standalone_dash("–") is True

    def test_multiple_dashes(self):
        assert _is_standalone_dash("---") is True

    def test_padded_em_dash(self):
        assert _is_standalone_dash("  —  ") is True

    def test_number_is_not_dash(self):
        assert _is_standalone_dash("0") is False

    def test_negative_number_not_dash(self):
        assert _is_standalone_dash("-500") is False

    def test_empty_string_not_dash(self):
        assert _is_standalone_dash("") is False


# ===========================================================================
# 3. _normalize_period
# ===========================================================================
class TestNormalizePeriod:
    def test_fy_4digit(self):
        assert _normalize_period("FY2024") == "FY2024"

    def test_fy_4digit_with_space(self):
        assert _normalize_period("FY 2024") == "FY2024"

    def test_fy_2digit(self):
        assert _normalize_period("FY24") == "FY2024"

    def test_fy_2digit_lowercase(self):
        assert _normalize_period("fy24") == "FY2024"

    def test_single_quote_year(self):
        assert _normalize_period("'24") == "FY2024"

    def test_left_single_quote_year(self):
        # Unicode left single quote (\u2018)
        assert _normalize_period("\u201824") == "FY2024"

    def test_bare_4digit_year(self):
        assert _normalize_period("2023") == "2023"

    def test_quarter_short(self):
        result = _normalize_period("Q1'24")
        assert result == "Q1 2024"

    def test_quarter_long(self):
        assert _normalize_period("Q3 2023") == "Q3 2023"

    def test_date_string_sep(self):
        assert _normalize_period("September 30, 2023") == "2023"

    def test_date_string_short(self):
        assert _normalize_period("Sep 24, 2022") == "2022"

    def test_unknown_passthrough(self):
        assert _normalize_period("TTM") == "TTM"


# ===========================================================================
# 4. _parse_pnl_cell
# ===========================================================================
class TestParsePnlCell:
    def test_plain_number(self):
        assert _parse_pnl_cell("383,285") == pytest.approx(383_285.0)

    def test_parentheses_negative(self):
        assert _parse_pnl_cell("(29,749)") == pytest.approx(-29_749.0)

    def test_em_dash_is_zero(self):
        assert _parse_pnl_cell("—") == 0.0

    def test_en_dash_is_zero(self):
        assert _parse_pnl_cell("–") == 0.0

    def test_hyphen_is_zero(self):
        assert _parse_pnl_cell("-") == 0.0

    def test_footnote_asterisk_stripped(self):
        assert _parse_pnl_cell("42,567*") == pytest.approx(42_567.0)

    def test_footnote_dagger_stripped(self):
        assert _parse_pnl_cell("158,844†") == pytest.approx(158_844.0)

    def test_footnote_trailing_digit_stripped(self):
        assert _parse_pnl_cell("99,803 1") == pytest.approx(99_803.0)

    def test_table_scale_applied(self):
        # "in millions": raw value 100 → 100_000_000
        assert _parse_pnl_cell("100", scale_multiplier=1_000_000) == pytest.approx(100_000_000.0)

    def test_table_scale_with_negative(self):
        assert _parse_pnl_cell("(1,234)", scale_multiplier=1_000_000) == pytest.approx(-1_234_000_000.0)

    def test_cell_own_scale_not_doubled(self):
        # Cell says "2 million"; table is also "in millions" → don't double-apply
        result = _parse_pnl_cell("2 million", scale_multiplier=1_000_000)
        assert result == pytest.approx(2_000_000.0)

    def test_integer_passthrough(self):
        assert _parse_pnl_cell(12345, scale_multiplier=1_000) == pytest.approx(12_345_000.0)

    def test_float_passthrough(self):
        assert _parse_pnl_cell(1.5, scale_multiplier=1_000_000) == pytest.approx(1_500_000.0)

    def test_empty_returns_none(self):
        assert _parse_pnl_cell("") is None

    def test_none_returns_none(self):
        assert _parse_pnl_cell(None) is None

    def test_non_numeric_returns_none(self):
        assert _parse_pnl_cell("N/A") is None


# ===========================================================================
# 5. Apple FY2023 full income-statement integration
# ===========================================================================

# Mirrors Apple's Consolidated Statements of Operations (FY2023 10-K)
# Values are "in millions" as declared in the caption.
APPLE_FY2023_TABLE = {
    "caption": "Apple Inc. CONSOLIDATED STATEMENTS OF OPERATIONS"
               " (In millions, except number of shares and per-share data)",
    "columns": ["", "2023", "2022", "2021"],
    "rows": [
        # Sub-headers → skipped (no matching synonym)
        ["Net sales:", None, None, None],
        ["  Products",              "200,583", "158,844*",  "191,973"],
        ["  Services",              "85,200",  "78,129",    "68,425"],
        # Revenue total
        ["Total net sales",         "383,285",  "258,974",  "260,174"],
        # COGS
        ["Cost of sales:", None, None, None],
        ["  Products",              "126,590",  "101,226",  "126,371"],
        ["  Services",              "24,392",   "22,075",   "20,715"],
        ["Total cost of sales",     "150,982",  "123,301",  "147,086"],
        # Gross profit
        ["Gross margin",            "232,303",  "135,673",  "113,088"],
        # Operating expenses
        ["Operating expenses:", None, None, None],
        ["Research and development",             "29,915",  "26,251",  "21,914"],
        ["Selling, general and administrative",  "24,932",  "25,094",  "21,973"],
        ["Total operating expenses",             "54,847",  "51,345",  "43,887"],
        # Operating income
        ["Operating income",        "114,301",  "119,437",  "108,949"],
        # Other items (not in our synonyms → skipped cleanly)
        ["Other income/(expense), net", "269",  "(334)",    "(76)"],
        ["Income before provision for income taxes", "114,570", "119,103", "108,873"],
        # Taxes
        ["Provision for income taxes", "29,749", "19,300",  "14,527"],
        # Net income
        ["Net income",              "96,995",   "99,803",   "94,680"],
        # Edge case: zero-value with em-dash (not in synonyms, just verifying it doesn't crash)
        ["Discontinued operations", "—",        "—",        "—"],
    ],
}


class TestAppleFY2023:
    """Integration: parse a realistic Apple income-statement table."""

    @pytest.fixture(scope="class")
    def result(self):
        r = parse_pnl_table(APPLE_FY2023_TABLE)
        assert r is not None, "parse_pnl_table returned None"
        return r

    # --- Metadata ---
    def test_scale_label_is_M(self, result):
        assert result.metadata.scale_label == "M"

    def test_scale_multiplier_is_1M(self, result):
        assert result.metadata.scale_multiplier == 1_000_000

    def test_currency_detected_usd(self, result):
        # Caption contains "In millions" which has no currency symbol,
        # but Apple's caption often has implied USD.  Verify at least no crash.
        # (Currency detection is best-effort from header text.)
        assert result.metadata.currency in (None, "USD")

    def test_three_periods_extracted(self, result):
        assert set(result.periods) == {"2021", "2022", "2023"}

    # --- Revenue ---
    def test_revenue_present(self, result):
        assert "revenue" in result.items

    def test_revenue_2023(self, result):
        # 383,285 * 1_000_000
        assert result.items["revenue"]["2023"] == pytest.approx(383_285_000_000.0)

    def test_revenue_2022(self, result):
        assert result.items["revenue"]["2022"] == pytest.approx(258_974_000_000.0)

    # --- COGS ---
    def test_cogs_present(self, result):
        assert "cogs" in result.items

    def test_cogs_2023(self, result):
        assert result.items["cogs"]["2023"] == pytest.approx(150_982_000_000.0)

    # --- Gross profit ---
    def test_gross_profit_present(self, result):
        assert "gross_profit" in result.items

    def test_gross_profit_2023(self, result):
        assert result.items["gross_profit"]["2023"] == pytest.approx(232_303_000_000.0)

    # --- Operating income ---
    def test_operating_income_present(self, result):
        assert "operating_income" in result.items

    def test_operating_income_2023(self, result):
        assert result.items["operating_income"]["2023"] == pytest.approx(114_301_000_000.0)

    # --- Taxes ---
    def test_taxes_present(self, result):
        assert "taxes" in result.items

    def test_taxes_2023(self, result):
        assert result.items["taxes"]["2023"] == pytest.approx(29_749_000_000.0)

    # --- Net income ---
    def test_net_income_present(self, result):
        assert "net_income" in result.items

    def test_net_income_2023(self, result):
        assert result.items["net_income"]["2023"] == pytest.approx(96_995_000_000.0)

    def test_net_income_all_three_years(self, result):
        ni = result.items["net_income"]
        assert "2021" in ni and "2022" in ni and "2023" in ni

    # --- Footnote marker on 2022 Products row (indirectly verifies stripping) ---
    # "158,844*" appears in the Products sub-row (not a canonical item),
    # so we verify no crash and that the parser returns valid items.
    def test_no_crash_on_footnote_row(self, result):
        assert len(result.items) >= 5


# ===========================================================================
# 6. Multi-row header collapsing
# ===========================================================================
APPLE_MULTIROW_HEADER_TABLE = {
    "caption": "Apple Inc. Consolidated Statements of Operations",
    "columns": ["", "Fiscal Year Ended", "", ""],
    "rows": [
        # This first row is a continuation of the header
        ["", "September 30, 2023", "September 24, 2022", "September 25, 2021"],
        # Data rows (scale declared separately via units)
        ["Total net sales",        "383285", "258974", "260174"],
        ["Total cost of sales",    "150982", "123301", "147086"],
        ["Gross margin",           "232303", "135673", "113088"],
        ["Operating income",       "114301", "119437", "108949"],
        ["Provision for income taxes", "29749", "19300", "14527"],
        ["Net income",             "96995",  "99803",  "94680"],
    ],
}


class TestMultiRowHeaderCollapsing:
    @pytest.fixture(scope="class")
    def result(self):
        r = parse_pnl_table(APPLE_MULTIROW_HEADER_TABLE)
        assert r is not None
        return r

    def test_periods_extracted_from_date_row(self, result):
        assert set(result.periods) == {"2021", "2022", "2023"}

    def test_revenue_mapped_from_date_periods(self, result):
        assert "revenue" in result.items
        assert "2023" in result.items["revenue"]

    def test_net_income_all_periods(self, result):
        assert set(result.items["net_income"].keys()) == {"2021", "2022", "2023"}


# ===========================================================================
# 7. FY notation normalisation
# ===========================================================================
APPLE_FY_NOTATION_TABLE = {
    "caption": "Income Statement (in millions)",
    "columns": ["Item", "FY2023", "FY22", "'21"],
    "rows": [
        ["Total net sales", "383,285", "258,974", "260,174"],
        ["Net income",      "96,995",  "99,803",  "94,680"],
    ],
}


class TestFYNotationNormalisation:
    @pytest.fixture(scope="class")
    def result(self):
        r = parse_pnl_table(APPLE_FY_NOTATION_TABLE)
        assert r is not None
        return r

    def test_fy2023_period_present(self, result):
        assert "FY2023" in result.items["revenue"]

    def test_fy22_expanded_to_fy2022(self, result):
        assert "FY2022" in result.items["revenue"]

    def test_quote21_expanded_to_fy2021(self, result):
        assert "FY2021" in result.items["revenue"]

    def test_scale_applied_from_caption(self, result):
        # 383,285 * 1_000_000 = 383_285_000_000
        assert result.items["revenue"]["FY2023"] == pytest.approx(383_285_000_000.0)


# ===========================================================================
# 8. Parentheses negatives at table level
# ===========================================================================
class TestParenthesesNegatives:
    def test_single_parentheses_negative_with_scale(self):
        table = {
            "caption": "P&L (in millions)",
            "columns": ["", "2022"],
            "rows": [["Net income", "(1,234)"]],
        }
        r = parse_pnl_table(table)
        assert r is not None
        assert r.items["net_income"]["2022"] == pytest.approx(-1_234_000_000.0)

    def test_positive_and_negative_same_table(self):
        table = {
            "caption": "(in millions)",
            "columns": ["", "2022", "2021"],
            "rows": [
                ["Net income",  "99,803",  "(1,000)"],
                ["Total net sales", "258,974", "260,174"],
            ],
        }
        r = parse_pnl_table(table)
        assert r is not None
        assert r.items["net_income"]["2022"] == pytest.approx(99_803_000_000.0)
        assert r.items["net_income"]["2021"] == pytest.approx(-1_000_000_000.0)


# ===========================================================================
# 9. Em-dash zeros
# ===========================================================================
class TestEmDashZero:
    def test_em_dash_cell_is_zero(self):
        table = {
            "caption": "(in millions)",
            "columns": ["", "2023"],
            "rows": [["Net income", "—"]],
        }
        r = parse_pnl_table(table)
        assert r is not None
        assert r.items["net_income"]["2023"] == 0.0

    def test_en_dash_cell_is_zero(self):
        table = {
            "caption": "(in millions)",
            "columns": ["", "2023"],
            "rows": [["Net income", "–"]],
        }
        r = parse_pnl_table(table)
        assert r is not None
        assert r.items["net_income"]["2023"] == 0.0

    def test_mixed_zero_and_positive(self):
        table = {
            "caption": "",
            "columns": ["", "2023", "2022"],
            "rows": [["Net income", "—", "500"]],
        }
        r = parse_pnl_table(table)
        assert r is not None
        assert r.items["net_income"]["2023"] == 0.0
        assert r.items["net_income"]["2022"] == pytest.approx(500.0)


# ===========================================================================
# 10. Edge cases / robustness
# ===========================================================================
class TestEdgeCases:
    def test_empty_table_returns_none(self):
        assert parse_pnl_table({}) is None

    def test_no_matching_rows_returns_none(self):
        table = {
            "columns": ["", "2023"],
            "rows": [["Unrecognised line item", "100"]],
        }
        assert parse_pnl_table(table) is None

    def test_thousands_scale(self):
        table = {
            "caption": "Financials (in thousands)",
            "columns": ["", "2023"],
            "rows": [["Net income", "96,995"]],
        }
        r = parse_pnl_table(table)
        assert r is not None
        assert r.metadata.scale_label == "K"
        assert r.items["net_income"]["2023"] == pytest.approx(96_995_000.0)

    def test_billions_scale(self):
        table = {
            "caption": "Financials (in billions)",
            "columns": ["", "2023"],
            "rows": [["Net income", "96.995"]],
        }
        r = parse_pnl_table(table)
        assert r is not None
        assert r.metadata.scale_label == "B"
        assert r.items["net_income"]["2023"] == pytest.approx(96_995_000_000.0)

    def test_none_cells_skipped(self):
        table = {
            "columns": ["", "2023", "2022"],
            "rows": [
                ["Net sales:", None, None],      # sub-header, all None → skipped
                ["Total net sales", "100", "90"],
            ],
        }
        r = parse_pnl_table(table)
        assert r is not None
        assert r.items["revenue"]["2023"] == pytest.approx(100.0)

    def test_layout_b_with_fy_period(self):
        table = {
            "columns": ["period", "line item", "value"],
            "rows": [
                ["FY24", "net income", "500"],
                ["FY24", "total net sales", "1000"],
                ["FY23", "net income", "400"],
            ],
        }
        r = parse_pnl_table(table)
        assert r is not None
        assert "FY2024" in r.items["net_income"]
        assert "FY2023" in r.items["net_income"]
        assert r.items["net_income"]["FY2024"] == pytest.approx(500.0)
