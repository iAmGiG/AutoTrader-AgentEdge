#!/usr/bin/env python3
"""
A simplified test for just the sector detection and query understanding capabilities
of the enhanced Sentiment Agent.
"""

import os
import json
import re
from collections import Counter

# Load the sector data
def load_market_sectors():
    try:
        config_dir = os.path.dirname(os.path.abspath(__file__))
        sectors_file = os.path.join(config_dir, 'config', 'market_sectors.json')
        
        with open(sectors_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading market sectors: {e}")
        return {"sectors": {}}

# Extract query details using the same logic from the SentimentAgent
def extract_query_details(message, market_sectors):
    ticker = None
    topic = None
    start_date = None
    end_date = None
    sector = None
    
    # Extract ticker if present (uppercase 1-5 chars)
    words = message.split()
    for word in words:
        # Skip common acronyms that aren't tickers
        if word.isupper() and 1 <= len(word) <= 5 and word not in ["I", "A", "AI", "US"]:
            ticker = word
            break
    
    # Check if message contains keywords for specific sectors
    message_lower = message.lower()
    
    # First pass: Check for direct mentions of keywords with higher priority for certain sectors
    priority_matches = []
    
    for sector_name, sector_data in market_sectors.items():
        keywords = sector_data.get("keywords", [])
        
        # Check if any primary keyword from this sector appears in the message
        for keyword in keywords:
            if keyword in message_lower:
                # Calculate a match priority score
                # Longer matches are more specific and should have higher priority
                priority = len(keyword)
                
                # Exact sector names get higher priority
                if sector_name.replace("_", " ") == keyword:
                    priority += 10
                    
                # "Sector" mentions get higher priority
                if keyword.endswith(" sector") or keyword.endswith(" stocks"):
                    priority += 5
                
                # Holiday season and retail should have very high priority for retail sector
                if sector_name == "retail" and ("holiday season" in message_lower or "shopping" in message_lower):
                    priority += 15
                
                priority_matches.append((sector_name, priority, sector_data))
    
    # If we have matches, take the highest priority one
    if priority_matches:
        # Sort by priority (highest first)
        priority_matches.sort(key=lambda x: x[1], reverse=True)
        sector_name, _, sector_data = priority_matches[0]
        
        sector = sector_name
        topic = sector_name.replace("_", " ")
        
        # If no specific ticker found, use the sector's representative ticker
        if not ticker:
            ticker = sector_data.get("representative")
            
    # Second pass: If no direct match, try related topics with sector context
    if not sector:
        for sector_name, sector_data in market_sectors.items():
            related = sector_data.get("related_topics", [])
            
            # Check for related topics combined with sector context
            if any(topic in message_lower for topic in related):
                # Check if the sector itself is mentioned
                sector_terms = [sector_name.replace("_", " "), "sector", "stocks", "industry"]
                if any(term in message_lower for term in sector_terms):
                    sector = sector_name
                    topic = sector_name.replace("_", " ")
                    
                    # If no specific ticker found, use the sector's representative ticker
                    if not ticker:
                        ticker = sector_data.get("representative")
                    break
    
    # If no sector detected, try to extract topic from standard patterns
    if not topic:
        topic_indicators = ["about", "on", "for", "around", "sentiment on", "sentiment around"]
        for indicator in topic_indicators:
            if indicator in message_lower:
                parts = message_lower.split(indicator)
                if len(parts) > 1:
                    # Grab the part right after the indicator, clean it up
                    topic_candidate = parts[1].strip().split("?")[0].split(".")[0]
                    if not (ticker and ticker.lower() in topic_candidate):
                        topic = topic_candidate
                        break
    
    # Look for date-related keywords
    if "since" in message_lower:
        after_since = message_lower.split("since")[-1].strip()
        words = after_since.split()
        if words and (words[0].startswith("-") or words[0] in ["yesterday", "today", "ytd"]):
            start_date = words[0]
    
    if "last" in message_lower:
        after_last = message_lower.split("last")[-1].strip()
        words = after_last.split()
        if words:
            if "day" in after_last or "days" in after_last:
                try:
                    days = int(words[0])
                    start_date = f"-{days}d"
                except ValueError:
                    start_date = "-5d"  # Default to 5 days
            elif "week" in after_last or "weeks" in after_last:
                try:
                    weeks = int(words[0])
                    start_date = f"-{weeks}w"
                except ValueError:
                    start_date = "-1w"
            elif "month" in after_last or "months" in after_last:
                try:
                    months = int(words[0])
                    start_date = f"-{months}m"
                except ValueError:
                    start_date = "-1m"
    
    # For open-ended queries, extract topic using NLP techniques if needed
    if not topic and not ticker and len(message.split()) > 3:
        # Remove common stopwords and extract likely topic words
        stopwords = ['the', 'and', 'to', 'of', 'on', 'in', 'for', 'is', 'are', 'what', 'how', 
                    'a', 'an', 'this', 'that', 'with', 'by', 'as', 'be', 'it', 'from',
                    'might', 'affect', 'impact', 'recent', 'sentiment', 'market', 'understand',
                    'analyze', 'need', 'their', 'behavior', 'reaction', 'perceived', 'future',
                    'around', 'light', 'being', 'i', 'me', 'my', 'you', 'your']
        
        # Clean up the message and extract potential topic words
        clean_words = [word.lower() for word in re.findall(r'\b\w+\b', message_lower)
                      if word.lower() not in stopwords and len(word) > 3]
        
        # Use word frequency to identify potential topics
        word_counts = Counter(clean_words)
        common_words = [word for word, count in word_counts.most_common(3)]
        
        if common_words:
            topic = " ".join(common_words)
            
            # Try to map extracted topic to a sector if possible
            for sector_name, sector_data in market_sectors.items():
                if any(word in sector_data.get("keywords", []) for word in common_words):
                    sector = sector_name
                    ticker = sector_data.get("representative")
                    break
    
    # If no date provided, default to 5 days
    if not start_date:
        start_date = "-5d"
    
    # If we still have no ticker but have a topic, try to find a relevant ticker
    if not ticker and topic:
        # Default to SPY for general market topics
        ticker = "SPY"
        
        # Check if our topic might match any sector
        topic_words = topic.lower().split()
        for sector_name, sector_data in market_sectors.items():
            if any(keyword in topic_words for keyword in sector_data.get("keywords", [])):
                ticker = sector_data.get("representative")
                break
    
    return {
        "ticker": ticker,
        "topic": topic,
        "sector": sector,
        "start_date": start_date,
        "end_date": end_date
    }

# Run query extraction tests on various kinds of queries
def run_tests():
    # Load sector data
    market_sectors = load_market_sectors().get("sectors", {})
    
    # Test cases
    test_queries = [
        "What's the market sentiment on chip tariffs and how might they impact semiconductor stocks?",
        "I need to understand the recent investor sentiment around AI companies and their market behavior",
        "How are bank stocks being perceived in light of recent Federal Reserve announcements?",
        "Analyze the energy sector's reaction to recent geopolitical tensions",
        "What's the sentiment on tech layoffs and how might this affect future market behavior?",
        "How have gold prices performed over the last 30 days?",
        "Tell me about healthcare stocks since the beginning of the year",
        "What's the impact of rising interest rates on the utilities sector?",
        "Get stock data for AAPL for the last 7 days",
        "Fetch news about retail during the holiday season",
        "Compare real estate performance to the broader market"
    ]
    
    print("\n*** TESTING QUERY UNDERSTANDING ***\n")
    
    for i, query in enumerate(test_queries):
        print(f"\nTEST CASE {i+1}: '{query}'")
        print("-" * 70)
        
        results = extract_query_details(query, market_sectors)
        
        print(f"Ticker: {results['ticker']}")
        print(f"Topic: {results['topic']}")
        print(f"Sector: {results['sector']}")
        print(f"Date Range: {results['start_date']} to {results['end_date'] or 'present'}")
        
        # If we identified a sector, show the relevant ETFs
        if results['sector'] and results['sector'] in market_sectors:
            sector_data = market_sectors[results['sector']]
            print(f"\nSector Information:")
            print(f"  Representative: {sector_data.get('representative')}")
            print(f"  ETFs: {', '.join(sector_data.get('etfs', [])[:3])}")
            if sector_data.get('leveraged_etfs'):
                print(f"  Leveraged ETFs: {', '.join(sector_data.get('leveraged_etfs', [])[:2])}")
            print(f"  Blue Chips: {', '.join(sector_data.get('blue_chips', [])[:5])}")

if __name__ == "__main__":
    run_tests()