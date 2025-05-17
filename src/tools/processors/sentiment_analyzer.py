"""Sentiment analysis utility for financial and news text"""
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import pandas as pd


class SentimentAnalyzer:
    """
    A utility class for analyzing sentiment in text data, 
    optimized for financial news and market-related content.
    """

    def __init__(self):
        """Initialize the sentiment analyzer with VADER lexicon."""
        try:
            # Download required NLTK resources if not already present
            nltk.download('vader_lexicon', quiet=True)
            self.analyzer = SentimentIntensityAnalyzer()

            # Customize VADER lexicon for financial terms
            self._add_financial_lexicon()

        except Exception as e:
            print(f"Error initializing sentiment analyzer: {e}")
            self.analyzer = None

    def _add_financial_lexicon(self):
        """Add financial domain-specific terms to the VADER lexicon including Austrian economics concepts."""
        if self.analyzer:
            # Positive financial terms
            self.analyzer.lexicon.update({
                # Standard financial terms
                'bull': 3.0,
                'bullish': 3.0,
                'outperform': 2.5,
                'upgrade': 2.0,
                'growth': 1.5,
                'profit': 2.0,
                'upside': 2.0,
                'rally': 2.0,
                'gain': 1.5,
                'beat': 1.5,
                'exceed': 1.5,
                'dividend': 1.0,

                # Austrian economics positive terms
                'free market': 2.5,
                'deregulation': 2.0,
                'sound money': 3.0,
                'gold standard': 2.0,
                'free banking': 2.0,
                'capital accumulation': 2.0,
                'entrepreneurship': 2.5,
                'voluntary exchange': 2.0,
                'price discovery': 1.5,
                'economic calculation': 1.5,
                'savings': 2.0,
                'hard money': 2.0,
                'private property': 2.0,
                'decentralization': 1.5,
                'liquidation': 1.0,  # In Austrian terms, liquidation of malinvestment is positive
                'deflation': 1.0,    # Price deflation from productivity is positive in Austrian view
                'austerity': 1.0,    # Often viewed positively in Austrian economics
            })

            # Negative financial terms
            self.analyzer.lexicon.update({
                # Standard financial terms
                'bear': -3.0,
                'bearish': -3.0,
                'underperform': -2.5,
                'downgrade': -2.0,
                'decline': -1.5,
                'loss': -2.0,
                'downside': -2.0,
                'selloff': -2.0,
                'drop': -1.5,
                'miss': -1.5,
                'below': -1.0,
                'debt': -1.0,

                # Austrian economics negative terms
                'central planning': -3.0,
                'monetary expansion': -2.5,
                'quantitative easing': -2.5,
                'fiat currency': -2.0,
                'federal reserve': -1.5,
                'money printing': -3.0,
                'malinvestment': -2.5,
                'government spending': -2.0,
                'stimulus': -1.5,
                'bailout': -2.5,
                'subsidy': -2.0,
                'intervention': -2.0,
                'regulation': -2.0,
                'price control': -2.5,
                'central bank': -2.0,
                'fractional reserve': -1.5,
                'inflation': -2.5,
                'credit expansion': -2.0,
                'business cycle': -1.0,  # Often discussed negatively in Austrian context
                'fiscal policy': -1.0,
                'keynes': -1.5,
                'keynesian': -1.5,
            })

    def analyze_text(self, text):
        """
        Analyze the sentiment of a given text.

        :param text: The text to analyze
        :return: A float between -1.0 (very negative) and 1.0 (very positive)
        """
        if not self.analyzer or not text:
            return 0.0

        sentiment_dict = self.analyzer.polarity_scores(text)
        return sentiment_dict['compound']

    def analyze_dataframe(self, df, text_column, output_column='sentiment_score'):
        """
        Analyze sentiment for a text column in a DataFrame.

        :param df: pandas DataFrame containing the text data
        :param text_column: name of the column containing text to analyze
        :param output_column: name of the column to store sentiment scores
        :return: DataFrame with added sentiment score column
        """
        if self.analyzer is None:
            df[output_column] = 0.0
            return df

        # Create a copy to avoid modifying the original
        result_df = df.copy()

        # Apply sentiment analysis to each row in the text column
        result_df[output_column] = result_df[text_column].apply(
            lambda x: self.analyze_text(x) if pd.notna(x) else 0.0
        )

        return result_df


if __name__ == "__main__":
    # Example usage
    analyzer = SentimentAnalyzer()

    # Test with individual texts
    texts = [
        "The company reported strong earnings, beating market expectations.",
        "The stock plummeted after the earnings miss and revised guidance.",
        "Analysts maintain a neutral outlook on the sector.",
        "The market rallied despite ongoing economic concerns."
    ]

    for text in texts:
        score = analyzer.analyze_text(text)
        print(f"Text: \"{text}\"\nSentiment Score: {score:.2f}\n")

    # Test with a DataFrame
    data = {
        'headline': [
            "Tech company exceeds Q4 revenue targets",
            "Bank announces job cuts amid restructuring",
            "Oil prices remain stable as production holds steady"
        ]
    }

    df = pd.DataFrame(data)
    result = analyzer.analyze_dataframe(df, 'headline')
    print("DataFrame with sentiment scores:")
    print(result)
