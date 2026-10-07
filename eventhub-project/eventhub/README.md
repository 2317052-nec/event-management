# EventHub (Flask + SQLite)

    pip install -r requirements.txt
    python app.py          # open http://localhost:5000

The database (`eventhub.db`) is created and seeded on first run.
Demo accounts (password `eventhub123`): admin@eventhub.in, organizer@eventhub.in, user@eventhub.in

## API
| Method | Path | Who |
|---|---|---|
| POST | /api/auth/signup, /api/auth/login | anyone (returns Bearer token) |
| GET | /api/events?q=&category=&city=&type=&price=Free|Paid&sort=&available=1 | anyone |
| GET | /api/events/<id> | anyone |
| POST | /api/events/<id>/register | anyone (validates email, phone, duplicates, seats, ended events, payment) |
| GET | /api/registrations | logged in |
| DELETE | /api/registrations/<id> | owner / organizer |
| POST | /api/events | organizer (goes to `pending`) |
| GET, PATCH | /api/admin/events | admin approves / rejects |
| GET | /api/events/<id>/participants | organizer |
| POST | /api/checkin `{"id": "EH-26-12345"}` | organizer (blocks duplicates) |
| GET | /api/organizer/stats | organizer |
| POST, DELETE | /api/saved/<id> | logged in |
| GET | /api/recommendations?interests=ai,python | anyone |
| POST | /api/ai `{"question": "..."}` | anyone |

Payments are simulated: any `payment.method` is accepted. Replace with Razorpay/Stripe before real use.
The frontend (`static/index.html`) loads events from the API and posts registrations to it; login, dashboards and check-in screens still use demo data in the page.
