# Conditional import for sentiment analyzer (requires nltk which may not be available)
try:
    from .sentiment_analyzer import SentimentAnalyzer
except ImportError:
    # SentimentAnalyzer not available - likely due to missing nltk
    # This is fine for voting strategies that don't use sentiment
    SentimentAnalyzer = None

# indicator_library moved to core/indicators/
