# Constraint System Architecture

This document details the plugin-based constraint system architecture used in the OptiRoster application.

## Overview

The constraint system implements a plugin architecture that allows for modular addition and removal of optimization constraints. The system separates hard constraints (must be satisfied) from soft constraints (optimization objectives) while providing a unified interface for constraint management.

## Architecture Components

### 1. Registry Pattern (`base.py`)

The core registry system manages constraint registration and discovery:

```python
constraint_registry = []  # Global constraint registry

def register(constraint: ConstraintBase) -> None:
    """Register a constraint instance for use in optimization"""
    constraint_registry.append(constraint)

def all_constraints() -> list[ConstraintBase]:
    """Get all registered constraints"""
    return list(constraint_registry)
```

**Key Features:**

- Global registry for constraint discovery
- Runtime constraint registration
- Simple list-based storage for constraint instances

### 2. Base Constraint Interface (`base_impl.py`)

All constraints implement the `ConstraintBase` abstract class:

```python
class ConstraintBase(ABC):
    name: str = "unnamed"                    # Constraint identifier  
    summary: str = "no summary"              # Human-readable description
    requires: ClassVar[set[str]] = set()     # Required context keys

    def ensure_requires(self, ctx: Mapping[str, Any]) -> None:
        """Validate required context keys are present"""
        miss = self.requires - set(ctx.keys())
        if miss:
            raise RuntimeError(f"{self.name}: missing ctx keys: {sorted(miss)}")

    @abstractmethod
    def apply(
        self,
        model: pulp.LpProblem,              # PuLP optimization model
        x: Mapping[VarKey, pulp.LpVariable], # Decision variables
        ctx: Context,                        # Optimization context
    ) -> None:
        """Add constraints to the optimization model"""
        pass
```

**Design Principles:**

- **Abstract Interface**: Ensures consistent constraint implementation
- **Context Validation**: Automatic validation of required data dependencies
- **Type Safety**: Strong typing for optimization components
- **Name-based Identification**: Each constraint has a unique name for debugging

### 3. Auto-Import System (`autoimport.py`)

Automatic discovery and loading of constraint modules:

```python
def auto_import_all() -> None:
    """Automatically import all constraint modules"""
    from . import __path__ as pkg_path

    for m in pkgutil.iter_modules(pkg_path):
        name = m.name
        if name.startswith("_"):
            continue
        if name in {"base", "base_impl", "autoimport"}:
            continue
        importlib.import_module(f"src.constraints.{name}")
```

**Features:**

- **Zero-Configuration**: No manual constraint registration needed
- **Module Discovery**: Automatically finds constraint modules
- **Selective Import**: Skips internal/utility modules
- **Plugin Loading**: Enables true plugin architecture

## Constraint Implementation Pattern

### Hard Constraint Example

```python
from .base import register
from .base_impl import ConstraintBase

class OnePersonPerHospital(ConstraintBase):
    name = "one_person_per_hospital"
    summary = "必要な(病院, 日)ごとに勤務者は1人"
    requires: ClassVar[set[str]] = {"required_hd"}  # Dependencies

    @override
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context
    ) -> None:
        self.ensure_requires(ctx)  # Validate dependencies

        required_hd = ctx["required_hd"]  # Extract context data
        by_hd = defaultdict(list)

        # Group variables by hospital-date
        for (h, _, d, _), var in x.items():
            by_hd[(h, d)].append(var)

        # Add constraint: exactly one person per hospital per required date
        for h, d in required_hd:
            vars_hd = by_hd.get((h, d), [])
            model += pulp.lpSum(vars_hd) == 1, f"one_person_{h}_{d.strftime('%Y%m%d')}"

# Auto-registration when module is imported
register(OnePersonPerHospital())
```

## Constraint Categories

### Hard Constraints (c##\_prefix)

Must be satisfied for a valid solution:

- `c01_one_person_per_hospital`: Each hospital-date needs exactly one person
- `c02_no_overlap_same_time`: No simultaneous assignments for one person
- `c03_respect_preferences`: Honor worker preferences (cannot work when marked unavailable)
- `c04_max_assignments_per_worker_hospital`: Limit assignments per worker per hospital
- `c05_night_spacing`: Minimum spacing between night duties
- `c06_forbid_remote_after_night`: No remote assignments after night duty
- `c07_univ_last_holiday_night_specialist`: University holiday night duties require specialists

### Soft Constraints (s##\_prefix)

Optimization objectives with penalties:

- `s01_night_spacing_pairs`: Maximize night duty spacing
- `s02_soft_no_night_remote_daypm_same_day`: Avoid night + remote on same day
- `s03_night_deviation_band`: Balance night duty assignments
- `s04_soft_balance_non_night_by_weekday`: Balance weekday assignments
- `s05_soft_no_duty_after_night`: Avoid Day/AM duty assignments the day after night duty

## Context System Integration

### Context Keys

The constraint system uses a typed context system:

```python
@dataclass
class Context:
    hospitals: list[Hospital]
    workers: list[Worker]
    required_hd: set[tuple[str, date]]  # Required (hospital, date) pairs
    # ... other context data
```

### VarKey System

Decision variables are indexed by structured keys:

```python
VarKey = tuple[str, str, date, ShiftType]  # (hospital, worker, date, shift)
```

## Plugin Lifecycle

```mermaid
graph TD
    A[Application Start] --> B[auto_import_all()]
    B --> C[Load Constraint Modules]
    C --> D[Module Import Triggers register()]
    D --> E[Constraint Instance Added to Registry]
    E --> F[Optimization Phase]
    F --> G[all_constraints() Returns List]
    G --> H[Apply Each Constraint to Model]
    H --> I[Solve Optimization Problem]
```

## Adding New Constraints

### 1. Create Constraint Module

```python
# src/constraints/c08_my_new_constraint.py
from .base import register
from .base_impl import ConstraintBase

class MyNewConstraint(ConstraintBase):
    name = "my_new_constraint"
    requires: ClassVar[set[str]] = {"workers", "hospitals"}

    @override
    def apply(self, model, x, ctx):
        self.ensure_requires(ctx)
        # Add your constraint logic here
        pass

register(MyNewConstraint())
```

### 2. Auto-Discovery

The constraint is automatically discovered and loaded when the application starts.

### 3. Testing

```python
# tests/test_my_new_constraint.py
def test_my_new_constraint():
    constraint = MyNewConstraint()
    # Test constraint logic
    assert constraint.name == "my_new_constraint"
```

## Design Benefits

### Modularity

- Each constraint is self-contained
- Easy to add/remove constraints
- Clear separation of concerns

### Extensibility

- Plugin-based architecture
- No core system modifications needed
- Support for both hard and soft constraints

### Maintainability

- Consistent interface across all constraints
- Automatic dependency validation
- Clear naming conventions

### Testability

- Individual constraint testing
- Registry isolation in tests
- Dependency injection through context

## Performance Considerations

- **Lazy Loading**: Constraints loaded only when needed
- **Registry Efficiency**: Simple list-based registry for small constraint counts
- **Context Validation**: Early validation prevents runtime errors
- **Memory Usage**: Constraint instances are lightweight

## Integration with Optimizer

The constraint system integrates with the PuLP optimization framework:

1. **Model Creation**: Empty PuLP model created
2. **Variable Generation**: Decision variables created based on domain model
3. **Constraint Application**: Each registered constraint adds rules to model
4. **Optimization**: PuLP solver finds optimal solution
5. **Result Processing**: Solution extracted and formatted

This architecture provides a robust, extensible foundation for complex optimization constraint management.
