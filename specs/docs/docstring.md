---
size: small
modified_date: 2026-05-10
implemented_git_tag: 1cf3cb7
---

# Add a standardized docstring to all functions in python files

## Current state
Python files have docstrings of various formats and information

## Target state
All functions defined in .py files get a uniform docstring

### Docstring format

```python
def my_function(param: str) -> bool:
    """Short description of what the function does.

    param: description of the parameter.

    Returns: description of the return value.

    ExceptionName1: condition that triggers the error. (omitted if none)
    ExceptionName2: condition that triggers the error. (omitted if none)

    Side-effects: description of side-effects. (omitted if none)
    """
```
### Side-effects
Update CONTRIBUTING.md with new docstring format

---

> **Note on file paths:** This spec was authored when all Python modules lived in
> the project root. As of spec
> [`refactors/src_layout_package.md`](../refactors/src_layout_package.md), the
> source code has been moved under `src/resourcery_ssg/`. References to `.py`
> files at the root now refer to `src/resourcery_ssg/`. The docstring conventions
> defined by this spec apply identically in the new location.