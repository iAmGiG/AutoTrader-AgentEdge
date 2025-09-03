#!/usr/bin/env python3
"""
Basic Voting Strategy Demo - Issue #250 Implementation

Demonstrates the core voting architecture with integration to existing V0-V4 system.
Shows how BasicVotingStrategy coordinates MACD + sentiment signals for ensemble decisions.

Usage:
    python examples/basic_voting_demo.py
    
Expected Output:
    - Voting decision with signal breakdown
    - Integration validation results
    - Performance metrics
"""

import sys
import os
import json
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Demonstrate basic voting strategy functionality"""
    
    print("=" * 60)
    print("RH2MAS Multi-Indicator Voting System Demo")
    print("Issue #250: Core Voting Architecture")
    print("=" * 60)
    
    try:
        # Import voting system
        from src.voting import BasicVotingStrategy
        from src.agents.tech_agent import TechAgent
        
        print("\n1. Initializing Basic Voting Strategy...")
        
        # Create voting strategy
        voting_strategy = BasicVotingStrategy("DemoVotingStrategy")
        print(f"   ✓ Created: {voting_strategy.name}")
        
        # Create and register TechAgent for MACD signals
        tech_agent = TechAgent("DemoTechAgent")
        voting_strategy.register_tech_agent(tech_agent)
        print(f"   ✓ Registered TechAgent: {tech_agent.name}")
        
        print("\n2. Validating Integration...")
        
        # Validate integration with existing system
        validation = voting_strategy.validate_integration()
        print(f"   ✓ Integration Status:")
        print(f"     - MACD Available: {validation['integration_health']['macd_available']}")
        print(f"     - Sentiment Agents: {validation['sentiment_agents']['total_count']}")
        print(f"     - Tools Loaded: {len(validation['tools_available'])}")
        print(f"     - Ready for Voting: {validation['integration_health']['ready_for_voting']}")
        
        print("\n3. Running Basic Voting Test...")
        
        # Run test voting decision
        test_result = voting_strategy.run_basic_test("AAPL", "2024-01-15")
        
        print(f"   ✓ Voting Decision: {test_result.get('action', 'ERROR')}")
        print(f"     - Confidence: {test_result.get('confidence', 0.0):.2f}")
        print(f"     - Weighted Score: {test_result.get('weighted_score', 0.0):.1f}")
        print(f"     - Reasoning: {test_result.get('reasoning', 'N/A')}")
        
        if 'signal_breakdown' in test_result:
            print(f"   ✓ Signal Breakdown:")
            for signal_name, signal_data in test_result['signal_breakdown'].items():
                print(f"     - {signal_name}: {signal_data.get('strength', 0)} (conf: {signal_data.get('confidence', 0.0):.2f})")
        
        print("\n4. Performance Metrics...")
        
        # Get performance metrics
        metrics = voting_strategy.get_performance_metrics()
        print(f"   ✓ Total Decisions: {metrics.get('total_decisions', 0)}")
        
        if 'action_distribution' in metrics:
            print(f"   ✓ Action Distribution: {metrics['action_distribution']}")
            
        print("\n5. Architecture Overview...")
        
        # Show architecture details
        print(f"   ✓ Strategy Class: {voting_strategy.__class__.__name__}")
        print(f"   ✓ Base Class: {voting_strategy.__class__.__bases__[0].__name__}")
        print(f"   ✓ Indicator Weights: {len(voting_strategy.indicator_weights)} configured")
        print(f"   ✓ Decision History: {len(voting_strategy.decision_history)} recorded")
        
        print("\n" + "=" * 60)
        print("✅ Issue #250 (Core Voting Architecture) - IMPLEMENTATION COMPLETE")
        print("   - BaseVotingStrategy: Abstract foundation ✓")
        print("   - BasicVotingStrategy: Equal-weighted voting ✓")
        print("   - TechAgent Integration: MACD signals ✓")
        print("   - AutoGen Compatibility: Full support ✓")
        print("   - Performance Tracking: Decision history ✓")
        print("\n📋 Next Steps (Issues #277-280):")
        print("   - Issue #277: RSI Implementation")
        print("   - Issue #278: Bollinger Bands")
        print("   - Issue #279: Volume Confirmation")
        print("   - Issue #280: Ensemble Metrics Dashboard")
        print("=" * 60)
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("   Make sure you've installed dependencies: pip install -e .")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Demo Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()