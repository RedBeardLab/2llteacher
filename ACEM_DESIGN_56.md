# Design Document: Change "Homeworks" Tab Name to "Homework"

## Issue Summary

The tab containing homework assignments is incorrectly labeled "Homeworks" when it should be "Homework" (singular).

## Overview

This is a straightforward text change across multiple template files. The Django project does not use internationalization (i18n), so all text changes will be direct string replacements.

## Files to Modify

### User-Facing Text Changes

The following files contain user-visible "Homeworks" text that should be changed to "Homework":

| File | Line(s) | Context | Change |
|------|---------|---------|--------|
| `templates/base.html` | 49 | Nav tab link | `Homeworks` → `Homework` |
| `templates/homepage.html` | 56 | Button text | `View Homeworks` → `View Homework` |
| `src/homeworks/templates/homeworks/list.html` | 3, 14 | Page title and h1 | `Homeworks` → `Homework` |
| `src/homeworks/templates/homeworks/matrix.html` | 44, 112 | Label text | `Total Homeworks` → `Total Homework`, `No Homeworks` → `No Homework` |
| `src/homeworks/templates/homeworks/non_interactive_answer.html` | 15 | Breadcrumb | `Homeworks` → `Homework` |
| `src/homeworks/templates/homeworks/section_detail.html` | 22 | Breadcrumb | `Homeworks` → `Homework` |
| `src/courses/templates/courses/detail.html` | 48, 52 | Section header | `Homeworks` → `Homework` |
| `src/conversations/templates/conversations/detail.html` | 19, 221 | Breadcrumb and back link | `Homeworks` → `Homework` |
| `src/conversations/templates/conversations/start.html` | 12 | Breadcrumb | `Homeworks` → `Homework` |
| `src/conversations/templates/conversations/section_answers.html` | 11 | Breadcrumb | `Homeworks` → `Homework` |

### Files NOT to Modify

The following contain "Homeworks" but are non-user-facing or follow Django conventions:

- `src/homeworks/__init__.py` - App comment
- `src/homeworks/apps.py` - Django app config class name (`HomeworksConfig`)
- `src/llteacher/management/commands/populate_test_database.py` - Logging output
- `VIEWS.md`, `CLAUDE.md`, `DATABASE_POPULATION.md`, `legacy_documentation/` - Documentation

## Implementation

### Step 1: Update Navigation Tab

**File:** `templates/base.html` (line 49)

```html
<!-- Before -->
<a class="nav-link {% if request.path == '/homeworks/' %}active{% endif %}" href="{% url 'homeworks:list' %}">Homeworks</a>

<!-- After -->
<a class="nav-link {% if request.path == '/homeworks/' %}active{% endif %}" href="{% url 'homeworks:list' %}">Homework</a>
```

### Step 2: Update Homepage Button

**File:** `templates/homepage.html` (line 56)

```html
<!-- Before -->
<a href="{% url 'homeworks:list' %}" class="btn btn-success btn-lg">View Homeworks</a>

<!-- After -->
<a href="{% url 'homeworks:list' %}" class="btn btn-success btn-lg">View Homework</a>
```

### Step 3: Update Homework List Template

**File:** `src/homeworks/templates/homeworks/list.html` (lines 3 and 14)

```html
<!-- Before -->
{% block title %}Homeworks{% endblock %}
...
<h1>Homeworks</h1>

<!-- After -->
{% block title %}Homework{% endblock %}
...
<h1>Homework</h1>
```

### Step 4: Update Matrix Template

**File:** `src/homeworks/templates/homeworks/matrix.html` (lines 44 and 112)

```html
<!-- Before -->
<small class="text-muted">Total Homeworks</small>
...
<th class="text-center text-muted">No Homeworks</th>

<!-- After -->
<small class="text-muted">Total Homework</small>
...
<th class="text-center text-muted">No Homework</th>
```

### Step 5: Update Breadcrumbs and Links

Update the following breadcrumb items from `Homeworks` to `Homework`:

- `src/homeworks/templates/homeworks/non_interactive_answer.html` (line 15)
- `src/homeworks/templates/homeworks/section_detail.html` (line 22)

### Step 6: Update Course Detail Template

**File:** `src/courses/templates/courses/detail.html` (lines 48, 52)

```html
<!-- Before -->
<!-- Homeworks Section -->
<h2 class="mb-0"><i class="bi bi-file-text"></i> Homeworks</h2>

<!-- After -->
<!-- Homework Section -->
<h2 class="mb-0"><i class="bi bi-file-text"></i> Homework</h2>
```

### Step 7: Update Conversation Templates

Update breadcrumb and back links in:

- `src/conversations/templates/conversations/detail.html` (lines 19, 221)
- `src/conversations/templates/conversations/start.html` (line 12)
- `src/conversations/templates/conversations/section_answers.html` (line 11)

## Edge Cases

1. **URL Path**: The URL remains `/homeworks/` - this change is only cosmetic (display text), not a URL rename. No URL changes are required.

2. **Sentence Context**: When "Homeworks" appears in sentences like "You haven't created any homeworks yet", these should also be changed to singular for consistency:
   - `src/homeworks/templates/homeworks/list.html` (line 21): `"You haven't created any homeworks yet"` → `"You haven't created any homework yet"`

3. **Case Sensitivity**: All changes are simple singular/plural updates with no case sensitivity issues.

## Testing

1. **Visual Verification**: After making changes, navigate through the application to verify:
   - Nav tab shows "Homework" (singular)
   - Homepage button shows "View Homework"
   - All breadcrumbs and section headers are singular

2. **No URL Changes**: Verify that all existing links still work - only text display changed.

## Summary of Changes

| File | Changes |
|------|---------|
| `templates/base.html` | 1 line |
| `templates/homepage.html` | 1 line |
| `src/homeworks/templates/homeworks/list.html` | 3 lines |
| `src/homeworks/templates/homeworks/matrix.html` | 2 lines |
| `src/homeworks/templates/homeworks/non_interactive_answer.html` | 1 line |
| `src/homeworks/templates/homeworks/section_detail.html` | 1 line |
| `src/courses/templates/courses/detail.html` | 2 lines |
| `src/conversations/templates/conversations/detail.html` | 2 lines |
| `src/conversations/templates/conversations/start.html` | 1 line |
| `src/conversations/templates/conversations/section_answers.html` | 1 line |

**Total: 15 lines across 10 files**

This is a low-risk change affecting only user-facing display text with no functional impact.
