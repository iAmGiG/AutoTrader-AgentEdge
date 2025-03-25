from sec_edgar_downloader import Downloader
from bs4 import BeautifulSoup
import os


class SECEdgarTool:
    def __init__(self, download_dir="sec_filings"):
        self.downloader = Downloader(download_dir)

    def fetch_filings(self, ticker, form_type="10-K", num_filings=1):
        self.downloader.get(form_type, ticker, amount=num_filings)
        file_path = os.path.join("sec_filings", ticker, form_type)
        return self.extract_risk_factors(file_path)

    def extract_risk_factors(self, file_path):
        risk_sections = []
        for filename in os.listdir(file_path):
            if filename.endswith(".txt"):  # SEC filings are text-heavy
                with open(os.path.join(file_path, filename), "r", encoding="utf-8") as f:
                    soup = BeautifulSoup(f.read(), "html.parser")
                    risk_sections.append(soup.get_text())
        return risk_sections


# Example Usage
edgar_tool = SECEdgarTool()
risks = edgar_tool.fetch_filings("AAPL", "10-K")
print(risks[0][:500])  # Show first 500 characters of the risk section
