"""
SEC EDGAR data source tool for retrieving SEC filings and performing analysis.

This tool provides access to SEC EDGAR (Electronic Data Gathering, Analysis, and Retrieval)
system for retrieving various types of SEC filings, extracting relevant sections,
and analyzing the content. It works primarily with 10-K, 10-Q, 8-K and other filing types.
"""

import os
import re
import logging
import tempfile
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from sec_edgar_downloader import Downloader
from src.tools.date_utils import process_date_param

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

        # Create a downloader instance
        self.downloader = Downloader(self.download_dir)

        # Store the form types and section definitions
        self.form_types = FORM_TYPES
        self.report_sections = REPORT_SECTIONS

    def fetch_filings(self,
                      ticker: str,
                      form_type: str = "10-K",
                      num_filings: int = 1,
                      before_date: Optional[str] = None,
                      after_date: Optional[str] = None,
                      extract_sections: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Fetch SEC filings for a company and extract relevant data.

        Args:
            ticker: Company ticker symbol (e.g., 'AAPL')
            form_type: Type of SEC form to retrieve (e.g., '10-K', '10-Q', '8-K')
            num_filings: Number of filings to retrieve
            before_date: Get filings before this date (YYYY-MM-DD or relative date like "today")
            after_date: Get filings after this date (YYYY-MM-DD or relative date like "-1y")
            extract_sections: List of sections to extract (e.g., ['risk_factors', 'business'])

        Returns:
            DataFrame with filing data including dates, sections, and metrics
        """
        try:
            # Validate input
            ticker = ticker.upper()  # Ensure ticker is uppercase
            if form_type not in FORM_TYPES and form_type not in FORM_TYPES.values():
                self.logger.warning(
                    f"Form type '{form_type}' is not in the standard list.")

            # Process date parameters using date_utils
            date_kwargs = {}
            if before_date:
                processed_before = process_date_param(before_date)
                if processed_before:
                    date_kwargs['before_date'] = processed_before

            if after_date:
                processed_after = process_date_param(after_date)
                if processed_after:
                    date_kwargs['after_date'] = processed_after

            # Download the filings
            self.logger.info(
                f"Downloading {num_filings} {form_type} filings for {ticker}")
            result = self.downloader.get(
                form_type, ticker, amount=num_filings, **date_kwargs)

            # Get the path where filings were saved
            filing_path = os.path.join(self.download_dir, ticker, form_type)

            if not os.path.exists(filing_path):
                self.logger.error(f"Filing path not found: {filing_path}")
                return pd.DataFrame()

            # Process the downloaded filings
            return self._process_filings(filing_path, ticker, form_type, extract_sections)

        except Exception as e:
            self.logger.error(
                f"Error fetching {form_type} filings for {ticker}: {e}")
            return pd.DataFrame()

    def _process_filings(self,
                         filing_path: str,
                         ticker: str,
                         form_type: str,
                         extract_sections: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Process downloaded filings and extract relevant information.

        Args:
            filing_path: Path to the downloaded filings
            ticker: Company ticker symbol
            form_type: Type of SEC form
            extract_sections: List of sections to extract

        Returns:
            DataFrame with processed filing data
        """
        data = []

        # Default to extracting risk factors if not specified
        sections_to_extract = extract_sections or ["risk_factors"]

        # List files in the filing directory
        try:
            files = [f for f in os.listdir(filing_path) if f.endswith('.txt')]
            self.logger.info(f"Found {len(files)} filing files to process")

            for file in files:
                file_path = os.path.join(filing_path, file)

                # Parse the filing date from the filename or file content
                filing_date = self._extract_filing_date(file_path, file)

                # Extract content for each requested section
                section_contents = {}
                for section in sections_to_extract:
                    if section in self.report_sections:
                        content = self._extract_section(file_path, section)
                        section_contents[section] = content
                    else:
                        self.logger.warning(f"Unknown section: {section}")
                        section_contents[section] = ""

                # Create the data record
                record = {
                    'ticker': ticker,
                    'form_type': form_type,
                    'filing_date': filing_date,
                    'file_name': file,
                    'file_path': file_path
                }

                # Add section contents
                for section, content in section_contents.items():
                    record[f'{section}_content'] = content
                    record[f'{section}_length'] = len(
                        content) if content else 0

                # Calculate metrics if we have risk factors
                if 'risk_factors_content' in record and record['risk_factors_content']:
                    metrics = self._calculate_metrics(
                        record['risk_factors_content'])
                    record.update(metrics)

                data.append(record)

            # Create DataFrame
            df = pd.DataFrame(data)

            # Convert filing_date to datetime if it's not already
            if 'filing_date' in df.columns and not pd.api.types.is_datetime64_dtype(df['filing_date']):
                df['filing_date'] = pd.to_datetime(
                    df['filing_date'], errors='coerce')

            # Sort by filing date descending
            if 'filing_date' in df.columns:
                df = df.sort_values('filing_date', ascending=False)

            return df

        except Exception as e:
            self.logger.error(f"Error processing filings: {e}")
            return pd.DataFrame()

    def _extract_filing_date(self, file_path: str, file_name: str) -> str:
        """
        Extract the filing date from either the filename or content.

        Args:
            file_path: Path to the filing file
            file_name: Name of the filing file

        Returns:
            Filing date as string in YYYY-MM-DD format
        """
        # Try to extract from filename first (SEC format often includes date)
        date_match = re.search(r'(\d{8})', file_name)
        if date_match:
            date_str = date_match.group(1)
            try:
                # Convert from YYYYMMDD to YYYY-MM-DD
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            except Exception:
                pass

        # If that fails, try to extract from content
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read just the beginning to look for date
                content = f.read(10000)

                # Look for common date patterns
                # Format: YYYY-MM-DD
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', content)
                if date_match:
                    return date_match.group(1)

                # Format: MM/DD/YYYY
                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', content)
                if date_match:
                    date_parts = date_match.group(1).split('/')
                    if len(date_parts) == 3:
                        month, day, year = date_parts
                        return f"{year}-{int(month):02d}-{int(day):02d}"
        except Exception as e:
            self.logger.warning(f"Error extracting date from content: {e}")

        # Default to file modification date if all else fails
        try:
            mod_time = os.path.getmtime(file_path)
            dt = datetime.fromtimestamp(mod_time)
            return dt.strftime("%Y-%m-%d")
        except Exception as e:
            self.logger.warning(f"Error getting file modification date: {e}")

        # Last resort, use today's date from date_utils
        return process_date_param("today")

    def _extract_section(self, file_path: str, section_name: str) -> str:
        """
        Extract a specific section from a filing.

        Args:
            file_path: Path to the filing file
            section_name: Name of the section to extract (e.g., 'risk_factors')

        Returns:
            Text content of the extracted section
        """
        if section_name not in self.report_sections:
            self.logger.warning(f"Unknown section: {section_name}")
            return ""

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Parse with BeautifulSoup to handle HTML structure
            soup = BeautifulSoup(content, 'html.parser')
            text_content = soup.get_text(separator=' ')

            # Normalize whitespace
            text_content = re.sub(r'\s+', ' ', text_content).strip()

            # Look for section markers
            section_markers = self.report_sections[section_name]
            for marker in section_markers:
                pattern = re.compile(
                    rf'(item\s*{marker.replace("item", "")}[\s.:]+.*?)(item\s*\d)', re.IGNORECASE | re.DOTALL)
                match = pattern.search(text_content)
                if match:
                    return match.group(1).strip()

            # Try more general pattern for finding the section
            for marker in section_markers:
                pattern = rf'{marker}'
                index = text_content.lower().find(pattern)
                if index >= 0:
                    # Extract from this position to the next likely section
                    next_section_match = re.search(
                        r'item\s*\d', text_content.lower()[index+len(pattern):])
                    if next_section_match:
                        end_pos = index + len(pattern) + \
                            next_section_match.start()
                        return text_content[index:end_pos].strip()
                    else:
                        # If no next section, take a reasonable chunk
                        chunk_size = min(20000, len(text_content) - index)
                        return text_content[index:index+chunk_size].strip()

            return ""

        except Exception as e:
            self.logger.error(
                f"Error extracting {section_name} from {file_path}: {e}")
            return ""

    def _calculate_metrics(self, text: str) -> Dict[str, float]:
        """
        Calculate text-based metrics for analysis.

        Args:
            text: Text content to analyze

        Returns:
            Dictionary of calculated metrics
        """
        metrics = {}

        if not text:
            return {
                'word_count': 0,
                'avg_sentence_length': 0,
                'complexity_score': 0
            }

        try:
            # Calculate word count
            words = re.findall(r'\b\w+\b', text)
            metrics['word_count'] = len(words)

            # Estimate average sentence length
            sentences = re.split(r'[.!?]+', text)
            valid_sentences = [s for s in sentences if len(s.strip()) > 0]
            if valid_sentences:
                total_words = sum(len(re.findall(r'\b\w+\b', s))
                                  for s in valid_sentences)
                metrics['avg_sentence_length'] = total_words / \
                    len(valid_sentences)
            else:
                metrics['avg_sentence_length'] = 0

            # Simple complexity score (based on word length)
            if words:
                avg_word_length = sum(len(word) for word in words) / len(words)
                metrics['complexity_score'] = avg_word_length * \
                    metrics['avg_sentence_length'] / 10
            else:
                metrics['complexity_score'] = 0

        except Exception as e:
            self.logger.error(f"Error calculating metrics: {e}")
            metrics = {
                'word_count': 0,
                'avg_sentence_length': 0,
                'complexity_score': 0
            }

        return metrics

    def search_filings(self,
                    ticker: str,
                    search_terms: list,
                    form_type: str = "10-K",
                    section: str = None,
                    num_filings: int = 3) -> pd.DataFrame:
        """
        Search SEC filings for specific terms and return matches with context.
        
        Args:
            ticker: Company ticker symbol
            search_terms: List of terms to search for
            form_type: Type of SEC form
            section: Specific section to search (if None, searches entire document)
            num_filings: Number of filings to search
            
        Returns:
            DataFrame with search results and context
        """
        try:
            # Get the filings
            if section:
                extract_sections = [section]
            else:
                # If no specific section, use all standard sections
                extract_sections = list(self.report_sections.keys())
                
            filings_df = self.fetch_filings(
                ticker=ticker,
                form_type=form_type,
                num_filings=num_filings,
                extract_sections=extract_sections
            )
            
            if filings_df.empty:
                self.logger.warning(f"No filings found for {ticker} ({form_type})")
                return pd.DataFrame()
                
            # Prepare results dataframe
            results = []
            
            # Search through each filing and section
            for _, filing in filings_df.iterrows():
                for sec in extract_sections:
                    content_col = f"{sec}_content"
                    
                    # Skip if the section content is not available
                    if content_col not in filing or pd.isna(filing[content_col]) or not filing[content_col]:
                        continue
                        
                    content = filing[content_col]
                    
                    # Search for each term
                    for term in search_terms:
                        # Case-insensitive search
                        occurrences = re.finditer(re.escape(term), content, re.IGNORECASE)
                        
                        for match in occurrences:
                            # Get context around the match
                            start = max(0, match.start() - 100)
                            end = min(len(content), match.end() + 100)
                            
                            context = content[start:end]
                            
                            # Add to results
                            results.append({
                                'ticker': ticker,
                                'form_type': form_type,
                                'filing_date': filing['filing_date'],
                                'section': sec,
                                'search_term': term,
                                'context': context,
                                'file_path': filing.get('file_path', '')
                            })
            
            # Convert to DataFrame
            results_df = pd.DataFrame(results)
            
            # Sort by filing date (newest first)
            if not results_df.empty and 'filing_date' in results_df.columns:
                results_df = results_df.sort_values('filing_date', ascending=False)
                
            return results_df
            
        except Exception as e:
            self.logger.error(f"Error searching SEC filings: {e}")
            return pd.DataFrame()
            
    def compare_filings_over_time(self,
                                  ticker: str,
                                  form_type: str = "10-K",
                                  section: str = "risk_factors",
                                  num_filings: int = 5) -> pd.DataFrame:
        """
        Compare filing sections over time to identify changes.

        Args:
            ticker: Company ticker symbol
            form_type: Type of SEC form
            section: Section to compare
            num_filings: Number of filings to compare

        Returns:
            DataFrame with comparison metrics between filings
        """
        try:
            # Get the filings
            filings_df = self.fetch_filings(
                ticker=ticker,
                form_type=form_type,
                num_filings=num_filings,
                extract_sections=[section]
            )

            if filings_df.empty:
                self.logger.warning(
                    f"No filings found for {ticker} ({form_type})")
                return pd.DataFrame()

            # If we have at least 2 filings, calculate changes
            if len(filings_df) >= 2:
                # Sort by filing date
                filings_df = filings_df.sort_values('filing_date')

                # Calculate year-over-year changes for metrics
                for metric in ['word_count', 'avg_sentence_length', 'complexity_score']:
                    if metric in filings_df.columns:
                        filings_df[f'{metric}_change'] = filings_df[metric].pct_change(
                        ) * 100

                # Add percentage growth in text length
                content_col = f'{section}_length'
                if content_col in filings_df.columns:
                    filings_df[f'{section}_length_change'] = filings_df[content_col].pct_change(
                    ) * 100

            return filings_df

        except Exception as e:
            self.logger.error(f"Error comparing filings: {e}")
            return pd.DataFrame()

    def search_filings(self,
                       ticker: str,
                       search_terms: List[str],
                       form_type: str = "10-K",
                       section: Optional[str] = None,
                       num_filings: int = 3) -> pd.DataFrame:
        """
        Search SEC filings for specific terms and return results.

        Args:
            ticker: Company ticker symbol
            search_terms: List of terms to search for
            form_type: Type of SEC form
            section: Specific section to search within (if None, searches entire filing)
            num_filings: Number of filings to search

        Returns:
            DataFrame with search results and context
        """
        try:
            # Extract sections if specified
            sections_to_extract = [section] if section else list(
                self.report_sections.keys())

            # Get the filings - use date_utils for default date handling
            filings_df = self.fetch_filings(
                ticker=ticker,
                form_type=form_type,
                num_filings=num_filings,
                extract_sections=sections_to_extract
            )

            if filings_df.empty:
                self.logger.warning(
                    f"No filings found for {ticker} ({form_type})")
                return pd.DataFrame()

            # Initialize results
            search_results = []

            # For each filing
            for _, filing in filings_df.iterrows():
                # Determine which content to search
                if section:
                    content_col = f'{section}_content'
                    content = filing.get(content_col, "")
                    sections_to_search = [section]
                else:
                    # Combine all section contents
                    sections_to_search = []
                    content = ""
                    for s in self.report_sections:
                        content_col = f'{s}_content'
                        if content_col in filing and filing[content_col]:
                            content += filing[content_col] + " "
                            sections_to_search.append(s)

                # Search for each term
                for term in search_terms:
                    # Compile regex pattern for word boundaries
                    pattern = re.compile(
                        rf'\b{re.escape(term)}\b', re.IGNORECASE)
                    matches = pattern.finditer(content)

                    # Process each match
                    for match in matches:
                        # Get context around the match (100 chars before and after)
                        start = max(0, match.start() - 100)
                        end = min(len(content), match.end() + 100)
                        context = content[start:end]

                        # Highlight the match in context
                        match_start = match.start() - start
                        match_end = match.end() - start
                        highlighted = (
                            context[:match_start] +
                            "**" + context[match_start:match_end] + "**" +
                            context[match_end:]
                        )

                        # Determine which section this match is from
                        match_section = section if section else self._identify_section(
                            content, match.start(), sections_to_search)

                        # Add to results
                        search_results.append({
                            'ticker': ticker,
                            'form_type': form_type,
                            'filing_date': filing.get('filing_date', ''),
                            'search_term': term,
                            'section': match_section,
                            'context': highlighted
                        })

            # Create DataFrame from results
            results_df = pd.DataFrame(search_results)

            # Sort by filing date and then by section
            if not results_df.empty and 'filing_date' in results_df.columns:
                results_df = results_df.sort_values(
                    ['filing_date', 'section'], ascending=[False, True])

            return results_df

        except Exception as e:
            self.logger.error(f"Error searching filings: {e}")
            return pd.DataFrame()

    def _identify_section(self, content: str, position: int, sections: List[str]) -> str:
        """
        Identify which section a matched position belongs to.

        Args:
            content: Full content text
            position: Match position within the content
            sections: List of sections to check

        Returns:
            Name of the section containing the position
        """
        # Simple approach: Each section is calculated to start after the previous
        # one ended, so we use section name and its position in the list to infer
        curr_pos = 0
        for section in sections:
            content_col = f'{section}_content'
            section_length = len(content_col)
            if curr_pos <= position < curr_pos + section_length:
                return section
            curr_pos += section_length

        return "unknown"

    def get_key_facts(self, ticker: str) -> Dict[str, Any]:
        """
        Extract key facts about a company from its latest annual report.

        Args:
            ticker: Company ticker symbol

        Returns:
            Dictionary containing key facts about the company
        """
        try:
            # Get the latest 10-K using current date handling
            filings_df = self.fetch_filings(
                ticker=ticker,
                form_type="10-K",
                num_filings=1,
                before_date="today",
                extract_sections=["business", "risk_factors"]
            )

            if filings_df.empty:
                self.logger.warning(f"No 10-K filings found for {ticker}")
                return {}

            # Extract the first row (latest filing)
            filing = filings_df.iloc[0]

            # Initialize key facts
            facts = {
                'ticker': ticker,
                'filing_date': filing.get('filing_date', ''),
                'form_type': '10-K',
                'company_profile': self._extract_company_profile(filing.get('business_content', '')),
                'risk_count': filing.get('word_count', 0),
                'risk_complexity': filing.get('complexity_score', 0)
            }

            return facts

        except Exception as e:
            self.logger.error(f"Error getting key facts for {ticker}: {e}")
            return {}

    def _extract_company_profile(self, business_section: str) -> str:
        """
        Extract a concise company profile from the business section.

        Args:
            business_section: Business section text from a 10-K

        Returns:
            Concise company profile text
        """
        if not business_section:
            return ""

        # Take first 1000 characters as a simple approach
        # (In a more sophisticated implementation, we'd use NLP to summarize)
        profile = business_section[:1000].strip()

        # Clean up the profile
        profile = re.sub(r'\s+', ' ', profile)

        return profile

    def clean_up(self, days_old: int = 7):
        """
        Clean up old downloaded files to save disk space.

        Args:
            days_old: Remove files older than this many days
        """
        try:
            # Don't clean up temporary directories
            if '/tmp/' in self.download_dir or 'temp' in self.download_dir:
                return

            # Use date_utils for date calculations
            current_date = process_date_param("today")
            current_datetime = datetime.strptime(current_date, '%Y-%m-%d')
            cutoff_time = current_datetime - timedelta(days=days_old)
            count = 0

            # Walk through the download directory
            for root, dirs, files in os.walk(self.download_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    modified_time = os.path.getmtime(file_path)
                    file_datetime = datetime.fromtimestamp(modified_time)

                    # Remove if older than cutoff
                    if file_datetime < cutoff_time:
                        os.remove(file_path)
                        count += 1

            self.logger.info(
                f"Cleaned up {count} files older than {days_old} days")

        except Exception as e:
            self.logger.error(f"Error cleaning up old files: {e}")

    def list_available_forms(self) -> pd.DataFrame:
        """
        List available SEC form types with descriptions.

        Returns:
            DataFrame of available form types and descriptions
        """
        data = []
        for form_id, description in self.form_types.items():
            data.append({
                'form_id': form_id,
                'description': description
            })

        return pd.DataFrame(data)


# Example usage
if __name__ == "__main__":
    # Enable logging for example
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Initialize the tool with a temporary directory
    edgar_tool = SECEdgarTool(use_temp_dir=True)

    try:
        # Example 1: Fetch risk factors from latest 10-K using relative dates
        print("\nExample 1: Fetch risk factors from latest 10-K")
        risk_factors = edgar_tool.fetch_filings(
            "AAPL",
            "10-K",
            num_filings=1,
            before_date="today",
            after_date="-1y",
            extract_sections=["risk_factors"]
        )

        if not risk_factors.empty:
            print(f"Found {len(risk_factors)} filings")
            risk_text = risk_factors['risk_factors_content'].iloc[0]
            print(f"Risk factors excerpt: {risk_text[:200]}...")
            print(f"Word count: {risk_factors['word_count'].iloc[0]}")

        # Example 2: Compare risk factors over time
        print("\nExample 2: Compare risk factors over time")
        risk_comparison = edgar_tool.compare_filings_over_time("MSFT",
                                                               form_type="10-K",
                                                               section="risk_factors",
                                                               num_filings=2)
        if not risk_comparison.empty:
            print(f"Comparing {len(risk_comparison)} filings")
            print(risk_comparison[['filing_date',
                  'word_count', 'word_count_change']])

        # Example 3: Search for specific terms
        print("\nExample 3: Search for specific terms")
        search_results = edgar_tool.search_filings("GOOGL",
                                                   search_terms=[
                                                       "artificial intelligence", "AI"],
                                                   form_type="10-K",
                                                   num_filings=1)
        if not search_results.empty:
            print(f"Found {len(search_results)} matches")
            for i, result in search_results.head(2).iterrows():
                print(
                    f"Match in {result['section']} section: {result['context'][:100]}...")

    except Exception as e:
        print(f"Error in example: {e}")

    finally:
        # Clean up temporary files
        edgar_tool.clean_up(days_old=0)  # Clean up all files in temp dir
