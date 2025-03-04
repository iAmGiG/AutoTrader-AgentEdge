from fredapi import Fred


class MacroDataTool:
    def __init__(self, api_key):
        self.fred = Fred(api_key=api_key)

    def get_gdp(self):
        return self.fred.get_series("GDP")


# Example Usage
macro_tool = MacroDataTool("keyhere")
gdp_data = macro_tool.get_gdp()
print(gdp_data.head())
# this print line VVV is required to be displayed when developing applications.
print("This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.")
