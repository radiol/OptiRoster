# OptiRoster User Guide

A comprehensive guide for configuring and using the OptiRoster system to automatically create optimal hospital duty schedules.

## Quick Start

### Prerequisites

- Python 3.11+ installed
- `uv` package manager (`pip install uv` or `brew install uv`)

### Installation

```bash
# Clone and setup
git clone <repository-url>
cd OptiRoster
uv sync
```

### Basic Usage

```bash
uv run -m src.cli.main \
  --year 2025 --month 10 \
  --specified-days data/specified-2025-10.toml \
  --preferences data/2025-10.csv \
  --xlsx output/schedule-2025-10.xlsx
```

## Configuration Files

### 1. Hospital Configuration (`config/hospitals.toml`)

Defines hospital properties and staffing requirements:

```toml
[[hospitals]]
name = "Central Hospital"
is_remote = false
is_university = false

[[hospitals.demand_rules]]
shift_type = "当直"
weekdays = ["金曜", "土曜"]
frequency = "毎週"

[[hospitals]]
name = "Remote Clinic"
is_remote = true
is_university = false

[[hospitals.demand_rules]]
shift_type = "日勤"
weekdays = ["月曜", "水曜", "金曜"]
frequency = "毎週"
```

**Hospital Properties:**

- `name`: Unique hospital identifier
- `is_remote`: `true` for remote locations (affects post-night duty rules)
- `is_university`: `true` for university hospitals (specialist requirements)

**Demand Rules:**

- `shift_type`: `"日勤"` (day), `"当直"` (night), `"AM"`, `"PM"`
- `weekdays`: `["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]`
- `frequency`: `"毎週"` (weekly), `"隔週"` (biweekly), `"指定日"` (specific days)

### 2. Worker Configuration (`config/workers.toml`)

Defines worker capabilities and availability:

```toml
[[workers]]
name = "Dr. Smith"
is_diagnostic_specialist = true

[[workers.assignments]]
hospital = "Central Hospital"
weekdays = ["月曜", "金曜"]
shift_type = "当直"

[[workers.assignments]]
hospital = "Central Hospital"
weekdays = ["火曜", "水曜", "木曜"]
shift_type = "日勤"

[[workers]]
name = "Dr. Johnson"
is_diagnostic_specialist = false

[[workers.assignments]]
hospital = "Remote Clinic"
weekdays = ["月曜", "水曜", "金曜"]
shift_type = "日勤"
```

**Worker Properties:**

- `name`: Unique worker identifier
- `is_diagnostic_specialist`: Required for university hospital holiday night duties

**Assignment Rules:**

- `hospital`: Hospital where worker can be assigned
- `weekdays`: Days of week worker is available
- `shift_type`: Type of shift worker can handle

### 3. Specified Days (`data/specified-YYYY-MM.toml`)

Override specific dates with special requirements:

```toml
# Public holidays and special dates
[[specified_days]]
hospital = "University Hospital"
date = 2025-10-10  # Public holiday
shift_type = "当直"
```

### 4. Preferences (`data/YYYY-MM.csv`)

Worker preferences for specific dates:

```csv
name,date,shift_type,preference
Dr. Smith,2025-10-01,当直,可
Dr. Smith,2025-10-02,日勤,不可
Dr. Johnson,2025-10-15,日勤,希望
Dr. Johnson,2025-10-20,当直,不可
```

**Preference Values:**

- `希望` (preferred): Soft preference for assignment
- `可` (available): Neutral availability
- `不可` (unavailable): Hard constraint against assignment

### 5. Maximum Assignments (`data/max-assignments.csv`)

Limit assignments per worker per hospital:

```csv
worker,hospital,max_assignments
Dr. Smith,Central Hospital,8
Dr. Smith,University Hospital,4
Dr. Johnson,Remote Clinic,10
```

## Command Line Interface

### Required Arguments

- `--year YYYY`: Target year for schedule generation
- `--month MM`: Target month (1-12)
- `--specified-days PATH`: Path to specified days TOML file
- `--preferences PATH`: Path to preferences CSV file

### Optional Arguments

- `--hospitals PATH`: Hospital config (default: `config/hospitals.toml`)
- `--workers PATH`: Worker config (default: `config/workers.toml`)
- `--max-assignments-csv PATH`: Max assignments (default: `data/max-assignments.csv`)
- `--xlsx PATH`: Excel output file path
- `--json`: Output results as JSON instead of formatted text

### Examples

**Basic monthly schedule:**

```bash
uv run -m src.cli.main \
  --year 2025 --month 10 \
  --specified-days data/specified-2025-10.toml \
  --preferences data/2025-10.csv
```

**With Excel output:**

```bash
uv run -m src.cli.main \
  --year 2025 --month 10 \
  --specified-days data/specified-2025-10.toml \
  --preferences data/2025-10.csv \
  --xlsx schedules/october-2025.xlsx
```

**JSON output for integration:**

```bash
uv run -m src.cli.main \
  --year 2025 --month 10 \
  --specified-days data/specified-2025-10.toml \
  --preferences data/2025-10.csv \
  --json > results.json
```

## Understanding Output

### Console Output

The system provides rich formatted output showing:

1. **Solve Summary:**
   - Status: Optimal, Infeasible, or other solver states
   - Objective value: Total assignments + penalty adjustments
   - Solve time: Optimization duration

2. **Penalty Report:**
   - Summary table with total penalties grouped by constraint type
   - Individual penalty item breakdown with metadata
   - Helps identify scheduling conflicts and constraint violations
   - Shows human-readable constraint descriptions for easier understanding

3. **Assignment Schedule:**
   - Date-sorted assignment list
   - Format: Date | Hospital | Worker | Shift

### Penalty Report Interpretation

The penalty report provides detailed insights into constraint violations and optimization trade-offs:

#### Summary Section

```
                              Penalty Summary                               
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Constraint                              ┃ Total                         ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ 夜勤間隔を空けたい                      ┃ 15.450                        ┃
┃ 勤務希望.CSVの内容を遵守                ┃ 8.000                         ┃
┃ 平日の非夜勤のバランス                  ┃ 3.200                         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

- **Total Penalty**: Sum of all constraint violations weighted by importance
- **By Constraint**: Breakdown showing which constraints contribute most to penalties
- **Human-readable descriptions**: Japanese summaries explain what each constraint does

#### Detail Section

```
                                  Penalty Items (Top 30)                                   
┏━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┓
┃ # ┃ Constraint                 ┃ Var                           ┃ Val ┃ Weight ┃ Penalty┃ Meta    ┃
┣━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━╋━━━━━━━━╋━━━━━━━━╋━━━━━━━━━┫
┃ 1 ┃ 夜勤間隔を空けたい         ┃ night_spacing_violation_Dr... ┃ 2.0 ┃ 5.0    ┃ 10.0   ┃ w=Dr... ┃
┃ 2 ┃ 勤務希望.CSVの内容を遵守   ┃ preference_violation_2025...  ┃ 1.0 ┃ 8.0    ┃ 8.0    ┃ d=10/15 ┃
┗━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━┻━━━━━━━━┻━━━━━━━━┻━━━━━━━━━┛
```

- **#**: Ranking by penalty severity
- **Constraint**: Human-readable constraint description
- **Var**: Optimization variable name (technical identifier)
- **Val**: Variable value (amount of violation)
- **Weight**: Penalty weight applied to this violation
- **Penalty**: Final penalty score (Val × Weight)
- **Meta**: Additional context (worker names, dates, etc.)

#### Using Penalty Reports for Optimization

1. **High Total Penalty**: Consider adjusting constraints or input data
2. **Constraint Imbalance**: If one constraint dominates, review its importance
3. **Repeated Violations**: Workers or dates appearing frequently may need attention
4. **Zero Penalties**: Indicates optimal solution with no constraint violations

### Excel Output

When `--xlsx` is specified, generates a formatted Excel file with:

- Calendar view of assignments
- Hospital-based worksheets
- Summary statistics
- Constraint violation reports

## Optimization Process

### Hard Constraints (Must be satisfied)

1. **One person per hospital per day**: Each required hospital-date gets exactly one assignment
2. **No overlapping assignments**: Workers cannot be in multiple places simultaneously
3. **Respect preferences**: Honor "不可" (unavailable) preferences absolutely
4. **Maximum assignments**: Enforce per-worker per-hospital limits
5. **Night spacing**: Minimum gap between night duties
6. **Post-night restrictions**: No remote assignments after night duty
7. **Specialist requirements**: University holiday nights require specialists

### Soft Constraints (Optimization objectives)

1. **Night spacing optimization**: Maximize gaps between night duties
2. **Workload balancing**: Distribute assignments evenly
3. **Day-of-week balancing**: Even distribution across weekdays
4. **Preference optimization**: Favor "希望" (preferred) assignments

## Troubleshooting

### Common Issues

**Infeasible Solution:**

- Insufficient worker availability for required coverage
- Conflicting hard constraints
- Check preferences for excessive "不可" markings
- Verify worker assignment rules cover required hospitals/shifts

**Suboptimal Results:**

- Review soft constraint weights in source code
- Adjust worker availability windows
- Balance specialist vs. general worker ratios

**Performance Issues:**

- Large worker/hospital combinations increase complexity
- Consider monthly vs. quarterly optimization periods
- Review constraint complexity in implementation

### Debugging Steps

1. **Validate input files:**

   ```bash
   # Check TOML syntax
   python -c "import tomllib; print(tomllib.load(open('config/hospitals.toml', 'rb')))"

   # Check CSV format
   head -5 data/preferences.csv
   ```

2. **Test with minimal data:**
   - Start with 2-3 workers and 2-3 hospitals
   - Gradually add complexity

3. **Review constraint violations:**
   - Check penalty report for high penalty sources
   - Examine individual constraint logic

## Advanced Usage

### Custom Constraints

Add new constraints by creating files in `src/constraints/`:

```python
# src/constraints/c08_custom_rule.py
from .base import register
from .base_impl import ConstraintBase

class CustomRule(ConstraintBase):
    name = "custom_rule"
    requires: ClassVar[set[str]] = {"workers", "hospitals"}

    def apply(self, model, x, ctx):
        # Add your constraint logic here
        pass

register(CustomRule())
```

### Batch Processing

Process multiple months:

```bash
for month in {1..12}; do
  uv run -m src.cli.main \
    --year 2025 --month $month \
    --specified-days data/specified-2025-$(printf "%02d" $month).toml \
    --preferences data/2025-$(printf "%02d" $month).csv \
    --xlsx output/schedule-2025-$(printf "%02d" $month).xlsx
done
```

### Integration

**JSON Output Processing:**

```python
import json
import subprocess

result = subprocess.run([
    "uv", "run", "-m", "src.cli.main",
    "--year", "2025", "--month", "10",
    "--specified-days", "data/specified-2025-10.toml",
    "--preferences", "data/2025-10.csv",
    "--json"
], capture_output=True, text=True)

schedule = json.loads(result.stdout)
# Process schedule data...
```

## Best Practices

### Data Management

- Use version control for configuration files
- Maintain monthly data file naming conventions
- Backup generated schedules with timestamps

### Configuration

- Start with conservative constraint parameters
- Test new configurations with limited data sets
- Document custom constraint modifications

### Quality Assurance

- Run tests before deploying schedule changes
- Validate generated schedules manually for critical periods
- Monitor penalty reports for unexpected constraint violations

### Performance

- Optimize for monthly rather than longer periods
- Consider worker/hospital count impact on solve time
- Use JSON output for automated processing workflows
