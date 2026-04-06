# Homework Description Collapsible View - Implementation Plan

## Issue Summary

**Problem**: The homework list view (`homeworks/list.html`) displays full markdown descriptions for all homework cards without any collapsible mechanism. When homework assignments have vastly different description lengths, the UI appears inconsistent.

**Goal**: Apply the same `<details>/<summary>` collapsible pattern used in `courses/list.html` to hide long homework descriptions by default while keeping them accessible.

**User Feedback**: Apply the same patterns as in `courses/list.html`

## Current Implementation

### Reference Pattern in `courses/list.html` (lines 81-94)

```html
{% if course.description %}
<div class="card-text">
    <details>
        <summary class="text-primary" style="cursor: pointer;">
            <i class="bi bi-chevron-down"></i> View Description
        </summary>
        <div class="mt-2">
            <zero-md src="data:text/markdown;charset=utf-8,{{ course.description|urlencode }}">
            <template data-append>
                <style>.markdown-body { background-color: transparent !important; }</style>
            </template>
        </div>
    </details>
</div>
{% endif %}
```

### Current Homework List Implementation

In `src/homeworks/templates/homeworks/list.html` (lines 57-64):
```html
<div class="card-text">
    <zero-md src="data:text/markdown;charset=utf-8,{{ homework.description|urlencode }}">
    <template data-append>
        <style>.markdown-body { background-color: transparent !important; }</style>
    </template>
</zero-md>
</div>
```

## Proposed Solution

Apply the identical `<details>/<summary>` pattern from `courses/list.html` to `homeworks/list.html`.

## Files to Modify

| File | Change Type | Lines Affected |
|------|-------------|----------------|
| `src/homeworks/templates/homeworks/list.html` | Modify | 57-64 |

## Implementation Details

### Template Changes

**Location**: `src/homeworks/templates/homeworks/list.html`, lines 57-64

**Current Code**:
```html
<div class="card-text">
    <zero-md src="data:text/markdown;charset=utf-8,{{ homework.description|urlencode }}">
    <template data-append>
        <style>.markdown-body { background-color: transparent !important; }</style>
    </template>
</zero-md>
</div>
```

**New Code**:
```html
{% if homework.description %}
<div class="card-text">
    <details>
        <summary class="text-primary" style="cursor: pointer;">
            <i class="bi bi-chevron-down"></i> View Description
        </summary>
        <div class="mt-2">
            <zero-md src="data:text/markdown;charset=utf-8,{{ homework.description|urlencode }}">
            <template data-append>
                <style>.markdown-body { background-color: transparent !important; }</style>
            </template>
        </div>
    </details>
</div>
{% endif %}
```

## No Changes Required

The following components require no changes:

- **`src/homeworks/views.py`**: `HomeworkListItem` dataclass (line 42-57) already includes the `description` field
- **`src/homeworks/models.py`**: No model changes needed
- **JavaScript**: No new JavaScript needed - `<details>/<summary>` is native HTML
- **Tests**: Existing tests verify description data passing; no test changes required

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Empty description | No description section rendered (conditional `{% if %}`) |
| None/Null description | No description section rendered |
| Very long description | Hidden by default inside `<details>`, expanded on click |
| Short description | Hidden by default (consistent UI across all cards) |
| Markdown with special chars | `urlencode` filter handles special characters |
| HTML/markdown content | Rendered correctly inside zero-md component |

## Testing Plan

### Manual Testing Checklist
1. Navigate to homework list page
2. Verify homework cards with descriptions show "View Description" toggle
3. Verify homework cards without descriptions show no description section
4. Click "View Description" and verify full description expands
5. Click collapsed summary and verify description collapses again
6. Verify markdown renders correctly in expanded view

### Automated Testing
```bash
uv run python run_tests.py --settings=src.llteacher.test_settings apps.homeworks.tests
```

## Comparison: Before vs After

### Before
- All descriptions visible by default
- Inconsistent card heights when descriptions vary in length
- Visual clutter from long markdown content

### After
- All descriptions collapsed by default
- Consistent card appearance
- Clean "View Description" toggle for all cards
- Identical UX pattern to courses list page

## Implementation Steps

1. Read `src/homeworks/templates/homeworks/list.html`
2. Modify lines 57-64 to wrap description in `<details>/<summary>` with conditional
3. Run tests to verify no regressions
4. Commit changes (if requested by user)
