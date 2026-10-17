/* My Diary — vanilla JavaScript frontend. No build tools required. */
'use strict';

const $ = (id) => document.getElementById(id);
const now = new Date();
const state = {
  selectedDate: localISO(now),
  viewYear: now.getFullYear(),
  viewMonth: now.getMonth(),
  viewMode: 'day', // day | all | completed
  filter: 'all',
  query: '',
  tasks: [],
  calendar: {},
  toastTimer: null,
};

const fmt = (date, opts) => new Intl.DateTimeFormat('en-US', opts).format(date);
const dateFromISO = (day) => new Date(`${day}T12:00:00`);
function localISO(date) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-');
}
function htmlEscape(text) {
  return String(text ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}
function shortDate(day) { return fmt(dateFromISO(day), { month: 'short', day: 'numeric' }); }
function todayISO() { return localISO(new Date()); }
function monthISO() { return `${state.viewYear}-${String(state.viewMonth + 1).padStart(2, '0')}`; }

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      headers: {'Content-Type': 'application/json'},
      ...options,
    });
  } catch (_) { throw new Error('Could not connect to the server. Please try again.'); }
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || 'Something went wrong.');
  return body;
}
function notify(message, error = false) {
  const element = $('toast');
  element.textContent = message;
  element.classList.toggle('error', error);
  element.hidden = false;
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => { element.hidden = true; }, 3300);
}

function drawCalendar() {
  const first = new Date(state.viewYear, state.viewMonth, 1);
  const offset = (first.getDay() + 6) % 7; // Monday-first grid.
  const base = new Date(state.viewYear, state.viewMonth, 1 - offset);
  $('calendarTitle').textContent = fmt(first, { month: 'long', year: 'numeric' });
  const grid = $('calendarGrid');
  grid.replaceChildren();
  // 42 slots keeps the panel from jumping between months.
  for (let i = 0; i < 42; i++) {
    const day = new Date(base.getFullYear(), base.getMonth(), base.getDate() + i);
    const value = localISO(day);
    const inMonth = day.getMonth() === state.viewMonth;
    const selected = state.viewMode === 'day' && value === state.selectedDate;
    const hasEvents = inMonth && Boolean(state.calendar[value]?.total);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = ['calendar-day', inMonth ? '' : 'outside', selected ? 'selected' : '', value === todayISO() ? 'today' : '', hasEvents ? 'has-events' : ''].filter(Boolean).join(' ');
    button.textContent = String(day.getDate());
    button.dataset.day = value;
    button.setAttribute('role', 'gridcell');
    button.setAttribute('aria-label', fmt(day, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }) + (hasEvents ? `, ${state.calendar[value].total} tasks` : ''));
    button.setAttribute('aria-selected', String(selected));
    if (value === todayISO()) button.setAttribute('aria-current', 'date');
    button.addEventListener('click', async () => {
      state.selectedDate = value;
      state.viewYear = day.getFullYear();
      state.viewMonth = day.getMonth();
      state.viewMode = 'day';
      state.filter = 'all';
      state.query = '';
      $('taskSearch').value = '';
      updateNav();
      await refreshCalendarAndTasks();
    });
    grid.appendChild(button);
  }
}
async function loadCalendar() {
  const result = await api(`/api/calendar?month=${monthISO()}`);
  state.calendar = result.days;
  drawCalendar();
}
function updateNav() {
  $('navToday').classList.toggle('active', state.viewMode === 'day');
  $('navAll').classList.toggle('active', state.viewMode === 'all');
  $('navCompleted').classList.toggle('active', state.viewMode === 'completed');
  $('taskListTitle').innerHTML = state.viewMode === 'completed' ? 'Completed<span class="accent-period">.</span>' : 'Your tasks<span class="accent-period">.</span>';
  $('selectedDateLabel').textContent = state.viewMode === 'day'
    ? fmt(dateFromISO(state.selectedDate), {weekday:'long', month:'long', day:'numeric', year:'numeric'})
    : state.viewMode === 'all' ? 'Every day, one organized list' : 'Everything you have accomplished';
  document.querySelectorAll('[data-filter]').forEach(button => {
    button.classList.toggle('selected', button.dataset.filter === state.filter);
    button.setAttribute('aria-pressed', String(button.dataset.filter === state.filter));
  });
  $('newDate').value = state.selectedDate;
}
function emptyTasks(message, subtext) {
  return `<div class="empty-state"><div class="empty-illustration"><svg class="icon"><use href="#i-sparkle"/></svg></div><strong>${message}</strong><p>${subtext}</p></div>`;
}
function drawTasks() {
  const list = $('tasksList');
  $('dayTaskCount').textContent = `${state.tasks.length} ${state.tasks.length === 1 ? 'TASK' : 'TASKS'}`;
  $('taskFooter').textContent = state.viewMode === 'day' ? 'For ' + shortDate(state.selectedDate) : `${state.tasks.length} tasks in this view`;
  if (!state.tasks.length) {
    list.innerHTML = emptyTasks(state.query ? 'No matches found.' : 'A little breathing room.', state.query ? 'Try a different search.' : 'Nothing here yet. Your next small win is a click away.');
    return;
  }
  list.innerHTML = state.tasks.map(task => `<article class="task-item ${task.completed ? 'is-done' : ''}" data-task-id="${task.id}">
    <button class="task-checkbox" type="button" role="checkbox" aria-checked="${task.completed}" aria-label="${task.completed ? 'Mark incomplete' : 'Mark complete'}: ${htmlEscape(task.title)}" data-action="toggle"><svg class="icon"><use href="#i-check"/></svg></button>
    <div class="task-info"><div class="task-name">${htmlEscape(task.title)}</div>${task.description ? `<div class="task-desc">${htmlEscape(task.description)}</div>` : ''}
      <div class="task-tags"><span class="priority-tag ${task.priority}">● ${task.priority} priority</span>${state.viewMode !== 'day' ? `<span class="priority-tag">${shortDate(task.due_date)}</span>` : ''}${task.overdue ? '<span class="overdue-tag">Overdue</span>' : ''}</div></div>
    <div class="task-menu"><button class="task-action" type="button" data-action="edit" aria-label="Edit ${htmlEscape(task.title)}" title="Edit task"><svg class="icon"><use href="#i-pencil"/></svg></button><button class="task-action danger" type="button" data-action="delete" aria-label="Delete ${htmlEscape(task.title)}" title="Delete task"><svg class="icon"><use href="#i-trash"/></svg></button></div>
  </article>`).join('');
}
async function loadTasks() {
  const params = new URLSearchParams();
  if (state.viewMode === 'day') params.set('date', state.selectedDate);
  if (state.viewMode === 'completed' || state.filter === 'completed') params.set('status', 'completed');
  else if (state.filter === 'active') params.set('status', 'active');
  if (state.query) params.set('q', state.query);
  const result = await api('/api/tasks?' + params.toString());
  state.tasks = result.tasks;
  drawTasks();
}
function setText(id, value) { $(id).textContent = value; }
function changeLabel(value, isLate = false) {
  if (value === null) return 'First year of tracking';
  if (value === 0) return '→ 0% vs last year';
  return `${value > 0 ? '↑' : '↓'} ${Math.abs(value)}% vs last year`;
}
function drawChart(months) {
  const max = Math.max(1, ...months);
  const names = ['J','F','M','A','M','J','J','A','S','O','N','D'];
  $('activityChart').innerHTML = months.map((count, i) => `<div class="chart-column" title="${count} completed in month ${i+1}"><div class="chart-bar ${count === 0 ? 'empty' : ''}" style="height:${Math.max(3, Math.round(count / max * 82))}px"></div><span class="chart-month">${names[i]}</span></div>`).join('');
  $('activityChart').setAttribute('aria-label', `Monthly completed tasks: ${months.map((v, i) => `${i+1}: ${v}`).join(', ')}`);
}
async function loadStats() {
  const s = await api('/api/stats');
  setText('totalCount', s.total);
  setText('completedCount', s.completed);
  setText('activeCount', s.active);
  setText('navTotal', s.total);
  setText('completedBarLabel', `${s.completed} of ${s.total}`);
  setText('onTimeBarLabel', `${s.on_time} of ${s.completed}`);
  setText('overdueBarLabel', `${s.overdue} of ${s.active}`);
  $('completedBar').style.width = s.completion_rate + '%';
  $('onTimeBar').style.width = s.on_time_rate + '%';
  $('overdueBar').style.width = s.overdue_rate + '%';
  setText('displayYear', s.year);
  setText('yearCompleted', s.completed_year);
  setText('yearLate', s.late_year);
  setText('yearCompletedChange', changeLabel(s.completed_change));
  setText('yearLateChange', changeLabel(s.late_change, true));
  drawChart(s.monthly_completed);
}
async function refreshCalendarAndTasks() {
  try { updateNav(); await Promise.all([loadCalendar(), loadTasks()]); }
  catch (err) { notify(err.message, true); }
}
async function refreshAll() {
  try { updateNav(); await Promise.all([loadStats(), loadCalendar(), loadTasks()]); }
  catch (err) { notify(err.message, true); }
}
async function createTask(event) {
  event.preventDefault();
  const button = $('addTaskButton');
  const data = {
    title: $('newTitle').value.trim(),
    due_date: $('newDate').value,
    priority: $('newPriority').value,
    description: $('newDescription').value.trim(),
  };
  if (!data.title || !data.due_date) { notify('Add a task name and due date.', true); return; }
  try {
    button.disabled = true;
    await api('/api/tasks', {method:'POST',body:JSON.stringify(data)});
    $('newTitle').value = '';
    $('newDescription').value = '';
    $('newPriority').value = 'medium';
    state.selectedDate = data.due_date;
    const date = dateFromISO(data.due_date);
    state.viewYear = date.getFullYear(); state.viewMonth = date.getMonth();
    state.viewMode = 'day'; state.filter = 'all'; state.query = '';
    $('taskSearch').value = '';
    await refreshAll();
    notify('Task created. You’ve got this!');
  } catch(err) { notify(err.message,true); }
  finally { button.disabled = false; }
}
async function taskAction(event) {
  const action = event.target.closest('[data-action]');
  if (!action) return;
  const item = action.closest('[data-task-id]');
  const task = state.tasks.find(t => t.id === Number(item?.dataset.taskId));
  if (!task) return;
  if (action.dataset.action === 'edit') {
    $('editId').value = task.id;
    $('editTaskTitle').value = task.title;
    $('editTaskDescription').value = task.description;
    $('editTaskDate').value = task.due_date;
    $('editTaskPriority').value = task.priority;
    $('editDialog').showModal();
    return;
  }
  if (action.dataset.action === 'delete' && !confirm(`Delete “${task.title}”? This cannot be undone.`)) return;
  try {
    action.disabled = true;
    if (action.dataset.action === 'toggle') {
      await api(`/api/tasks/${task.id}`, {method:'PATCH', body: JSON.stringify({completed:!task.completed})});
      notify(task.completed ? 'Task moved back to your list.' : 'A small victory. Task completed!');
    } else if (action.dataset.action === 'delete') {
      await api(`/api/tasks/${task.id}`, {method:'DELETE'});
      notify('Task removed.');
    }
    await refreshAll();
  } catch(err) { notify(err.message,true); action.disabled = false; }
}
async function saveEdit(event) {
  event.preventDefault();
  const id = $('editId').value;
  const data = {
    title: $('editTaskTitle').value.trim(),
    description: $('editTaskDescription').value.trim(),
    due_date: $('editTaskDate').value,
    priority: $('editTaskPriority').value,
  };
  try {
    await api(`/api/tasks/${id}`, {method:'PATCH',body:JSON.stringify(data)});
    $('editDialog').close();
    await refreshAll();
    notify('Changes saved.');
  } catch (err) { notify(err.message, true); }
}
function goToday() {
  state.selectedDate = todayISO();
  const today = new Date(); state.viewYear = today.getFullYear(); state.viewMonth = today.getMonth();
  state.viewMode = 'day'; state.filter = 'all'; state.query = '';
  $('taskSearch').value = '';
  refreshCalendarAndTasks();
}
function setup() {
  $('weekdayLabel').textContent = fmt(now, {weekday:'long'}).toUpperCase();
  $('newDate').value = state.selectedDate;
  $('createForm').addEventListener('submit', createTask);
  $('editForm').addEventListener('submit', saveEdit);
  $('tasksList').addEventListener('click', taskAction);
  $('closeDialog').addEventListener('click', () => $('editDialog').close());
  $('editDialog').addEventListener('click', event => { if (event.target === $('editDialog')) $('editDialog').close(); });
  $('prevMonth').addEventListener('click', async () => { const date = new Date(state.viewYear, state.viewMonth - 1, 1); state.viewYear = date.getFullYear(); state.viewMonth = date.getMonth(); try { await loadCalendar(); } catch(err) { notify(err.message,true); } });
  $('nextMonth').addEventListener('click', async () => { const date = new Date(state.viewYear, state.viewMonth + 1, 1); state.viewYear = date.getFullYear(); state.viewMonth = date.getMonth(); try { await loadCalendar(); } catch(err) { notify(err.message,true); } });
  $('jumpToday').addEventListener('click', goToday);
  $('navToday').addEventListener('click', goToday);
  $('navAll').addEventListener('click', () => { state.viewMode='all'; state.filter='all'; state.query=''; $('taskSearch').value=''; refreshCalendarAndTasks(); });
  $('navCompleted').addEventListener('click', () => { state.viewMode='completed'; state.filter='completed'; state.query=''; $('taskSearch').value=''; refreshCalendarAndTasks(); });
  document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
    state.filter = button.dataset.filter;
    if (state.viewMode === 'completed' && state.filter !== 'completed') state.viewMode = 'all';
    updateNav();
    loadTasks().catch(err => notify(err.message,true));
  }));
  $('searchToggle').addEventListener('click', () => {
    const wrap = $('searchWrap'); wrap.hidden = !wrap.hidden;
    $('searchToggle').setAttribute('aria-expanded', String(!wrap.hidden));
    if (!wrap.hidden) $('taskSearch').focus();
    if (wrap.hidden && state.query) { state.query = ''; $('taskSearch').value = ''; loadTasks().catch(err=>notify(err.message,true)); }
  });
  let searchTimer;
  $('taskSearch').addEventListener('input', event => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.query = event.target.value.trim(); loadTasks().catch(err => notify(err.message,true)); }, 180);
  });
  $('addTaskShortcut').addEventListener('click', () => { $('newDate').value = state.selectedDate; $('newTitle').focus(); $('createTitle').scrollIntoView({behavior:'smooth',block:'center'}); });
  refreshAll();
}

document.addEventListener('DOMContentLoaded', setup);
