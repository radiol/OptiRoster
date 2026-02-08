# OptiRoster - AI Coding Agent Instructions

## Project Overview

**OptiRoster** is a constraint optimization system for hospital duty scheduling using PuLP (Python Linear Programming). It generates monthly duty rosters by satisfying hard constraints while minimizing soft constraint penalties.

**Core Tech Stack:** Python 3.13+, PuLP (MIP solver), PySide6 (GUI), pandas/openpyxl (I/O), pytest

## Architecture: Pipeline with Plugin Constraints

The system follows a **5-phase pipeline** architecture:

1. **Input Loading** (`src/io/`) - Parse TOML/CSV configs into domain objects
2. **Variable Generation** (`src/model/variable_builder.py`) - Three-stage filtering to create sparse decision variables
3. **Constraint Application** (`src/constraints/`) - Plugin-based constraint system with auto-discovery
4. **Optimization** (`src/optimizer/`) - Two-stage objective (shortage minimization → penalty minimization)
5. **Output Generation** (`src/io/export_excel.py`) - Excel roster with highlighting

### Key Design Patterns

**Variable Builder: Three-Stage Filtering**
```python
# Cartesian product space: H × W × D × S (hospitals × workers × days × shifts)
vb = VariableBuilder(hospitals, workers, days)
vb.init_all_zero()                              # Stage 1: All UB=0 (unavailable)
vb.elevate_by_workers(workers)                  # Stage 2: Worker rules → UB=1
vb.restrict_by_hospitals(hospitals, specified_days)  # Stage 3: Hospital demands → UB=0 for unneeded
vb.filter_by_max_assignments(max_assignments)   # Filter out max=0 assignments
x = vb.materialize()  # Create PuLP variables only for UB=1 combinations
```
Only combinations with `UB=1` become PuLP decision variables. This drastically reduces problem size.

**Plugin Constraint System** (`src/constraints/`)
All constraints inherit `ConstraintBase` and are auto-discovered:
```python
class MyConstraint(ConstraintBase):
    name = "my_constraint"
    summary = "Human-readable description"
    requires: ClassVar[set[str]] = {"workers", "days"}  # Required context keys
    
    def apply(self, model: pulp.LpProblem, x: dict[VarKey, LpVariable], ctx: Context):
        self.ensure_requires(ctx)  # Validates context
        # Add constraints to model using x variables and ctx data

register(MyConstraint())  # Auto-registered via autoimport.py
```
- `c01_*.py` to `c07_*.py`: Hard constraints (must satisfy)
- `s01_*.py` to `s06_*.py`: Soft constraints (penalties in objective)
- Auto-import via `src/constraints/autoimport.py` - just create the file

**Context TypedDict Pattern**
`Context` (in `src/domain/context.py`) is a TypedDict with `Required` fields. All data flows through this:
```python
ctx = Context(
    hospitals=hospitals, workers=workers, days=days,
    specified_days=specified_days, preferences=preferences,
    max_assignments=max_assignments, required_hd=required_hd,
    variables=x
)
# Constraints read from ctx and may add slack variables/penalties
```

**VarKey NamedTuple**
Decision variables indexed by `VarKey(hospital: str, worker: str, day: date, shift_type: ShiftType)`

## Domain Model (`src/domain/types.py`)

**Core Enums:**
- `ShiftType`: `日勤`, `当直` (night), `AM`, `PM`
- `Weekday`: `月曜` through `日曜` (Japanese weekday strings)
- `Frequency`: `毎週` (weekly), `隔週` (biweekly), `指定日` (specific days)

**Domain Objects:**
- `Hospital`: name, `is_remote`, `is_university`, `demand_rules: list[HospitalDemandRule]`
  - `HospitalDemandRule`: shift_type, weekdays, frequency
- `Worker`: name, `is_diagnostic_specialist`, `assignments: list[WorkerAssignmentRule]`
  - `WorkerAssignmentRule`: hospital, weekdays, shift_type

## Critical Developer Workflows

### Setup & Run
```bash
uv sync                          # Install dependencies (not "pip install")
uv run -m src.gui.app           # Launch GUI
uv run -m src.cli.main --help   # CLI usage
uv run -m pytest                # Run all tests
```

### Pre-commit Hooks (Lefthook)
- **Format:** `uv run ruff format {staged_files}` (auto-staged)
- **Lint:** `uv run ruff check --fix {staged_files}`
- **Type check:** `uv run mypy src` (strict mode, tests excluded)
- **Tests on push:** `uv run -m pytest -q`

Install hooks: `lefthook install` (if not auto-installed)

### Testing Conventions
- **Naming:** `test_c##_*.py` (hard constraints), `test_s##_*.py` (soft constraints)
- **Pattern:** Use `tmp_path` fixture for file I/O tests
- **Structure:** `tests/` mirrors `src/` structure
- **Example pattern:**
  ```python
  def test_constraint_with_temp_file(tmp_path):
      path = tmp_path / "test.toml"
      path.write_text("[workers]\nname = \"Taro\"")
      result = load_workers(str(path))
      assert result[0].name == "Taro"
  ```

### Adding New Constraints
1. Create `src/constraints/c##_name.py` (hard) or `s##_name.py` (soft)
2. Inherit `ConstraintBase`, set `name`, `summary`, `requires`
3. Implement `apply()` method
4. Call `register(YourConstraint())` at module level
5. Create matching `tests/test_c##_name.py` or `tests/test_s##_name.py`
6. No need to import anywhere - auto-discovered by `autoimport.py`

**Soft constraint pattern:** Add penalty variables to `ctx["penalties"]` list, not directly to objective.

## File Organization Conventions

### Config Files (`config/`, `data/`)
- **Monthly:** `data/specified-dates.toml`, `data/max-assignments.csv`
- **Personnel changes:** `config/hospitals.toml`, `config/workers.toml`
- **Year-specific:** `config/2026年度/`, `data/2026年度/` (optional subdirectories)

### Source Layout
```
src/
├── domain/       # Types and context (no business logic)
├── io/           # Loaders/writers for TOML/CSV/Excel
├── model/        # Variable builder, demand computation
├── constraints/  # Plugin constraints (auto-discovered)
├── optimizer/    # Solver, objective, penalty reporting
├── cli/          # CLI entrypoint (main.py)
├── gui/          # PySide6 GUI (app.py, editors)
└── calendar/     # Date utilities (jpholiday integration)
```

### Naming Patterns
- **Loaders:** `load_<entity>()` returns domain objects (e.g., `load_hospitals()` → `list[Hospital]`)
- **Writers:** `dump_<entity>()` writes domain objects to files
- **Constraints:** `c##_` (hard), `s##_` (soft) prefixes
- **Tests:** Mirror source structure, `test_<module_name>.py`

## Project-Specific Conventions

### Japanese Strings in Code
Domain enums use Japanese strings as values (`月曜`, `日勤`, `毎週`). This is **intentional** - they appear directly in TOML configs and Excel output. Do not "fix" to English.

### TOML Format Specifics
- Use `tomlkit` (not `tomli`) for preserving formatting/comments
- Workers/Hospitals use array-of-tables (`[[workers]]`, `[[hospitals]]`)
- Specified days: `"病院名" = [1, 15, 30]` (day numbers, 1-indexed)

### Excel Output Format
- Row 1: Hospital names
- Row 2: Dates (formatted)
- Data rows: Worker assignments per day
- Highlighting: Yellow for shortage, conditional formatting for patterns

### Two-Stage Optimization
**Critical:** The objective is built in two stages:
1. Minimize `lpSum(shortage_slack.values())` → solve
2. Fix shortage slacks, minimize `lpSum(penalty_items)` → re-solve

See `src/optimizer/objective.py:set_two_stage_objective()`. Never add penalties directly to initial objective.

### uv, not pip
Always use `uv run` for commands. Dependencies managed by `uv sync`, not pip. `pyproject.toml` is source of truth.

## Integration Points

- **Calendar:** `jpholiday` for Japanese public holidays → excludes non-night shifts on holidays
- **Solver:** PuLP with CBC (default), supports other MIP solvers via `pulp.LpSolver`
- **GUI:** PySide6 with custom table editors (no Qt Designer files)
- **Lefthook:** Git hooks for formatting/linting/testing

## Common Pitfalls

1. **VarKey creation:** Use `VarKey(h.name, w.name, d, s)` not `(h.name, w.name, d, s)` - NamedTuple ensures field names
2. **Context validation:** Always call `self.ensure_requires(ctx)` in constraints
3. **Materialization:** Only `UB=1` variables are created - check `vb.ub` dict before expecting a variable to exist
4. **Weekday indexing:** `date.weekday()` returns 0-6, but `Weekday` enum is Japanese strings
5. **Test isolation:** Use `tmp_path`, don't modify `config/` or `data/` directly in tests
6. **Penalty reporting:** Add to `ctx["penalties"]`, not model objective directly

## Key Files Reference

- [src/cli/main.py](src/cli/main.py) - Full pipeline example in `build_and_solve()`
- [src/model/variable_builder.py](src/model/variable_builder.py) - Three-stage filtering logic
- [src/constraints/base_impl.py](src/constraints/base_impl.py) - Constraint interface
- [src/constraints/autoimport.py](src/constraints/autoimport.py) - Plugin discovery
- [docs/architecture/data-flow.md](docs/architecture/data-flow.md) - Detailed pipeline documentation
- [docs/architecture/constraint-system.md](docs/architecture/constraint-system.md) - Plugin architecture
