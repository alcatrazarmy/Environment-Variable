#!/usr/bin/env python3
"""Tests for the permit scraper."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from scraper import (
    Config,
    PermitRecord,
    get_nested_value,
    scrape_api_source,
    scrape_html_source,
)


class TestPermitRecord:
    """Tests for PermitRecord model."""

    def test_create_basic_record(self):
        """Test creating a basic permit record."""
        record = PermitRecord(
            permit_number="123",
            address="123 Main St",
            city="Anytown",
            state="CA",
            zip="90210",
            source_name="TestSource",
        )
        assert record.permit_number == "123"
        assert record.address == "123 Main St"
        assert record.source_name == "TestSource"

    def test_parse_estimated_value_with_currency(self):
        """Test parsing estimated value with currency symbols."""
        record = PermitRecord(estimated_value="$1,234.56")
        assert record.estimated_value == 1234.56

    def test_parse_estimated_value_plain_number(self):
        """Test parsing estimated value as plain number."""
        record = PermitRecord(estimated_value=5000)
        assert record.estimated_value == 5000.0

    def test_parse_estimated_value_empty(self):
        """Test parsing empty estimated value."""
        record = PermitRecord(estimated_value="")
        assert record.estimated_value is None

    def test_parse_issue_date(self):
        """Test parsing issue date."""
        record = PermitRecord(issue_date="2024-01-15")
        assert record.issue_date == "2024-01-15"

    def test_parse_issue_date_various_formats(self):
        """Test parsing issue date with various formats."""
        record = PermitRecord(issue_date="January 15, 2024")
        assert record.issue_date == "2024-01-15"

    def test_generate_hash(self):
        """Test hash generation for deduplication."""
        record = PermitRecord(
            permit_number="123",
            address="123 Main St",
            source_name="TestSource",
        )
        hash_id = record.generate_hash()
        assert len(hash_id) == 16
        assert hash_id.isalnum()


class TestGetNestedValue:
    """Tests for get_nested_value helper function."""

    def test_simple_key(self):
        """Test getting simple key."""
        data = {"name": "John"}
        assert get_nested_value(data, "name") == "John"

    def test_nested_key(self):
        """Test getting nested key."""
        data = {"address": {"street": "123 Main St"}}
        assert get_nested_value(data, "address.street") == "123 Main St"

    def test_deeply_nested_key(self):
        """Test getting deeply nested key."""
        data = {"a": {"b": {"c": "value"}}}
        assert get_nested_value(data, "a.b.c") == "value"

    def test_missing_key(self):
        """Test getting missing key returns None."""
        data = {"name": "John"}
        assert get_nested_value(data, "missing") is None

    def test_missing_nested_key(self):
        """Test getting missing nested key returns None."""
        data = {"address": {"city": "Boston"}}
        assert get_nested_value(data, "address.street") is None


class TestConfig:
    """Tests for Config model."""

    def test_default_config(self):
        """Test default configuration."""
        config = Config()
        assert config.days_back == 30
        assert config.geocode["enabled"] is False
        assert config.airtable["enabled"] is False
        assert config.sources == []

    def test_custom_config(self):
        """Test custom configuration."""
        config = Config(
            days_back=7,
            sources=[{"name": "TestSource", "mode": "api", "url": "https://example.com"}],
        )
        assert config.days_back == 7
        assert len(config.sources) == 1


class TestScrapeApiSource:
    """Tests for scrape_api_source function."""

    @patch("scraper.fetch_url")
    def test_scrape_api_source(self, mock_fetch):
        """Test scraping an API source."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "permitNumber": "P001",
                    "issueDate": datetime.now().strftime("%Y-%m-%d"),
                    "address": {"street": "123 Main St"},
                }
            ]
        }
        mock_fetch.return_value = mock_response

        source = {
            "name": "TestAPI",
            "url": "https://api.example.com/permits",
            "list_path": "results",
            "mapping": {
                "permit_number": "permitNumber",
                "issue_date": "issueDate",
                "address": "address.street",
            },
        }

        records = scrape_api_source(source, days_back=30)
        assert len(records) == 1
        assert records[0].permit_number == "P001"
        assert records[0].address == "123 Main St"

    def test_scrape_api_source_no_url(self):
        """Test scraping API source without URL."""
        source = {"name": "NoURL"}
        records = scrape_api_source(source, days_back=30)
        assert len(records) == 0


class TestScrapeHtmlSource:
    """Tests for scrape_html_source function."""

    @patch("scraper.fetch_url")
    def test_scrape_html_source(self, mock_fetch):
        """Test scraping an HTML source."""
        today = datetime.now().strftime("%Y-%m-%d")
        mock_response = MagicMock()
        mock_response.text = f"""
        <html>
        <table id="permits">
            <tr class="data">
                <td>P001</td>
                <td>{today}</td>
                <td>123 Main St</td>
            </tr>
        </table>
        </html>
        """
        mock_fetch.return_value = mock_response

        source = {
            "name": "TestHTML",
            "url": "https://example.com/permits",
            "row_selector": "table#permits tr.data",
            "fields": {
                "permit_number": "td:nth-child(1)::text",
                "issue_date": "td:nth-child(2)::text",
                "address": "td:nth-child(3)::text",
            },
        }

        records = scrape_html_source(source, days_back=30)
        assert len(records) == 1
        assert records[0].permit_number == "P001"
        assert records[0].address == "123 Main St"

    def test_scrape_html_source_no_url(self):
        """Test scraping HTML source without URL."""
        source = {"name": "NoURL"}
        records = scrape_html_source(source, days_back=30)
        assert len(records) == 0

    def test_scrape_html_source_no_selector(self):
        """Test scraping HTML source without row selector."""
        source = {"name": "NoSelector", "url": "https://example.com"}
        records = scrape_html_source(source, days_back=30)
        assert len(records) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
