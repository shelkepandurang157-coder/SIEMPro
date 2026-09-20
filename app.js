const api = {
  async get(url) {
    const res = await fetch(url);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || 'Request failed');
    }
    return res.json();
  },

  async post(url, data) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(body.detail || 'Request failed');
    }
    return body;
  },

  async patch(url, data) {
    const res = await fetch(url, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(body.detail || 'Request failed');
    }
    return body;
  },

  async delete(url) {
    const res = await fetch(url, { method: 'DELETE' });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(body.detail || 'Request failed');
    }
    return body;
  },
};

const appState = {
  user: null,
  dashboardData: null,
};

function applyRecordFilters() {
  if (!appState.dashboardData) return;

  const eventId = document.getElementById('overviewEventFilter')?.value || '';
  const competitionId = document.getElementById('overviewCompetitionFilter')?.value || '';
  const searchTerm = (document.getElementById('recordSearchInput')?.value || '').trim().toLowerCase();

  const matchesFilter = (item) => {
    const inEvent = !eventId || Number(item.event_id) === Number(eventId) || Number(item.event_id || item.eventId) === Number(eventId);
    const inCompetition = !competitionId || Number(item.competition_id) === Number(competitionId) || Number(item.competitionId) === Number(competitionId);
    if (!inEvent || !inCompetition) return false;

    if (!searchTerm) return true;

    const haystack = [
      item.name,
      item.email,
      item.phone,
      item.event_name,
      item.competition_name,
      item.preferred_role,
      item.assignment,
      item.skills,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();

    return haystack.includes(searchTerm);
  };

  const filteredRecentParticipants = (appState.dashboardData.recent_participants || []).filter(matchesFilter);
  const filteredRecentVolunteers = (appState.dashboardData.recent_volunteers || []).filter(matchesFilter);
  const filteredAllParticipants = (appState.dashboardData.all_participants || []).filter(matchesFilter);
  const filteredAllVolunteers = (appState.dashboardData.all_volunteers || []).filter(matchesFilter);

  renderRecords(
    'participantList',
    filteredRecentParticipants,
    (item) => `
      <div class="record-item">
        <strong>${item.name}</strong>
        <div>${item.event_name} • ${item.competition_name}</div>
        <div>${new Date(item.created_at).toLocaleString()}</div>
      </div>
    `,
  );

  renderRecords(
    'volunteerList',
    filteredRecentVolunteers,
    (item) => `
      <div class="record-item">
        <strong>${item.name}</strong>
        <div>${item.event_name} • ${item.competition_name}</div>
        <div>Assignment: ${item.assignment}</div>
      </div>
    `,
  );

  const chartData = {
    ...appState.dashboardData,
    event_breakdown: (appState.dashboardData.event_breakdown || []).filter((item) => {
      if (!eventId) return true;
      return Number(item.id) === Number(eventId);
    }),
  };

  renderEventBreakdown(chartData);

  const filteredData = {
    ...appState.dashboardData,
    recent_participants: filteredRecentParticipants,
    recent_volunteers: filteredRecentVolunteers,
    all_participants: filteredAllParticipants,
    all_volunteers: filteredAllVolunteers,
  };

  renderAllRecords(filteredData);
}

function renderStats(data) {
  const grid = document.getElementById('statsGrid');
  const cards = [
    ['Events', data.events],
    ['Competitions', data.competitions],
    ['Participants', data.participants],
    ['Volunteers', data.volunteers],
  ];

  grid.innerHTML = cards
    .map(
      ([label, value]) => `
        <div class="stat-card">
          <div class="label">${label}</div>
          <div class="value">${value}</div>
        </div>
      `,
    )
    .join('');
}

function renderRecords(containerId, items, formatter) {
  const container = document.getElementById(containerId);
  if (!items.length) {
    container.innerHTML = '<div class="empty-state">No records yet.</div>';
    return;
  }
  container.innerHTML = items.map(formatter).join('');
}

function renderEventBreakdown(data) {
  const container = document.getElementById('eventBreakdownChart');
  if (!data.event_breakdown || !data.event_breakdown.length) {
    container.innerHTML = '<div class="empty-state">No event data available yet.</div>';
    return;
  }

  const largestTotal = Math.max(
    ...data.event_breakdown.map((item) => Number(item.participants) + Number(item.volunteers) + Number(item.competitions)),
    1,
  );

  container.innerHTML = data.event_breakdown
    .map((item) => {
      const total = Number(item.participants) + Number(item.volunteers) + Number(item.competitions);
      const width = Math.max((total / largestTotal) * 100, 6);
      return `
        <div class="chart-row">
          <div class="chart-label">${item.name}</div>
          <div class="chart-track">
            <div class="chart-bar" style="width: ${width}%"></div>
          </div>
          <div class="chart-value">${total}</div>
        </div>
      `;
    })
    .join('');
}

function renderAllRecords(data) {
  const participantTable = document.getElementById('allParticipantsTable');
  const volunteerTable = document.getElementById('allVolunteersTable');

  participantTable.innerHTML = data.all_participants.length
    ? data.all_participants
        .map(
          (item) => `
            <tr>
              <td>${item.name}</td>
              <td>${item.email}</td>
              <td>${item.phone}</td>
              <td>${item.event_name}</td>
              <td>${item.competition_name}</td>
              <td>
                <button class="action-button edit" data-type="participant" data-id="${item.id}" type="button">Edit</button>
                <button class="action-button delete" data-type="participant" data-id="${item.id}" type="button">Delete</button>
              </td>
            </tr>
          `,
        )
        .join('')
    : '<tr><td colspan="6">No participants found.</td></tr>';

  volunteerTable.innerHTML = data.all_volunteers.length
    ? data.all_volunteers
        .map(
          (item) => `
            <tr>
              <td>${item.name}</td>
              <td>${item.email}</td>
              <td>${item.phone}</td>
              <td>${item.preferred_role}</td>
              <td>${item.assignment}</td>
              <td>${item.event_name}</td>
              <td>${item.competition_name}</td>
              <td>
                <button class="action-button edit" data-type="volunteer" data-id="${item.id}" type="button">Edit</button>
                <button class="action-button delete" data-type="volunteer" data-id="${item.id}" type="button">Delete</button>
              </td>
            </tr>
          `,
        )
        .join('')
    : '<tr><td colspan="8">No volunteers found.</td></tr>';

  document.querySelectorAll('.action-button.delete').forEach((button) => {
    button.addEventListener('click', async () => {
      const type = button.dataset.type;
      const id = button.dataset.id;
      try {
        await api.delete(`/api/${type}s/${id}`);
        loadDashboard();
        alert(`${type.charAt(0).toUpperCase() + type.slice(1)} deleted successfully.`);
      } catch (error) {
        alert(error.message);
      }
    });
  });

  document.querySelectorAll('.action-button.edit').forEach((button) => {
    button.addEventListener('click', async () => {
      const type = button.dataset.type;
      const id = button.dataset.id;
      const field = type === 'participant' ? 'name' : 'preferred_role';
      const currentValue = prompt(`Enter new ${field} for this ${type}:`, '');
      if (currentValue === null || currentValue.trim() === '') return;

      const payload = {};
      if (type === 'participant') {
        payload.name = currentValue.trim();
      } else {
        payload.preferred_role = currentValue.trim();
      }

      try {
        await api.patch(`/api/${type}s/${id}`, payload);
        loadDashboard();
        alert(`${type.charAt(0).toUpperCase() + type.slice(1)} updated successfully.`);
      } catch (error) {
        alert(error.message);
      }
    });
  });
}

function renderLoginState() {
  const badge = document.getElementById('loginBadge');
  badge.textContent = appState.user ? `Logged in as ${appState.user.username} (${appState.user.role})` : 'Not logged in';

  const deleteBtn = document.getElementById('deleteEventBtn');
  if (deleteBtn) {
    deleteBtn.disabled = !appState.user || appState.user.role !== 'admin';
    deleteBtn.style.opacity = deleteBtn.disabled ? '0.5' : '1';
  }

  const coordinatorOnlyFields = document.querySelectorAll('#competitionUpdateForm, #chatForm');
  coordinatorOnlyFields.forEach((field) => {
    const isEnabled = !!appState.user && (appState.user.role === 'admin' || appState.user.role === 'coordinator');
    field.style.opacity = isEnabled ? '1' : '0.6';
    field.querySelectorAll('input, textarea, select, button').forEach((control) => {
      control.disabled = !isEnabled;
    });
  });
}

function loadDashboard() {
  api
    .get('/api/dashboard')
    .then((data) => {
      appState.dashboardData = data;
      renderStats(data.stats);
      applyRecordFilters();
      renderEventBreakdown(data);
    })
    .catch((err) => {
      console.error(err);
      alert('Unable to load dashboard data.');
    });
}

async function exportReport(format, kind) {
  const eventId = document.getElementById('reportEventSelect').value;
  const competitionId = document.getElementById('reportCompetitionSelect').value;

  if (!eventId && !competitionId) {
    alert('Select an event or competition first.');
    return;
  }

  const params = new URLSearchParams();
  if (eventId) params.append('event_id', eventId);
  if (competitionId) params.append('competition_id', competitionId);

  const endpoint = kind === 'volunteer'
    ? (format === 'xlsx' ? '/api/reports/volunteers/xlsx' : '/api/reports/volunteers/csv')
    : (format === 'xlsx' ? '/api/reports/participants/xlsx' : '/api/reports/participants/csv');

  try {
    const response = await fetch(`${endpoint}?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Unable to export ${kind} ${format.toUpperCase()}.`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${kind}s_report.${format}`;
    link.click();
    URL.revokeObjectURL(url);
    alert(`${kind.charAt(0).toUpperCase() + kind.slice(1)} report exported successfully as ${format.toUpperCase()}.`);
  } catch (error) {
    alert(error.message);
  }
}

async function loadEvents() {
  const events = await api.get('/api/events');
  const selects = [
    document.getElementById('competitionEventSelect'),
    document.getElementById('participantEventSelect'),
    document.getElementById('volunteerEventSelect'),
    document.getElementById('chatEventSelect'),
    document.getElementById('eventDeleteSelect'),
    document.getElementById('reportEventSelect'),
    document.getElementById('updateCompetitionEventSelect'),
    document.getElementById('assignmentEventSelect'),
    document.getElementById('overviewEventFilter'),
  ];

  for (const select of selects) {
    if (!select) continue;
    select.innerHTML = '<option value="">Select event</option>' +
      events
        .map((event) => `<option value="${event.id}">${event.name}</option>`)
        .join('');
  }

  const overviewCompetitionFilter = document.getElementById('overviewCompetitionFilter');
  if (overviewCompetitionFilter) {
    overviewCompetitionFilter.innerHTML = '<option value="">Select competition</option>';
  }
}

async function loadCompetitionsForEvent(eventId, targetSelect) {
  if (!eventId) {
    targetSelect.innerHTML = '<option value="">Select competition</option>';
    return;
  }

  const competitions = await api.get(`/api/competitions?event_id=${eventId}`);
  targetSelect.innerHTML = '<option value="">Select competition</option>' +
    competitions
      .map((competition) => `<option value="${competition.id}">${competition.name} (${competition.capacity})</option>`)
      .join('');
}

async function loadVolunteerAssignments(eventId, competitionId) {
  const table = document.getElementById('volunteerAssignmentTable');
  if (!eventId || !competitionId) {
    table.innerHTML = '<tr><td colspan="5">Select an event and competition to manage assignments.</td></tr>';
    return;
  }

  try {
    const volunteers = await api.get(`/api/volunteers?competition_id=${competitionId}`);
    if (!volunteers.length) {
      table.innerHTML = '<tr><td colspan="5">No volunteers available for this competition.</td></tr>';
      return;
    }

    table.innerHTML = volunteers
      .map(
        (volunteer) => `
          <tr>
            <td>${volunteer.name}</td>
            <td>${volunteer.preferred_role}</td>
            <td>${volunteer.skills}</td>
            <td>
              <select data-volunteer-id="${volunteer.id}" class="assignment-select">
                <option value="Pending" ${volunteer.assignment === 'Pending' ? 'selected' : ''}>Pending</option>
                <option value="Assigned" ${volunteer.assignment === 'Assigned' ? 'selected' : ''}>Assigned</option>
                <option value="Rejected" ${volunteer.assignment === 'Rejected' ? 'selected' : ''}>Rejected</option>
              </select>
            </td>
            <td>
              <button type="button" class="save-assignment" data-volunteer-id="${volunteer.id}">Save</button>
            </td>
          </tr>
        `,
      )
      .join('');

    document.querySelectorAll('.save-assignment').forEach((button) => {
      button.addEventListener('click', async () => {
        const volunteerId = button.dataset.volunteerId;
        const select = document.querySelector(`.assignment-select[data-volunteer-id="${volunteerId}"]`);
        const assignment = select.value;

        try {
          await api.patch(`/api/volunteers/${volunteerId}`, { assignment });
          alert('Volunteer assignment updated successfully.');
          loadVolunteerAssignments(eventId, competitionId);
        } catch (error) {
          alert(error.message);
        }
      });
    });
  } catch (error) {
    table.innerHTML = '<tr><td colspan="5">Unable to load volunteer assignments.</td></tr>';
  }
}

async function loadCompetitionRules(eventId, competitionId) {
  if (!eventId || !competitionId) {
    document.getElementById('rulesBox').textContent = 'Select a competition to view its rules.';
    return;
  }

  try {
    const data = await api.get(`/api/competition-rules?event_id=${eventId}&competition_id=${competitionId}`);
    document.getElementById('rulesBox').textContent = `${data.competition_name}\n\n${data.rules}`;
  } catch (error) {
    document.getElementById('rulesBox').textContent = 'No rules available for this competition yet.';
  }
}

async function loadCompetitionMessages(eventId, competitionId) {
  const box = document.getElementById('chatBox');
  if (!eventId || !competitionId) {
    box.innerHTML = '<div class="empty-state">Select a competition to see messages.</div>';
    return;
  }

  try {
    const messages = await api.get(`/api/competition-messages?event_id=${eventId}&competition_id=${competitionId}`);
    if (!messages.length) {
      box.innerHTML = '<div class="empty-state">No messages yet. The coordinator can share rules and updates here.</div>';
      return;
    }
    box.innerHTML = messages
      .map(
        (message) => `
          <div class="chat-message ${message.sender === 'coordinator' ? 'coordinator' : 'participant'}">
            <strong>${message.sender_name}</strong>
            <div>${message.message}</div>
            <small>${new Date(message.created_at).toLocaleString()}</small>
          </div>
        `,
      )
      .join('');
  } catch (error) {
    box.innerHTML = '<div class="empty-state">Unable to load messages.</div>';
  }
}

function registerFormHandlers() {
  document.getElementById('loginForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;

    try {
      const user = await api.post('/api/login', { username, password });
      appState.user = { username: user.username, role: user.role };
      renderLoginState();
      document.getElementById('loginForm').reset();
      alert('Login successful.');
    } catch (error) {
      alert(error.message);
    }
  });

  document.getElementById('logoutBtn').addEventListener('click', () => {
    appState.user = null;
    renderLoginState();
    alert('Logged out successfully.');
  });

  document.getElementById('eventForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form).entries());
    try {
      await api.post('/api/events', data);
      form.reset();
      await loadEvents();
      loadDashboard();
      alert('Event created successfully.');
    } catch (err) {
      alert(err.message);
    }
  });

  document.getElementById('deleteEventBtn').addEventListener('click', async () => {
    const eventId = document.getElementById('eventDeleteSelect').value;
    if (!eventId) {
      alert('Please select an event to delete.');
      return;
    }

    if (!appState.user || appState.user.role !== 'admin') {
      alert('Only admin can delete events.');
      return;
    }

    try {
      await api.delete(`/api/events/${eventId}`);
      await loadEvents();
      loadDashboard();
      alert('Event deleted successfully.');
    } catch (error) {
      alert(error.message);
    }
  });

  document.getElementById('competitionForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form).entries());
    try {
      await api.post('/api/competitions', {
        ...data,
        capacity: Number(data.capacity),
      });
      form.reset();
      loadDashboard();
      alert('Competition created successfully.');
    } catch (err) {
      alert(err.message);
    }
  });

  document.getElementById('updateCompetitionEventSelect').addEventListener('change', async (event) => {
    const eventId = event.target.value;
    const target = document.getElementById('updateCompetitionSelect');
    await loadCompetitionsForEvent(eventId, target);
  });

  document.getElementById('reportEventSelect').addEventListener('change', async (event) => {
    const eventId = event.target.value;
    const reportCompetitionSelect = document.getElementById('reportCompetitionSelect');
    await loadCompetitionsForEvent(eventId, reportCompetitionSelect);
  });

  document.getElementById('reportCompetitionSelect').addEventListener('change', () => {
    const eventId = document.getElementById('reportEventSelect').value;
    const competitionId = document.getElementById('reportCompetitionSelect').value;
    if (!eventId && !competitionId) {
      return;
    }
  });

  document.getElementById('overviewEventFilter').addEventListener('change', async (event) => {
    const eventId = event.target.value;
    const competitionFilter = document.getElementById('overviewCompetitionFilter');
    await loadCompetitionsForEvent(eventId, competitionFilter);
    applyRecordFilters();
  });

  document.getElementById('overviewCompetitionFilter').addEventListener('change', () => {
    applyRecordFilters();
  });

  document.getElementById('clearOverviewFilter').addEventListener('click', () => {
    document.getElementById('overviewEventFilter').value = '';
    document.getElementById('overviewCompetitionFilter').innerHTML = '<option value="">Select competition</option>';
    applyRecordFilters();
  });

  document.getElementById('recordSearchInput').addEventListener('input', () => {
    applyRecordFilters();
  });

  document.getElementById('competitionUpdateForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const eventId = document.getElementById('updateCompetitionEventSelect').value;
    const competitionId = document.getElementById('updateCompetitionSelect').value;
    const name = document.getElementById('updateCompetitionName').value.trim();
    const capacity = document.getElementById('updateCompetitionCapacity').value.trim();
    const rules = document.getElementById('updateCompetitionRules').value.trim();

    if (!eventId || !competitionId) {
      alert('Select an event and competition before updating.');
      return;
    }

    try {
      const payload = {};
      if (name) payload.name = name;
      if (capacity) payload.capacity = Number(capacity);
      if (rules) payload.rules = rules;
      if (Object.keys(payload).length === 0) {
        alert('Enter at least one field to update.');
        return;
      }

      const response = await api.patch(`/api/competitions/${competitionId}`, payload);
      document.getElementById('competitionUpdateForm').reset();
      loadDashboard();
      alert('Competition updated successfully.');
    } catch (error) {
      alert(error.message);
    }
  });

  document.getElementById('exportParticipantsCsv').addEventListener('click', () => {
    exportReport('csv', 'participant');
  });

  document.getElementById('exportParticipantsXlsx').addEventListener('click', () => {
    exportReport('xlsx', 'participant');
  });

  document.getElementById('exportVolunteersCsv').addEventListener('click', () => {
    exportReport('csv', 'volunteer');
  });

  document.getElementById('exportVolunteersXlsx').addEventListener('click', () => {
    exportReport('xlsx', 'volunteer');
  });

  document.getElementById('exportCombinedXlsx').addEventListener('click', async () => {
    const eventId = document.getElementById('reportEventSelect').value;
    const competitionId = document.getElementById('reportCompetitionSelect').value;
    if (!eventId && !competitionId) {
      alert('Select an event or competition first.');
      return;
    }

    const params = new URLSearchParams();
    if (eventId) params.append('event_id', eventId);
    if (competitionId) params.append('competition_id', competitionId);

    try {
      const response = await fetch(`/api/reports/combined/xlsx?${params.toString()}`);
      if (!response.ok) {
        throw new Error('Unable to export combined XLSX.');
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'combined_report.xlsx';
      link.click();
      URL.revokeObjectURL(url);
      alert('Combined report exported successfully.');
    } catch (error) {
      alert(error.message);
    }
  });

  document.getElementById('participantForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form).entries());
    try {
      await api.post('/api/participants', {
        ...data,
        competition_id: Number(data.competition_id),
        event_id: Number(data.event_id),
      });
      form.reset();
      loadDashboard();
      alert('Participant registered successfully.');
    } catch (err) {
      alert(err.message);
    }
  });

  document.getElementById('volunteerForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form).entries());
    try {
      await api.post('/api/volunteers', {
        ...data,
        competition_id: Number(data.competition_id),
        event_id: Number(data.event_id),
      });
      form.reset();
      loadDashboard();
      alert('Volunteer application submitted.');
    } catch (err) {
      alert(err.message);
    }
  });

  document.getElementById('competitionEventSelect').addEventListener('change', (event) => {
    // No filtered competition list is needed here, so just keep the event selection in sync.
    const target = document.getElementById('competitionCompetitionSelect');
    target.style.display = 'none';
    target.innerHTML = '<option value="">Select competition</option>';
  });

  document.getElementById('participantEventSelect').addEventListener('change', (event) => {
    loadCompetitionsForEvent(event.target.value, document.getElementById('participantCompetitionSelect'));
  });

  document.getElementById('volunteerEventSelect').addEventListener('change', (event) => {
    loadCompetitionsForEvent(event.target.value, document.getElementById('volunteerCompetitionSelect'));
  });

  document.getElementById('assignmentEventSelect').addEventListener('change', async (event) => {
    const eventId = event.target.value;
    const target = document.getElementById('assignmentCompetitionSelect');
    await loadCompetitionsForEvent(eventId, target);
    if (!eventId) {
      document.getElementById('volunteerAssignmentTable').innerHTML = '<tr><td colspan="5">Select an event and competition to manage assignments.</td></tr>';
    }
  });

  document.getElementById('assignmentCompetitionSelect').addEventListener('change', (event) => {
    const eventId = document.getElementById('assignmentEventSelect').value;
    loadVolunteerAssignments(eventId, event.target.value);
  });

  document.getElementById('chatEventSelect').addEventListener('change', (event) => {
    loadCompetitionsForEvent(event.target.value, document.getElementById('chatCompetitionSelect'));
  });

  document.getElementById('chatCompetitionSelect').addEventListener('change', (event) => {
    const eventId = document.getElementById('chatEventSelect').value;
    loadCompetitionRules(eventId, event.target.value);
    loadCompetitionMessages(eventId, event.target.value);
  });

  document.getElementById('chatForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!appState.user || (appState.user.role !== 'admin' && appState.user.role !== 'coordinator')) {
      alert('Only admin and coordinator users can post messages.');
      return;
    }

    const eventId = document.getElementById('chatEventSelect').value;
    const competitionId = document.getElementById('chatCompetitionSelect').value;
    const senderRole = document.getElementById('chatSenderRole').value;
    const senderName = document.getElementById('chatSenderName').value.trim();
    const message = document.getElementById('chatMessage').value.trim();

    if (!eventId || !competitionId || !senderName || !message) {
      alert('Please select a competition and fill in your name and message.');
      return;
    }

    try {
      await api.post('/api/competition-messages', {
        event_id: Number(eventId),
        competition_id: Number(competitionId),
        sender: senderRole,
        sender_name: senderName,
        message,
      });
      document.getElementById('chatMessage').value = '';
      loadCompetitionMessages(eventId, competitionId);
    } catch (error) {
      alert(error.message);
    }
  });

  document.getElementById('refreshData').addEventListener('click', () => {
    loadDashboard();
    loadEvents();
  });
}

async function initialize() {
  renderLoginState();
  await loadEvents();
  registerFormHandlers();
  loadDashboard();
  loadCompetitionMessages('', '');
}

initialize();
