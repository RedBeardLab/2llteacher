# Implementation Plan: Show Range on Slider

## 1. Problem Summary

The assessment slider (`<input type="range">`) currently renders without visibly indicating its min/max range. Students see a thumb that slides but have no immediate visual cue that the range is 0–10. This degrades UX by forcing the user to guess or discover the range through interaction.

## 2. Current State

The slider range attributes `min="0" max="10"` are hardcoded in HTML templates in three locations. There is no single source of truth for the range constants. The backend validates against the same hardcoded bounds in `views.py:1452` and the model uses `MinValueValidator(0)/MaxValueValidator(10)` in `conversations/models.py:245-252`.

### Affected template locations

| Template | Lines | Context |
|---|---|---|
| `widget_answer.html` | 21 | Disabled "pre" value display (post mode) |
| `widget_answer.html` | 32 | Active slider (pre or post) |
| `detail.html` | 123-125 | Pre-assessment inline slider |
| `detail.html` | 295-296 | Disabled pre-value display (post section) |
| `detail.html` | 300-302 | Post-assessment inline slider |

## 3. Proposed Solution

Add static text labels showing the minimum (0) and maximum (10) values to the left and right of each slider, respectively. This requires **template-only changes** — no backend, model, or view modifications.

### 3.1 Design

Each slider currently lives inside a `d-flex align-items-center gap-3` container (detail.html) or a bare `<p>` (widget_answer.html). The labels will be inserted directly beside the slider element within the same flex row:

```
[ 0 ] ——————————●—————————— [ 10 ]
```

Visual approach:
- Small, muted text labels: `font-size: 0.8em`, `color: #6c757d` (Bootstrap's `text-muted`)
- Placed immediately before and after the `<input type="range">` element
- No JavaScript needed — these are static labels

### 3.2 Files to Modify

**File 1: `src/homeworks/templates/homeworks/widget_answer.html`**

- **Line 21** (disabled pre slider):
  ```html
  <span class="text-muted" style="font-size: 0.8em;">0</span>
  <input type="range" min="0" max="10" step="1" value="{{ data.pre_value }}" disabled oninput="this.nextElementSibling.textContent = this.value">
  <span class="text-muted" style="font-size: 0.8em;">10</span>
  ```

- **Line 32** (active slider):
  ```html
  <span class="text-muted" style="font-size: 0.8em;">0</span>
  <input type="range" name="value" min="0" max="10" step="1" value="5" id="slider" oninput="this.nextElementSibling.textContent = this.value">
  <span class="text-muted" style="font-size: 0.8em;">10</span>
  ```

- Wrap the slider row in a `d-flex align-items-center gap-2` container for consistent alignment (similar to the pattern already used in `detail.html`).

**File 2: `src/homeworks/templates/homeworks/detail.html`**

- **Lines 122-125** (pre slider):
  ```html
  <div class="d-flex align-items-center gap-2">
    <span class="text-muted" style="font-size: 0.8em;">0</span>
    <input type="range" name="value" min="0" max="10" step="1" value="5" class="flex-grow-1"
           oninput="this.nextElementSibling.textContent = this.value">
    <span style="font-weight: bold; font-size: 1.2em; min-width: 2em;">5</span>
    <span class="text-muted" style="font-size: 0.8em;">10</span>
  </div>
  ```

- **Lines 294-297** (disabled pre slider in post section):
  ```html
  <div class="d-flex align-items-center gap-2">
    <span class="text-muted" style="font-size: 0.8em;">0</span>
    <input type="range" min="0" max="10" step="1" value="{{ widget.pre_value }}" disabled class="flex-grow-1" oninput="this.nextElementSibling.textContent = this.value">
    <span style="font-weight: bold; font-size: 1.2em; min-width: 2em;">{{ widget.pre_value }}</span>
    <span class="text-muted" style="font-size: 0.8em;">10</span>
  </div>
  ```

- **Lines 299-302** (post slider):
  ```html
  <div class="d-flex align-items-center gap-2">
    <span class="text-muted" style="font-size: 0.8em;">0</span>
    <input type="range" name="value" min="0" max="10" step="1" value="5" class="flex-grow-1"
           oninput="this.nextElementSibling.textContent = this.value">
    <span style="font-weight: bold; font-size: 1.2em; min-width: 2em;">5</span>
    <span class="text-muted" style="font-size: 0.8em;">10</span>
  </div>
  ```

### 3.3 CSS Option (alternative, not required)

Instead of inline styles, we could add a reusable class to `static/css/main.css`:

```css
.slider-range-label {
    font-size: 0.8em;
    color: #6c757d;
    user-select: none;
    flex-shrink: 0;
}
```

Then use `<span class="slider-range-label">0</span>` in templates. The inline-style approach is lighter and consistent with existing patterns in these templates (see `style="font-weight: bold; font-size: 1.2em; min-width: 2em;"` already inline).

**Decision:** Use inline styles to match existing codebase conventions. A CSS class is optional polish.

## 4. Edge Cases

| Case | Handling |
|---|---|
| **Disabled slider (pre-value display)** | Labels still shown — they are static HTML, visually unaffected by `disabled` attribute |
| **Keyboard-navigation users** | No change — the labels are purely visual, adjacent `<span>` elements don't interfere with focus/keyboard flow |
| **Screen readers** | The labels are static text; screen readers will announce "0" and "10" alongside the slider role. No `aria-label` changes needed since `<input type="range">` already conveys its role and the min/max are programmatically available via the `min`/`max` attributes |
| **Dark mode** | `text-muted` class already adapts via Bootstrap's theme support |
| **Responsive / narrow viewports** | The flex layout with `gap-2` will naturally wrap or collapse. No breakpoint changes needed |

## 5. Testing

### 5.1 Template-based assertions (no new test classes needed)

Add assertions to existing test methods in `src/homeworks/tests/test_widget_answer_view.py`:

1. **`test_student_get_shows_pre_widget`** (line 68): Add `assertContains(response, "0")` and `assertContains(response, "10")` to verify range labels appear on the pre slider.

2. **`test_after_sections_completed_shows_post`** (line 238): Add `assertContains(response, "0")` and `assertContains(response, "10")` to verify range labels appear on the post slider.

3. **`test_student_get_shows_pre_value_locked_when_post`** (line 91): Verify that range labels appear on both the disabled pre slider and the active post slider.

### 5.2 Manual / visual verification

- Open the homework detail page as a student and verify:
  - Pre-assessment slider shows "0" left and "10" right
  - After answering pre, the answered badge shows, and post slider also shows labels
  - After answering everything, the completed state shows labels
- Open the dedicated widget answer page (`/homeworks/<id>/widgets/answer/`) and verify:
  - Pre mode: labels present on active slider
  - Post mode: labels present on both disabled pre slider and active post slider

### 5.3 No new route, view, model, or form changes

This change is purely cosmetic/template-level. No migrations, no new URL patterns, no new view logic.

## 6. Implementation Order

1. Edit `widget_answer.html` — add labels to the disabled slider (line 21) and the active slider (line 32)
2. Edit `detail.html` — add labels to all three slider instances (lines 122-125, 294-297, 299-302)
3. Run the existing test suite to confirm no regressions:
   ```
   uv run coverage run manage.py test --settings=src.llteacher.test_settings src/homeworks/tests/test_widget_answer_view.py
   ```
4. (Optional) Add `assertContains` checks for "0" and "10" in the relevant test methods

## 7. Summary

| What | Detail |
|---|---|
| **Files modified** | 2 templates: `widget_answer.html`, `detail.html` |
| **Files created** | 0 |
| **Backend changes** | None |
| **New tests** | ~3 `assertContains` lines added to existing test methods |
| **Risk** | Low — purely presentational change to static HTML |
