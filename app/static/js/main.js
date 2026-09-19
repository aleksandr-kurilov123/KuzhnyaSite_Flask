import * as bootstrap from 'bootstrap';

document.getElementById('tournament-selector').addEventListener('change', function() {
    var tournamentId = this.value;
    if (tournamentId) {
        fetch(`/api/tournament/${tournamentId}`)
            .then(response => response.json())
            .then(data => {
                var tournamentInfo = document.getElementById('tournament-info');
                var upcomingMatchesList = document.getElementById('upcoming-matches-list');
                var participantsList = document.getElementById('participants-list');

                upcomingMatchesList.innerHTML = '';
                participantsList.innerHTML = '';

                data.upcoming_matches.forEach(match => {
                    var li = document.createElement('li');
                    li.className = 'd-flex gap-1';
                    li.innerHTML = `<div class="match-name">Round ${match.round}: ${match.team_a} vs ${match.team_b}</div> <div class="match-time">${match.scheduled_at}</div>`;
                    upcomingMatchesList.appendChild(li);
                });

                data.participants.forEach(team => {
                    var li = document.createElement('li');
                    li.className = 'd-flex';
                    li.innerHTML = `<div class="team-name">${team.team_name}</div>`;
                    participantsList.appendChild(li);
                });

                tournamentInfo.style.display = 'block';
            });
    } else {
        document.getElementById('tournament-info').style.display = 'none';
    }
});
