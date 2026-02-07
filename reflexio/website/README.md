# /user_profiler/reflexio/website
Description: Next.js frontend for viewing user profiles and interactions

## Main Entry Points

- **Root**: `app/page.tsx` - Landing page
- **Layout**: `app/layout.tsx` - App layout with sidebar navigation
- **Login**: `app/login/page.tsx` - User authentication page
- **Register**: `app/register/page.tsx` - User registration page
- **Profiles**: `app/profiles/page.tsx` - View and search user profiles
- **Interactions**: `app/interactions/page.tsx` - View conversation history
- **Feedbacks**: `app/feedbacks/page.tsx` - View and manage user feedback
- **Evaluations**: `app/evaluations/page.tsx` - View agent success evaluation results
- **Settings**: `app/settings/page.tsx` - Configuration and settings management

## Purpose

1. **Authentication** - User login and registration (skipped in self-host mode)
2. **Profile viewing** - Display extracted user profiles with search
3. **Interaction browsing** - View conversation history, tool usage (tool name + inputs), and context
4. **Feedback management** - View and manage user feedback (displays blocking issues when present)
5. **Evaluation monitoring** - Track agent success metrics and analyze failures
6. **Settings configuration** - Manage application settings including root-level tool configuration (`tool_can_use`)
7. **API integration** - Sync client communicates with FastAPI backend

## Components

**Directory**: `components/`

Key files:
- `sidebar.tsx`: Navigation sidebar for switching between views
- `layout-content.tsx`: Authentication wrapper that handles auth routing and sidebar display
- `ui/`: ShadCN UI components (button, card, input, table, etc.)

## Architecture Pattern

**Next.js App Router** - Uses React Server Components where possible
**ShadCN UI** - Consistent design system across pages
**Backend API** - Calls FastAPI server at `http://0.0.0.0:8081`

## Development

**Start dev server:**
```bash
npm run dev
```
Open http://localhost:8080

**Build:**
```bash
npm run build
npm run start
```

## Styling

- **Tailwind CSS** - Utility-first styling
- **globals.css** - Global styles and CSS variables
- **ShadCN components** - Pre-styled, accessible components
