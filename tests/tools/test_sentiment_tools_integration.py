"""
Test that hybrid historical news tool is properly integrated into sentiment agent tools
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

def test_tools_import():
    """Test that tools import correctly"""
    print("=== Testing Tools Import ===\n")
    
    try:
        from src.tools.tools import SENTIMENT_TOOLS, hybrid_historical_news_tool
        print("✅ Successfully imported SENTIMENT_TOOLS and hybrid_historical_news_tool")
        
        print(f"📊 Found {len(SENTIMENT_TOOLS)} sentiment tools:")
        for i, tool in enumerate(SENTIMENT_TOOLS):
            print(f"  {i+1}. {tool.name} - {tool.description[:80]}...")
        
        # Check if hybrid tool is in the list
        hybrid_in_tools = any(tool.name == "fetch_hybrid_historical_news" for tool in SENTIMENT_TOOLS)
        print(f"\n🎯 Hybrid historical news tool in SENTIMENT_TOOLS: {hybrid_in_tools}")
        
        if hybrid_in_tools:
            print("✅ Integration successful!")
        else:
            print("❌ Integration failed - tool not found in SENTIMENT_TOOLS")
            
        return hybrid_in_tools
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_tool_functionality():
    """Test that the tool functions correctly when called"""
    print("\n\n=== Testing Tool Functionality ===\n")
    
    try:
        from src.tools.tools import hybrid_historical_news_tool
        from datetime import datetime
        
        # Test with current date
        current_date = datetime.now().strftime('%Y-%m-%d')
        print(f"🔍 Testing with current date: {current_date}")
        
        # Import and call the function directly
        from src.tools.data_sources.news.hybrid_historical_news_tool import fetch_hybrid_historical_news
        
        result = fetch_hybrid_historical_news(
            target_date=current_date,
            keywords=['AAPL', 'market'],
            max_articles=5
        )
        
        if not result.empty:
            print(f"✅ Tool returned {len(result)} articles")
            print(f"📊 Columns: {list(result.columns)}")
            
            # Check data sources
            if 'Data_Source' in result.columns:
                sources = result['Data_Source'].value_counts()
                print(f"📈 Data sources:")
                for source, count in sources.items():
                    print(f"  - {source}: {count} articles")
            
            # Show sample headlines
            print(f"\n📰 Sample headlines:")
            for i, row in result.head(3).iterrows():
                title = row['title'][:60] + "..." if len(row['title']) > 60 else row['title']
                source = row.get('Data_Source', 'Unknown')
                print(f"  {i+1}. [{source}] {title}")
                
            return True
        else:
            print("⚠️  Tool returned empty DataFrame")
            return False
            
    except Exception as e:
        print(f"❌ Tool functionality test failed: {e}")
        return False


def test_sentiment_agent_access():
    """Test that sentiment agent can access the tool"""
    print("\n\n=== Testing Sentiment Agent Access ===\n")
    
    try:
        from src.agents.sentiment_v1 import SentimentV1Agent
        
        # Create a sentiment agent (this will load the tools)
        print("🤖 Creating SentimentV1Agent (has sentiment tools)...")
        agent = SentimentV1Agent()
        
        # Check different ways the agent might store tools
        agent_tools = getattr(agent, 'tools', [])
        tools_dict = getattr(agent, '_tools_dict', {})
        
        print(f"📊 Agent tools attribute has {len(agent_tools)} tools")
        print(f"📊 Agent _tools_dict has {len(tools_dict)} tools")
        
        # Look for our hybrid tool in different places
        hybrid_tool_found = False
        
        # Check in tools list
        for tool in agent_tools:
            tool_name = getattr(tool, 'name', 'unknown')
            if tool_name == "fetch_hybrid_historical_news":
                hybrid_tool_found = True
                print(f"✅ Found hybrid tool in tools list: {tool_name}")
                break
        
        # Check in tools dict
        if not hybrid_tool_found and "fetch_hybrid_historical_news" in tools_dict:
            hybrid_tool_found = True
            print(f"✅ Found hybrid tool in tools dict")
        
        if not hybrid_tool_found:
            print("⚠️  Hybrid tool not found in agent tools")
            # List all tool names for debugging
            print("🔍 Available tools in tools list:")
            for tool in agent_tools:
                tool_name = getattr(tool, 'name', 'unknown')
                print(f"  - {tool_name}")
            
            print("🔍 Available tools in tools dict:")
            for tool_name in tools_dict.keys():
                print(f"  - {tool_name}")
        
        return hybrid_tool_found
        
    except Exception as e:
        print(f"❌ Sentiment agent access test failed: {e}")
        return False


def final_assessment(import_success, functionality_success, agent_access_success):
    """Provide final assessment"""
    print("\n\n=== FINAL ASSESSMENT ===\n")
    
    passed_tests = sum([import_success, functionality_success, agent_access_success])
    
    print(f"🎯 Integration Status:")
    print(f"  Import Test: {'✅ PASS' if import_success else '❌ FAIL'}")
    print(f"  Functionality Test: {'✅ PASS' if functionality_success else '❌ FAIL'}")  
    print(f"  Agent Access Test: {'✅ PASS' if agent_access_success else '❌ FAIL'}")
    
    print(f"\n📊 Overall Score: {passed_tests}/3 tests passed")
    
    if passed_tests == 3:
        print("🎉 COMPLETE SUCCESS!")
        print("✅ Hybrid historical news tool fully integrated with sentiment agent")
        print("✅ FinViz news data now available for sentiment analysis")
        print("✅ Ready to proceed with Issue #150 (aggressive prompts)")
    elif passed_tests >= 2:
        print("✅ MOSTLY SUCCESS!")
        print("🔧 Minor issues to resolve, but core integration working")
    else:
        print("❌ INTEGRATION ISSUES")
        print("🔧 Need to debug import or functionality problems")
    
    return passed_tests == 3


if __name__ == "__main__":
    print("Testing Sentiment Tools Integration")
    print("=" * 50)
    
    # Run tests
    import_success = test_tools_import()
    functionality_success = test_tool_functionality()
    agent_access_success = test_sentiment_agent_access()
    
    # Final assessment
    complete_success = final_assessment(import_success, functionality_success, agent_access_success)
    
    print("\n" + "=" * 50)
    if complete_success:
        print("🚀 Ready to implement aggressive trading prompts!")
    else:
        print("🔧 Need to fix integration issues first")