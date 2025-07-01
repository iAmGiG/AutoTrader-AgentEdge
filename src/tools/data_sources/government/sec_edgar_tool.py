"""
SEC EDGAR data source tool for retrieving SEC filings and performing analysis.

This tool provides access to SEC EDGAR (Electronic Data Gathering, Analysis, and Retrieval)
system for retrieving various types of SEC filings, extracting relevant sections,
and analyzing the content. It works primarily with 10-K, 10-Q, 8-K and other filing types.
"""

from src.utils.date_utils import process_date_param
from sec_edgar_downloader import Downloader
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import pandas as pd
import tempfile
import logging
import re
import os
from config.config_loader import ConfigLoader

config_loader = ConfigLoader()

# Define common form types for reference
FORM_TYPES = {
    "10-K": "Annual report",
    "10-Q": "Quarterly report",
    "8-K": "Current report (significant events)",
    "DEF 14A": "Proxy statement",
    "S-1": "Registration statement for new securities",
    "4": "Statement of changes in beneficial ownership",
    "13F": "Institutional investment manager holdings",
    "20-F": "Annual report for foreign issuers"
}

# Define sections of interest in 10-K/10-Q reports
REPORT_SECTIONS = {
    "risk_factors": ["risk factors", "item 1a", "item1a"],
    "management_discussion": ["management's discussion", "management discussion", "item 7", "item7"],
    "business": ["business", "item 1", "item1"],
    "legal_proceedings": ["legal proceedings", "item 3", "item3"],
    "financial_statements": ["financial statements", "item 8", "item8"],
    "controls_procedures": ["controls and procedures", "item 9a", "item9a"],
    "executive_compensation": ["executive compensation", "item 11", "item11"]
}

email = os.getenv("validEmail", config_loader.get("validEmail"))


class SECEdgarTool:
    """
    A tool for accessing SEC filings from the EDGAR database.

    This tool provides functionality to download and analyze various SEC filings,
    with particular focus on extracting relevant sections and insights from
    10-K and 10-Q reports. It allows for trend analysis over multiple filings
    and focused extraction of key sections.
    """

    def __init__(self, download_dir: Optional[str] = None, use_temp_dir: bool = False):
        """
        Initialize the SEC EDGAR tool.

        Args:
            download_dir: Directory to store downloaded filings. If None, uses "sec_filings"
            use_temp_dir: If True, uses a temporary directory instead
        """
        # Set up logger
        self.logger = logging.getLogger(self.__class__.__name__)

        # Determine download directory
        if use_temp_dir:
            self.download_dir = tempfile.mkdtemp(prefix="sec_filings_")
            self.logger.info(
                f"Using temporary directory for SEC filings: {self.download_dir}")
        else:
            self.download_dir = download_dir or "sec_filings"
            # Ensure the directory exists
            os.makedirs(self.download_dir, exist_ok=True)

        # Initialize the downloader
        # The email is required by SEC EDGAR for tracking purposes
        self.downloader = Downloader(
            company_name="RH2MAS Research",
            email_address=email,  # Your email for EDGAR tracking
            download_folder=self.download_dir
        )

        # Store form types and sections for reference
        self.form_types = FORM_TYPES
        self.report_sections = REPORT_SECTIONS

    def download_filing(self, ticker: str, form_type: str = "10-K",
                        limit: int = 1, after: Optional[str] = None, before: Optional[str] = None) -> List[str]:
        """
        Download SEC filings for a specific company.

        Args:
            ticker: Stock ticker symbol
            form_type: Type of SEC form (e.g., '10-K', '10-Q', '8-K')
            limit: Maximum number of filings to download
            after: Only download filings after this date (YYYY-MM-DD)
            before: Only download filings before this date (YYYY-MM-DD)

        Returns:
            List of paths to downloaded filings
        """
        try:
            self.logger.info(
                f"Downloading {form_type} filings for {ticker}...")

            # Process date parameters
            if after:
                after = process_date_param(after)
            if before:
                before = process_date_param(before)

            # Download filings
            self.downloader.get(
                ticker=ticker.upper(),
                filing_type=form_type,
                limit=limit,
                after=after,
                before=before
            )

            # Find downloaded files
            company_dir = os.path.join(
                self.download_dir, f"sec_edgar_filings/{ticker.upper()}/{form_type}")
            filing_paths = []

            if os.path.exists(company_dir):
                for root, dirs, files in os.walk(company_dir):
                    for file in files:
                        if file.endswith(".txt") or file.endswith(".html"):
                            filing_paths.append(os.path.join(root, file))

            self.logger.info(f"Downloaded {len(filing_paths)} filings")
            return filing_paths

        except Exception as e:
            self.logger.error(f"Error downloading filings: {e}")
            return []

    def extract_section(self, filing_path: str, section_name: str) -> str:
        """
        Extract a specific section from a filing.

        Args:
            filing_path: Path to the filing file
            section_name: Name of section to extract (e.g., 'risk_factors', 'management_discussion')

        Returns:
            Extracted text content
        """
        try:
            # Read the filing
            with open(filing_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Parse with BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text()

            # Look for section markers
            if section_name in self.report_sections:
                markers = self.report_sections[section_name]

                # Find section start
                section_start = -1
                for marker in markers:
                    pattern = re.compile(
                        rf"(?i)(?:^|\n)\s*{re.escape(marker)}", re.MULTILINE)
                    match = pattern.search(text)
                    if match:
                        section_start = match.end()
                        break

                if section_start == -1:
                    self.logger.warning(
                        f"Section '{section_name}' not found in filing")
                    return ""

                # Find next section (approximate end)
                # Look for common section markers
                next_section_markers = [
                    r"(?i)(?:^|\n)\s*item\s+\d+[a-z]?\.?\s*",
                    r"(?i)(?:^|\n)\s*part\s+[IVX]+",
                    r"(?i)(?:^|\n)\s*signatures"
                ]

                section_end = len(text)
                for marker in next_section_markers:
                    pattern = re.compile(marker)
                    matches = list(pattern.finditer(text[section_start:]))
                    if matches:
                        # Find the closest next section
                        closest_end = min(match.start() for match in matches)
                        section_end = section_start + closest_end
                        break

                # Extract section text
                section_text = text[section_start:section_end].strip()

                # Clean up the text
                section_text = re.sub(r'\s+', ' ', section_text)  # Normalize whitespace
                section_text = re.sub(
                    r'[-=]{3,}', '', section_text)  # Remove dividers

                return section_text[:50000]  # Limit length for processing

            else:
                self.logger.error(f"Unknown section name: {section_name}")
                return ""

        except Exception as e:
            self.logger.error(f"Error extracting section: {e}")
            return ""

    def analyze_filing(self, ticker: str, form_type: str = "10-K",
                       sections: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Download and analyze the most recent filing for a company.

        Args:
            ticker: Stock ticker symbol
            form_type: Type of SEC form
            sections: List of sections to extract. If None, extracts all standard sections

        Returns:
            Dictionary with analysis results
        """
        try:
            # Download the most recent filing
            filing_paths = self.download_filing(ticker, form_type, limit=1)

            if not filing_paths:
                self.logger.warning(f"No {form_type} filing found for {ticker}")
                return {}

            filing_path = filing_paths[0]

            # Determine which sections to extract
            if sections is None:
                sections = list(self.report_sections.keys())

            # Extract sections
            results = {
                "ticker": ticker.upper(),
                "form_type": form_type,
                "filing_path": filing_path,
                "sections": {}
            }

            for section in sections:
                if section in self.report_sections:
                    content = self.extract_section(filing_path, section)
                    if content:
                        results["sections"][section] = {
                            "content": content,
                            "length": len(content),
                            "preview": content[:500] + "..." if len(content) > 500 else content
                        }

            return results

        except Exception as e:
            self.logger.error(f"Error analyzing filing: {e}")
            return {}

    def get_filing_trends(self, ticker: str, form_type: str = "10-K",
                          section: str = "risk_factors", limit: int = 3) -> pd.DataFrame:
        """
        Analyze trends in a specific section across multiple filings.

        Args:
            ticker: Stock ticker symbol
            form_type: Type of SEC form
            section: Section to analyze
            limit: Number of filings to analyze

        Returns:
            DataFrame with trend analysis
        """
        try:
            # Download multiple filings
            filing_paths = self.download_filing(ticker, form_type, limit=limit)

            if not filing_paths:
                self.logger.warning(
                    f"No {form_type} filings found for {ticker}")
                return pd.DataFrame()

            trend_data = []

            for filing_path in filing_paths:
                # Extract filing date from path
                date_match = re.search(r'/(\d{4}-\d{2}-\d{2})/', filing_path)
                filing_date = date_match.group(
                    1) if date_match else "Unknown"

                # Extract section
                content = self.extract_section(filing_path, section)

                if content:
                    # Basic analysis
                    word_count = len(content.split())
                    sentence_count = len(
                        re.split(r'[.!?]+', content)) - 1  # Subtract 1 for empty split

                    # Look for specific keywords (example for risk factors)
                    risk_keywords = ['risk', 'uncertainty', 'volatility',
                                     'competition', 'regulation', 'cyber', 'pandemic']
                    keyword_counts = {
                        kw: len(re.findall(rf'\b{kw}\b', content, re.IGNORECASE))
                        for kw in risk_keywords
                    }

                    trend_data.append({
                        'filing_date': filing_date,
                        'word_count': word_count,
                        'sentence_count': sentence_count,
                        'avg_sentence_length': word_count / sentence_count if sentence_count > 0 else 0,
                        **keyword_counts,
                        'total_risk_mentions': sum(keyword_counts.values())
                    })

            if trend_data:
                df = pd.DataFrame(trend_data)
                df['filing_date'] = pd.to_datetime(df['filing_date'])
                df = df.sort_values('filing_date')
                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Error analyzing filing trends: {e}")
            return pd.DataFrame()

    def search_filings(self, ticker: str, search_terms: List[str],
                       form_type: str = "8-K", limit: int = 5) -> pd.DataFrame:
        """
        Search for specific terms across multiple filings.

        Args:
            ticker: Stock ticker symbol
            search_terms: List of terms to search for
            form_type: Type of SEC form to search
            limit: Maximum number of filings to search

        Returns:
            DataFrame with search results
        """
        try:
            # Download filings
            filing_paths = self.download_filing(ticker, form_type, limit=limit)

            if not filing_paths:
                self.logger.warning(
                    f"No {form_type} filings found for {ticker}")
                return pd.DataFrame()

            search_results = []

            for filing_path in filing_paths:
                # Extract filing date
                date_match = re.search(r'/(\d{4}-\d{2}-\d{2})/', filing_path)
                filing_date = date_match.group(
                    1) if date_match else "Unknown"

                # Read filing content
                with open(filing_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Parse and get text
                soup = BeautifulSoup(content, 'html.parser')
                text = soup.get_text().lower()

                # Search for terms
                for term in search_terms:
                    pattern = re.compile(
                        rf'\b{re.escape(term.lower())}\b')
                    matches = list(pattern.finditer(text))

                    if matches:
                        # Extract context around matches
                        contexts = []
                        for match in matches[:3]:  # Limit to first 3 matches
                            start = max(0, match.start() - 100)
                            end = min(len(text), match.end() + 100)
                            context = text[start:end].strip()
                            context = re.sub(r'\s+', ' ', context)
                            contexts.append(context)

                        search_results.append({
                            'filing_date': filing_date,
                            'form_type': form_type,
                            'search_term': term,
                            'match_count': len(matches),
                            'contexts': contexts[:2]  # Limit contexts
                        })

            if search_results:
                return pd.DataFrame(search_results)
            else:
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Error searching filings: {e}")
            return pd.DataFrame()

    def get_recent_8k_events(self, ticker: str, days_back: int = 30) -> pd.DataFrame:
        """
        Get recent 8-K filings to identify significant events.

        Args:
            ticker: Stock ticker symbol
            days_back: Number of days to look back

        Returns:
            DataFrame with recent 8-K events
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            # Download 8-K filings
            filing_paths = self.download_filing(
                ticker, "8-K",
                limit=10,  # Get multiple 8-Ks
                after=start_date.strftime('%Y-%m-%d')
            )

            if not filing_paths:
                self.logger.warning(f"No recent 8-K filings found for {ticker}")
                return pd.DataFrame()

            events = []

            # Common 8-K item numbers and their meanings
            item_descriptions = {
                "1.01": "Entry into a Material Definitive Agreement",
                "1.02": "Termination of a Material Definitive Agreement",
                "2.01": "Completion of Acquisition or Disposition of Assets",
                "2.02": "Results of Operations and Financial Condition",
                "2.03": "Creation of a Direct Financial Obligation",
                "3.01": "Notice of Delisting or Transfer of Listing",
                "4.01": "Changes in Registrant's Certifying Accountant",
                "5.01": "Changes in Control of Registrant",
                "5.02": "Departure/Election of Directors or Officers",
                "7.01": "Regulation FD Disclosure",
                "8.01": "Other Events"
            }

            for filing_path in filing_paths:
                # Extract filing date
                date_match = re.search(r'/(\d{4}-\d{2}-\d{2})/', filing_path)
                filing_date = date_match.group(
                    1) if date_match else "Unknown"

                # Read filing
                with open(filing_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Parse and extract text
                soup = BeautifulSoup(content, 'html.parser')
                text = soup.get_text()

                # Look for item numbers
                item_pattern = re.compile(
                    r'item\s+(\d+\.\d+)', re.IGNORECASE)
                items_found = item_pattern.findall(text)

                if items_found:
                    for item in set(items_found):  # Unique items
                        events.append({
                            'filing_date': filing_date,
                            'item_number': item,
                            'item_description': item_descriptions.get(item, "Other"),
                            'filing_path': filing_path
                        })

            if events:
                df = pd.DataFrame(events)
                df['filing_date'] = pd.to_datetime(df['filing_date'])
                df = df.sort_values('filing_date', ascending=False)
                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(f"Error getting recent 8-K events: {e}")
            return pd.DataFrame()

    def test_connection(self) -> bool:
        """
        Test the SEC EDGAR connection by attempting a small download.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to download one Apple 8-K as a test
            test_paths = self.download_filing("AAPL", "8-K", limit=1)
            return len(test_paths) > 0
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False


if __name__ == "__main__":
    # Example usage
    tool = SECEdgarTool(use_temp_dir=True)

    # Test connection
    print("Testing SEC EDGAR connection...")
    if tool.test_connection():
        print("✓ Connection successful!")
    else:
        print("✗ Connection failed!")

    # Analyze Apple's latest 10-K
    print("\nAnalyzing Apple's latest 10-K...")
    analysis = tool.analyze_filing("AAPL", "10-K", sections=["risk_factors"])
    if analysis and "sections" in analysis:
        for section, data in analysis["sections"].items():
            print(f"\n{section.upper()}:")
            print(f"Length: {data['length']} characters")
            print(f"Preview: {data['preview']}")

    # Get trend analysis
    print("\nAnalyzing risk factor trends...")
    trends = tool.get_filing_trends("AAPL", "10-K", "risk_factors", limit=3)
    if not trends.empty:
        print(trends[['filing_date', 'word_count', 'total_risk_mentions']])

    # Search for specific terms
    print("\nSearching for AI mentions in recent filings...")
    search_results = tool.search_filings(
        "MSFT", ["artificial intelligence", "AI", "machine learning"], "10-K", limit=1)
    if not search_results.empty:
        print(search_results[['filing_date', 'search_term', 'match_count']])

    # Get recent 8-K events
    print("\nGetting recent 8-K events for Tesla...")
    events = tool.get_recent_8k_events("TSLA", days_back=60)
    if not events.empty:
        print(events[['filing_date', 'item_number', 'item_description']])