from .data_normalizer import normalize_data_for_sentiment, normalize_alpha_vantage_data, normalize_finnhub_data, normalize_market_data_for_sentiment, normalize_newsapi_data, normalize_yahoo_finance_data, NEWS_SCHEMA

# Conditional import for sentiment analyzer (requires nltk which may not be available)
try:
    from .sentiment_analyzer import SentimentAnalyzer
except ImportError as e:
    # SentimentAnalyzer not available - likely due to missing nltk
    # This is fine for voting strategies that don't use sentiment
    SentimentAnalyzer = None
    
# indicator_library moved to core/indicators/
