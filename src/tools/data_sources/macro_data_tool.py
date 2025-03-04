from fredapi import Fred


class MacroDataTool:
    def __init__(self, api_key):
        self.fred = Fred(api_key=api_key)

    def get_gdp(self):
        return self.fred.get_series("GDP")


# Example Usage
macro_tool = MacroDataTool("YOUR_FRED_API_KEY")
gdp_data = macro_tool.get_gdp()
print(gdp_data.head())
