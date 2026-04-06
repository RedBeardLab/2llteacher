# Homework Description Truncation - Implementation Plan

## Issue Summary

**Problem**: The homework list view (`homeworks/list.html`) displays full markdown descriptions for all homework cards. When one homework has a very long description and others don't, the UI looks inconsistent and unprofessional.

**Goal**: Truncate long homework descriptions in the homework list view, similar to how course descriptions are handled in the course detail view.

## Current Implementation

### Course Description Pattern (Reference)

In `src/courses/templates/courses/detail.html` (line 81):
```html
<p class="mb-1 text-muted">{{ homework.description|truncatewords:20 }}</p>
```

### Homework List Current Implementation

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

Follow the same pattern used in the course detail view: use Django's `|truncatewords:20` filter to limit description display in the list view.

### Files to Modify

1. **`src/homeworks/templates/homeworks/list.html`** - Update the list template to conditionally truncate descriptions

### Implementation Details

#### Template Changes

Replace the full description rendering with a conditional approach:
- If description is short (≤20 words), show full description
- If description is longer (>20 words), show truncated version with "Read more" link

**New code for `list.html` (lines 57-64):**

```html
<div class="card-text">
    {% with homework.description|truncatewords:20 as truncated_desc %}
        {% if homework.description|wordcount <= 20 %}
            <zero-md src="data:text/markdown;charset=utf-8,{{ homework.description|urlencode }}">
                <template data-append>
                    <style>.markdown-body { background-color: transparent !important; }</style>
                </template>
            </zero-md>
        {% else %}
            <div class="homework-description" data-full-description="{{ homework.description|urlencode }}">
                <div class="description-truncated">
                    <p class="text-muted mb-2">
                        <zero-md src="data:text/markdown;charset=utf-8,{{ truncated_desc|urlencode }}">
                            <template data-append>
                                <style>.markdown-body { background-color: transparent !important; }</style>
                            </template>
                        </zero-md>
                    </p>
                    <button type="button" class="btn btn-link p-0 text-decoration-none" onclick="toggleHomeworkDescription(this)">
                        Read more <i class="bi bi-chevron-down"></i>
                    </button>
                </div>
                <div class="description-full d-none">
                    <zero-md src="data:text/markdown;charset=utf-8,{{ homework.description|urlencode }}">
                        <template data-append>
                            <style>.markdown-body { background-color: transparent !important; }</style>
                        </template>
                    </zero-md>
                    <button type="button" class="btn btn-link p-0 text-decoration-none mt-2" onclick="toggleHomeworkDescription(this)">
                        Show less <i class="bi bi-chevron-up"></i>
                    </button>
                </div>
            </div>
        {% endif %}
    {% endwith %}
</div>
```

#### JavaScript Addition

Add a JavaScript function to `base.html` or create a new file `static/js/homework-ui.js`:

```javascript
function toggleHomeworkDescription(button) {
    const container = button.closest('.homework-description');
    const truncated = container.querySelector('.description-truncated');
    const full = container.querySelector('.description-full');
    
    truncated.classList.toggle('d-none');
    full.classList.toggle('d-none');
}
```

Or inline in the template (simpler approach):

```html
<script>
function toggleHomeworkDescription(btn) {
    const container = btn.closest('.homework-description');
    const truncated = container.querySelector('.description-truncated');
    const full = container.querySelector('.description-full');
    truncated.classList.toggle('d-none');
    full.classList.toggle('d-none');
}
</script>
```

## Alternative Approaches Considered

### Option A: Pure CSS Truncation (Rejected)
Using CSS `max-height` and `overflow` to truncate zero-md content. This was rejected because zero-md renders markdown into the shadow DOM, making CSS truncation unreliable.

### Option B: Backend Truncation (Rejected)
Adding a `description_truncated` field to `HomeworkListItem` dataclass. This adds complexity without significant benefit since template-level truncation is simpler.

### Option C: Character-based Truncation (Rejected)
Using `|truncatechars:200` instead of `|truncatewords:20`. Word-based truncation is preferred for readability in markdown content.

## Data Structure Changes

No changes required to `HomeworkListItem` dataclass in `views.py`. The truncation happens at the template level using Django's built-in filters.

## Testing Plan

### Manual Testing
1. Create a homework with a short description (<20 words)
2. Create a homework with a long description (>20 words)
3. Verify short descriptions display fully
4. Verify long descriptions show truncated text with "Read more" button
5. Click "Read more" and verify full description displays
6. Click "Show less" and verify truncation returns

### Automated Testing
No new tests required for this UI-only change. Existing tests verify description data integrity.

## Edge Cases

1. **Empty description**: Handled gracefully - `|truncatewords:20` on empty string returns empty string
2. **Description with exactly 20 words**: Will display full description (wordcount = 20, not > 20)
3. **Description with special characters**: `urlencode` filter handles special characters in URLs
4. **Zero-md rendering errors**: Existing behavior unchanged

## Rollout Plan

1. Modify `src/homeworks/templates/homeworks/list.html`
2. Add JavaScript toggle function (either inline or in a new JS file)
3. Test locally with various description lengths
4. Commit changes

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/homeworks/templates/homeworks/list.html` | Modify | Add conditional truncation logic for homework descriptions |
