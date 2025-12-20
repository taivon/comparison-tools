# Project Context for Claude

> **Important**: This file should be kept in sync with `agents.md`. When updating this file, also update `agents.md` with the same changes, and vice versa.

## Deployment
- **Platform**: Google App Engine
- **Database**: Supabase PostgreSQL
- **Authentication**: Google OAuth only (via social-auth-app-django)

## Architecture
- Django 5.x web application
- Multi-product comparison tools (apartments, homes, hotels)
- Stripe integration for subscriptions
- Tailwind CSS for styling

## Package Management
This project uses [UV](https://docs.astral.sh/uv/) for fast Python package management.

```bash
# Install dependencies
uv sync

# Add a new dependency
uv add <package>

# Remove a dependency
uv remove <package>

# Update all dependencies
uv lock --upgrade
```

## Key Commands
```bash
# Run locally
uv run python manage.py runserver

# Run migrations
uv run python manage.py migrate

# Seed subscription products/plans
uv run python manage.py seed_products

# Run tests
uv run python manage.py test

# Deploy to App Engine
gcloud app deploy
```

## Pre-Push Requirements
Before pushing to the repository, a git pre-push hook automatically runs:
1. **Linting**: Runs `ruff check --fix` to auto-fix linting issues
2. **Formatting**: Runs `ruff format` to format code
3. **Tests**: Runs `python manage.py test` to ensure all tests pass

If any of these checks fail, the push will be blocked. If auto-fix makes changes, you'll need to commit them before pushing.

## Information Citation Guidelines
When providing information, follow these citation standards:

1. **Cite documentation sources whenever possible**, especially for claims about how tools, services, or APIs work.
2. **If documentation cannot be found to support a claim**, clearly state that the information is based on inference or general knowledge.
3. **Prefer linking to official documentation** over blog posts or community discussions whenever available.

## Unit Testing Conventions
When writing unit tests, follow these guidelines:

1. **First, look for existing test files in the same directory** to match patterns, structure, and testing tools.
2. **If none are found, look for test files elsewhere in the project** to understand the project's testing conventions.
3. **If no test files exist in the project**, use best practices:
   - Follow standard test file naming conventions (e.g., `test_*.py` or `*_test.py`)
   - Use appropriate testing frameworks for the language/project (e.g., Django's `TestCase` for Django projects)
   - Structure tests with clear describe/setup blocks or equivalent
   - Include setup/tear down as needed
   - Mock external dependencies appropriately
   - **Only test your own code**, not the functionality of external libraries or dependencies

## Environment Variables (Production)
- `DATABASE_URL` - Supabase PostgreSQL connection string
- `STRIPE_SECRET_KEY` - Stripe API key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing secret
- `SOCIAL_AUTH_GOOGLE_OAUTH2_KEY` - Google OAuth client ID
- `SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET` - Google OAuth client secret
- `SECRET_KEY` - Django secret key
- `GOOGLE_MAPS_API_KEY` - Google Maps API key (for address autocomplete and driving distances)

## UI Patterns

### Tooltips in Tables
Tooltips inside table cells get clipped by `overflow-x-auto` on the table container. To fix this:

1. Use a CSS class for the tooltip (e.g., `.score-breakdown-tooltip`, `.net-effective-tooltip`)
2. Add the tooltip to `setupTooltipPositioning()` in dashboard.html JavaScript
3. This function uses `position: fixed` to escape the overflow container and calculates position using `getBoundingClientRect()`

Example tooltip structure:
```html
<div class="group relative">
    <div class="cursor-help">Trigger content</div>
    <div class="my-tooltip hidden group-hover:block absolute z-50 w-64 text-xs rounded-lg shadow-lg p-3">
        Tooltip content
        <div class="tooltip-arrow absolute left-4 w-3 h-3 transform rotate-45"></div>
    </div>
</div>
```

Then in `setupTooltipPositioning()`:
```javascript
const tooltip = group.querySelector('.net-effective-tooltip') || group.querySelector('.score-breakdown-tooltip') || group.querySelector('.my-tooltip');
```
