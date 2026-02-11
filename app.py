import datetime
import os
import io
import csv
import random
from flask import Flask, render_template_string, request, make_response, redirect
from flask_sqlalchemy import SQLAlchemy
import pyrankvote
from pyrankvote import Candidate, Ballot

app = Flask(__name__)

# --- DATABASE CONFIG ---
uri = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.String(100))
    ranks = db.Column(db.Text) # This MUST be named 'ranks' to match the functions below

with app.app_context():
    db.create_all()

# --- THE OFFICIAL LIST ---
RAW_OPTIONS = [
    "STAMP - Shoreside Targeted Maintenance Process", "SHMRCC - Shamrocks", 
    "KRAKEN - Kinetic Repair", "SHARK - Shore Habitability", 
    "CEU-REACT - Civil Engineering", "HAMR - Habitability and Maintenance",
    "NEPTUNE - Naval Engineering", "BADGER - Base Asset Damage",
    "ANCHOR Team - Ashore Nationwide", "SIRC - Shoreside Infrastructure",
    "ANCHOR - Advanced Network", "BOLT - Base Operations",
    "DEU - Deployable Engineering", "PIER - Program for Integrated Engineering",
    "SEAWALL - Sustained Engineering", "SHORE - Shoreline Heavy Operations",
    "SURGE - Shoreline Utility", "SWIFT - Shoreline Works",
    "FRD - Facilities Response", "HMR (HAMMER) - Habitability Maintenance",
    "RENC (WRENCH) - Rapid Engineering", "SAW - Structural Assessment",
    "HLMT (HELMET) - Habitability Logistics", "PLIERS - Precision Logistics",
    "CEA OTTERS - Coast Guard Enlisted", "ANCHOR - Advanced Naval Construction",
    "BEACON - Base Engineering", "AEGIS - Advanced Engineering",
    "FORGE - Facility Operations", "RAMPART - Rapid Asset Maintenance"
]
OPTIONS = sorted(RAW_OPTIONS)

# (I'm keeping your HTML_TEMPLATE exactly as you had it, just ensuring the logic below matches it)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Unit Naming Vote</title>
    <script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif; padding: 0; margin: 0; background: #f3f2f1; color: #323130; }
        .container { max-width: 800px; margin: 20px auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding-bottom: 120px; }
        .results-header { display: flex; align-items: center; gap: 10px; margin-bottom: 5px; }
        .pulse-dot { height: 12px; width: 12px; background-color: #d13438; border-radius: 50%; display: inline-block; animation: pulse-red 2s infinite; }
        @keyframes pulse-red { 0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(209, 52, 56, 0.7); } 70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(209, 52, 56, 0); } 100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(209, 52, 56, 0); } }
        .winner-card { display: flex; justify-content: space-between; align-items: center; padding: 15px; margin-bottom: 10px; border-radius: 6px; border: 1px solid #e1dfdd; }
        .vote-count { font-weight: bold; color: #464EB8; min-width: 80px; text-align: right; }
        .search-box { width: 100%; padding: 12px; margin-bottom: 15px; border: 2px solid #464EB8; border-radius: 4px; box-sizing: border-box; font-size: 16px; }
        .sortable-item { background: #fff; border: 1px solid #e1dfdd; margin: 5px 0; padding: 12px; border-radius: 4px; cursor: grab; font-size: 13px; display: flex; align-items: center; }
        .rank-number { font-weight: bold; margin-right: 15px; color: #464EB8; font-size: 16px; min-width: 35px; }
        .button-container { position: fixed; bottom: 0; left: 0; right: 0; background: white; padding: 20px; border-top: 1px solid #e1dfdd; text-align: center; z-index: 100; }
        .submit-btn { background: #464EB8; color: white; border: none; padding: 15px; width: 100%; max-width: 760px; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 1.1em; }
        pre { background: #323130; color: #00ff00; padding: 15px; font-size: 11px; border-radius: 4px; overflow-x: auto; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        {% if already_voted %}
            <div class="results-header">
                <span class="pulse-dot"></span><h2 style="margin: 0;">Grand Standings</h2>
            </div>
            <p style="color: #666; font-size: 0.9em; margin-bottom: 20px;"><strong>AS OF:</strong> {{ timestamp }}</p>
            <div class="results-area">
                {{ winner|safe }}
                <p style="font-size: 0.8em; color: #888; margin-top: 15px;">Total Ballots Cast: {{ total_votes }}</p>
                <hr><pre>{{ detailed_results }}</pre>
            </div>
            <div style="text-align: center; margin-top: 30px; display: flex; flex-direction: column; gap: 15px; align-items: center;">
                <div style="display: flex; gap: 10px;">
                    <a href="/reset_my_vote" style="color: #464EB8; text-decoration: none; font-size: 0.9em; font-weight: bold; border: 1px solid #464EB8; padding: 10px 20px; border-radius: 4px;">🔄 Change My Vote</a>
                    <a href="/download_votes" style="color: #107c10; text-decoration: none; font-size: 0.9em; font-weight: bold; border: 1px solid #107c10; padding: 10px 20px; border-radius: 4px;">📥 Download CSV</a>
                </div>
            </div>
        {% else %}
            <h2>Unit Naming Vote</h2>
            <p>Drag your favorite names to the top. Your #1 choice should be at the very top of the list.</p>
            <input type="text" class="search-box" id="search" placeholder="Search names..." onkeyup="filterList()">
            <div id="sortable-list">
                {% for option in options %}
                <div class="sortable-item" data-id="{{ option }}"><span class="rank-number"></span> {{ option }}</div>
                {% endfor %}
            </div>
            <form id="voteForm" method="POST" action="/vote">
                <input type="hidden" name="final_rank" id="final_rank">
                <div class="button-container"><button type="submit" class="submit-btn" onclick="submitVote()">Submit My Ranked Ballot</button></div>
            </form>
        {% endif %}
    </div>
    <script>
        var el = document.getElementById('sortable-list');
        function updateNumbers() {
            var items = el.getElementsByClassName('rank-number');
            var count = 1;
            for (var i = 0; i < items.length; i++) {
                if (items[i].parentNode.style.display !== "none") { items[i].innerText = count + "."; count++; }
            }
        }
        var sortable = Sortable.create(el, { animation: 150, onEnd: updateNumbers });
        updateNumbers();
        function filterList() {
            var filter = document.getElementById('search').value.toUpperCase();
            var items = el.getElementsByClassName('sortable-item');
            for (var i = 0; i < items.length; i++) {
                var text = items[i].innerText;
                items[i].style.display = text.toUpperCase().indexOf(filter) > -1 ? "" : "none";
            }
            updateNumbers();
        }
        function submitVote() {
            var order = sortable.toArray();
            document.getElementById('final_rank').value = order.join('||');
        }
    </script>
</body>
</html>
"""

def get_election_data():
    all_votes = Vote.query.all()
    if not all_votes:
        return "Waiting for first vote...", "No rounds calculated yet.", 0, "No votes yet"
    
    ballots = []
    latest_time = "Unknown"
    for v in all_votes:
        rank_list = v.ranks.split('||')
        ballots.append(Ballot(ranked_candidates=[Candidate(c) for c in rank_list]))
        latest_time = v.timestamp
    
    candidates = [Candidate(o) for o in OPTIONS]
    # Changed to Instant Runoff for naming (Standard 1-winner election)
    election = pyrankvote.instant_runoff_voting(candidates, ballots)
    winners = election.get_winners()
    
    result_html = '<div style="display: flex; flex-direction: column; gap: 10px; margin-top: 15px;">'
    if winners:
        for i, winner in enumerate(winners):
            style = "background: #fff9e6; border: 2px solid #ffcc00;" if i == 0 else "background: white; border: 1px solid #e1dfdd;"
            label = "🏆 CURRENT LEADER" if i == 0 else f"Finalist #{i+1}"
            result_html += f'<div class="winner-card" style="{style}"><span><strong>{label}:</strong> {winner}</span></div>'
    result_html += '</div>'
        
    return result_html, str(election), len(all_votes), latest_time

@app.route('/')
def index():
    voted = request.cookies.get('voted')
    
    # We need to run the math even for the index page 
    # so we can show the current "Grand Standings" to people who already voted.
    winner, details, total, ts = get_election_data()
    
    # Use the TEMPLATE you built, not the simplified string!
    return render_template_string(
        HTML_TEMPLATE, 
        already_voted=voted, 
        options=OPTIONS, 
        winner=winner, 
        detailed_results=details, 
        total_votes=total, 
        timestamp=ts
    )

@app.route('/vote', methods=['POST'])
def vote():
    data = request.form.get('final_rank')
    if data:
        now = datetime.datetime.now().strftime("%A, %b %d, %Y | %I:%M %p")
        db.session.add(Vote(timestamp=now, ranks=data))
        db.session.commit()
    res = make_response(redirect('/'))
    res.set_cookie('voted', 'true', max_age=60*60*24*7)
    return res

@app.route('/download_votes')
def download_votes():
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Ranks', 'Time'])
    for v in Vote.query.all(): cw.writerow([v.id, v.ranks, v.timestamp])
    res = make_response(si.getvalue())
    res.headers["Content-Disposition"] = "attachment; filename=results.csv"
    res.headers["Content-type"] = "text/csv"
    return res

@app.route('/reset_my_vote')
def reset_my_vote():
    res = make_response(redirect('/'))
    res.set_cookie('voted', '', expires=0)
    return res

@app.route('/results_admin_view')
def results_admin_view():
    all_votes = Vote.query.all()
    if not all_votes: 
        return "<h1>The Vault is Empty</h1><p>No votes yet.</p><br><a href='/'>Back to Voting</a>"
    
    candidates = [Candidate(o) for o in OPTIONS]
    ballots = [Ballot(ranked_candidates=[Candidate(c.strip()) for c in v.ranks.split('||')]) for v in all_votes]
    election = pyrankvote.instant_runoff_voting(candidates, ballots)
    
    return f"""
    <body style="font-family: sans-serif; padding: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h1>Ranked Choice Results (Admin)</h1>
            <a href='/download_votes' style="background: #107c10; color: white; padding: 10px; text-decoration: none; border-radius: 4px;">📥 Download CSV</a>
        </div>
        
        <p>Total Ballots: <b>{len(all_votes)}</b></p>
        <pre style="background: #323130; color: #00ff00; padding: 15px; border-radius: 5px; overflow-x: auto;">{election}</pre>
        
        <hr style="margin: 30px 0;">
        <div style="display: flex; gap: 20px; align-items: center;">
            <a href='/'>🏠 Back to Voting</a>
            <a href='/admin_test_data' style="color: #464EB8;">🧪 Add 3 Test Votes</a>
            <a href='/wipe_the_vault_2026_CONFIRM' 
               onclick="return confirm('WARNING: This will permanently delete EVERY vote. Are you sure?')" 
               style="color: #d13438; font-size: 0.8em; border: 1px solid #d13438; padding: 5px; border-radius: 4px; text-decoration: none;">
               ⚠️ Wipe Database (Monday Morning Only)
            </a>
        </div>
    </body>
    """

@app.route('/results_2026_secret')
def secret_results_view():
    # This just points to the admin view so you don't have to maintain two pages
    return results_admin_view()

@app.route('/admin_test_data')
def admin_test_data():
    # Adds 3 random ballots for testing
    for _ in range(3):
        # We sample the full OPTIONS list to simulate a real ballot
        random_ranks = random.sample(OPTIONS, len(OPTIONS))
        db.session.add(Vote(timestamp=str(datetime.datetime.now()), ranks='||'.join(random_ranks)))
    db.session.commit()
    # This takes you straight to the results so you can see the math in action
    return redirect('/results_admin_view')

@app.route('/wipe_the_vault_2026_CONFIRM')
def wipe_database():
    try:
        # This deletes all rows in the Vote table
        db.session.query(Vote).delete()
        db.session.commit()
        return "<h1>Vault Wiped Clean</h1><p>The database is now at 0 votes. <a href='/'>Back to Home</a></p>"
    except Exception as e:
        db.session.rollback()
        return f"Error wiping database: {str(e)}"

if __name__ == '__main__':
    app.run()