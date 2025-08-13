# Scripts Directory

The scripts directory contains V0-V4 sentiment analysis validation and comparison runs.

## Directory Structure

```bash
scripts/
├── README.md
└── runs/                    # V0-V4 sentiment framework runs
    ├── validation/          # Pipeline validation scripts
    ├── sentiment/           # Individual V1-V4 sentiment runs  
    └── comparison/          # Cross-version comparison runs
```

## V0-V4 Validation Runs (`runs/validation/`)

**Pipeline validation scripts for each sentiment version:**

### `run_v0_pipeline_validation.py` - V0 Baseline Validation

```bash
python runs/validation/run_v0_pipeline_validation.py
```

Validates complete V0 pipeline (TechAgent + V0SentimentAgent + StrategyAgent orchestration).
Essential foundation test before implementing V1-V4.

### `run_v4_data_leakage_detection.py` - V4 Data Leakage Testing

```bash
python runs/validation/run_v4_data_leakage_detection.py
```

Critical obfuscation testing to detect if V4 LLM is using memorized training data.
Must pass before trusting V4 backtest results.

## V1-V4 Sentiment Runs (`runs/sentiment/`)

**Individual sentiment version validation (to be created):**

```bash
python runs/sentiment/run_v1_nlp_sentiment.py       # V1: NLP + News analysis
python runs/sentiment/run_v2_market_fear.py         # V2: VIX/VXX volatility  
python runs/sentiment/run_v3_heuristic_combo.py     # V3: V1 + V2 combination
python runs/sentiment/run_v4_llm_reasoning.py       # V4: GPT-4o-mini analysis
```

## Cross-Version Comparison (`runs/comparison/`)

**Compare sentiment versions on identical data (to be created):**

```bash
python runs/comparison/run_v0_v4_quarterly_comparison.py    # Full V0-V4 comparison
python runs/comparison/run_statistical_significance.py     # Validate differences
python runs/comparison/run_incremental_value_analysis.py   # V0→V1→V2→V3→V4 progression
```

## V0-V4 Testing Workflow

### 1. **Validate V0 Foundation**

```bash
python runs/validation/run_v0_pipeline_validation.py
```

✅ **Status**: Passing (4/4 validation checks)

### 2. **Implement and Test V1-V4** (Next Phase)

```bash
# As each version is implemented:
python runs/sentiment/run_v1_nlp_sentiment.py
python runs/sentiment/run_v2_market_fear.py  
python runs/sentiment/run_v3_heuristic_combo.py
python runs/sentiment/run_v4_llm_reasoning.py
```

### 3. **Validate V4 Data Integrity**

```bash
python runs/validation/run_v4_data_leakage_detection.py
```

🔍 **Critical**: Must pass before trusting V4 results

### 4. **Cross-Version Analysis**

```bash
python runs/comparison/run_v0_v4_quarterly_comparison.py
python runs/comparison/run_statistical_significance.py
```

## V0-V4 Research Framework

**Objective**: Demonstrate incremental value of LLM introduction through 5 sentiment approaches:

- **V0**: Fixed Baseline (sentiment = 1.0) - Pure MACD strategy
- **V1**: NLP Analysis (VADER + Google Search news)  
- **V2**: Market Fear (VXX/VIX volatility-based sentiment)
- **V3**: Heuristic Combination (V1 + V2 with adaptive weighting)
- **V4**: LLM Analysis (GPT-4o-mini reasoning for sentiment decisions)

**Key Principle**: Only V4 uses LLM for decision-making; V0-V3 are purely mechanical.

## Testing Strategy

1. **Pipeline Validation**: Each version gets comprehensive validation
2. **Incremental Analysis**: V0→V1→V2→V3→V4 progression measurement
3. **Statistical Significance**: Validate that improvements are statistically meaningful
4. **Data Leakage Detection**: Ensure V4 results are genuine analysis, not memorized data

**Current Status**: ✅ V0 foundation validated, ready for V1-V4 implementation
