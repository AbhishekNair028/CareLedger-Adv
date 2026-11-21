# CareLedger

A health expense and insurance manager: track medical bills, insurance claims, prescriptions and appointments, set a monthly health budget, and see where your money goes.

**Live demo:** `https://YOUR-USERNAME.github.io/careledger/` (after enabling GitHub Pages, see below)

## Two versions in one repo
| | Folder | Backend | Data stored in |
|---|---|---|---|
| **Static site** (opens on GitHub Pages) | repo root | runs in the browser (JavaScript) | browser localStorage |
| **Full-stack version** | `server/` | Flask + JWT | SQLite database |

Both share the same UI and features.

## Features
- Register and login (salted SHA-256 password hashes in the browser version, hashed passwords + JWT in the Flask version)
- Admin and user roles; the admin sees an extra page with all accounts
- Full CRUD for bills, insurance claims, prescriptions and appointments, with search
- Dashboard: monthly spend, unpaid bills, money recovered from insurance, 6-month trend, spend by category, upcoming visits, refills due
- Monthly budget with progress meter, CSV export of bills

## Demo accounts
| Account | Email | Password |
|---|---|---|
| Patient | demo@careledger.dev | demo1234 |
| Admin | admin@careledger.dev | admin1234 |

## Publish on GitHub Pages
1. Push this repo to GitHub.
2. Go to **Settings > Pages**.
3. Under **Build and deployment**, choose **Deploy from a branch**, select `main` and `/ (root)`, then Save.
4. After a minute your site is live at `https://YOUR-USERNAME.github.io/REPO-NAME/`.

## Run the Flask version
```bash
cd server
pip install -r requirements.txt
python app.py          # http://localhost:5000
python -m unittest tests.test_api
```

## Note
The static version keeps everything in your own browser, so data is private to each device and is cleared if you wipe site data. It is meant as a demo; the Flask version is the real multi-user backend.
