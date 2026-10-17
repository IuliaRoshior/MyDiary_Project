# My Diary ✳

A personal task dashboard inspired by the provided layout, redesigned as a complete responsive web application.

**Stack:** Python 3.10+, Python standard-library HTTP server, SQLite, HTML5, CSS3, vanilla JavaScript. No pip dependencies, frontend build tools, external database or API keys needed.

## Features

- Create tasks with names, due dates, priorities and optional notes.
- Check off tasks, edit them, or delete them (confirmation required).
- View one day on a Monday-first interactive calendar, or switch to all/completed tasks.
- Navigate months, jump to today and see tiny dots on dates with tasks.
- Filter to all/to-do/done tasks; search by task title or description.
- Live totals, completion rate, on-time rate, overdue rate, annual insights and monthly activity chart.
- SQLite persistence. User input is validated in the API, SQL is parameterized, and task text is escaped in HTML.
- Responsive design for desktop, tablet and phone, keyboard accessible controls and labeled actions.

## Quick start (Windows)

```powershell
cd MyDiary_Project
py -m venv .venv
.venv\Scripts\activate
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

## Quick start (macOS / Linux)

```bash
cd MyDiary_Project
python3 -m venv .venv
source .venv/bin/activate
python app.py
```

Open **http://127.0.0.1:5000**.

The app generates a sample set of tasks on first run, relative to today's date. These are editable demo records, not fabricated analytics. All future changes persist in `mydiary.sqlite3` and the file is ignored by Git. To start with an empty database use `python app.py --empty` on first run (or delete the `.sqlite3` file and restart with `--empty`).

Set `MYDIARY_DB` to choose another SQLite file, `PORT` to override port 5000. You can also run `python app.py --port 5050`.

## API

| Method | URL | Function |
|:--|:--|:--|
| `GET` | `/` | Dashboard HTML |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/tasks?date=2026-10-18&status=active&q=design` | List/filter/search tasks |
| `POST` | `/api/tasks` | Create task |
| `PATCH` | `/api/tasks/1` | Update fields or completion status |
| `DELETE` | `/api/tasks/1` | Delete task |
| `GET` | `/api/stats` | Computed global metrics |
| `GET` | `/api/calendar?month=2026-10` | Task totals per calendar date |

Create example:

```json
{"title":"Finish the case study","due_date":"2026-10-20","priority":"high","description":"Review mobile screens"}
```

For PATCH: send any subset of `title`, `description`, `due_date`, `priority`, `completed` (boolean). Validation errors produce `400 {"error":"..."}` and missing tasks `404`.

## Metrics explained

- **Completed tasks**: count of completed / all tasks.
- **Finished on time**: completed with `completed_at` date on/before due date / completed tasks.
- **Currently overdue**: open tasks whose due date has passed / all open tasks.
- **Completed this year**: completion timestamp occurs in the current year.
- **Finished late this year**: completion timestamp is later than the due date and occurs this year.
- **Year-over-year change**: only displayed when the previous year has at least one record; otherwise labeled *First year of tracking*.

All dates use the **server's local date** for lateness and the **browser's local date** for the initial selection. For a single-user local app these should match. The application has no login or user accounts and is intended for local/self-hosted usage, not public multi-tenant deployment.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Folders

```text
MyDiary_Project/
├── app.py                 # Python HTTP routes, validation, calculations, SQLite
├── requirements.txt
├── templates/
│   └── index.html         # Semantic dashboard + edit modal
├── static/
│   ├── favicon.svg
│   ├── css/styles.css      # Full responsive design system
│   └── js/app.js           # Calendar, tasks, API and chart UI
├── tests/test_app.py      # API tests
└── design/                # Screenshots and design reference
```

## Design guide

Colors: Navy `#25374A`, Blue `#3B86B3`, Mint `#4CA88B`, Warm orange `#DB8D77`, Sidebar `#EEF2ED`, Paper `#FFFEFA`. Typeface pairing: Georgia for expressive headings, DM Sans and Manrope for interface text. Main desktop layout: navigation & quick-add sidebar / insights & progress / calendar & task list.

The Figma Design document is at https://www.figma.com/design/0vRhFU2eazqTAlR0LOYsiQ . Use the bundled `figma-plugin/` importer to populate editable native desktop/mobile layers (remote Figma layer editing was blocked by the Starter plan limit). See `figma-plugin/README.md`.

## One-click launch

On Windows double-click `run_windows.bat`; on macOS/Linux run `./run_mac_linux.sh`. The Python standard library is sufficient; `requirements.txt` is intentionally empty.
