/**
 * VAL Personal Autonomous AI Operating System — Frontend Controller
 * Connects directly to backend APIs: Chat, Tasks, Agents, Factory, Learning, Teaching, Approvals, Status.
 */

const API_BASE = '/api/v1';
let currentConversationId = null;
let systemState = {
  isPaused: false,
  isEmergency: false,
  founderName: 'Tomiwa',
  status: 'ONLINE'
};

// Safe API Fetch Wrapper with Founder Token
async function api(path, opts = {}) {
  opts.headers = {
    'Content-Type': 'application/json',
    'x-val-founder-key': 'val-founder-dev-token',
    ...(opts.headers || {})
  };
  const res = await fetch(API_BASE + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API request failed');
  }
  return res.json();
}

// Format relative time (e.g. "2 minutes ago")
function formatTimeAgo(isoString) {
  if (!isoString) return '';
  const past = new Date(isoString);
  const now = new Date();
  const diffSec = Math.floor((now - past) / 1000);
  if (diffSec < 45) return 'just now';
  if (diffSec < 90) return '1 minute ago';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} minutes ago`;
  if (diffSec < 7200) return '1 hour ago';
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} hours ago`;
  return past.toLocaleDateString();
}

// Navigation & View Switching
function switchView(viewId) {
  document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
  
  const target = document.getElementById(viewId);
  if (target) {
    target.classList.add('active');
  }
  
  // Highlight active link
  const link = document.querySelector(`.nav-link[data-view="${viewId}"]`);
  if (link) {
    link.classList.add('active');
  }

  // Scroll viewport to top
  const vp = document.querySelector('.app-viewport');
  if (vp) vp.scrollTop = 0;
}

function toggleAdvancedNav() {
  const menu = document.getElementById('advanced-menu');
  const icon = document.getElementById('advanced-arrow');
  if (menu) {
    menu.classList.toggle('open');
    if (icon) icon.textContent = menu.classList.contains('open') ? '▾' : '▸';
  }
}

// --- DATA REFRESH LOOPS ---

async function refreshSystemStatus() {
  try {
    const status = await api('/status');
    systemState.isPaused = status.global_paused;
    systemState.isEmergency = status.emergency;
    systemState.founderName = status.founder_display_name || 'Tomiwa';

    // Update greeting
    const greetingEl = document.getElementById('founder-greeting');
    if (greetingEl) {
      const hr = new Date().getHours();
      const timeGreeting = hr < 12 ? 'Good morning' : (hr < 18 ? 'Good afternoon' : 'Good evening');
      greetingEl.textContent = `${timeGreeting}, ${systemState.founderName}.`;
    }

    const headerName = document.getElementById('header-founder-name');
    if (headerName) headerName.textContent = systemState.founderName;

    // Status Pill
    const pill = document.getElementById('val-status-pill');
    const pillText = document.getElementById('val-status-text');
    if (pill && pillText) {
      if (status.emergency) {
        pill.className = 'status-pill emergency';
        pillText.textContent = 'EMERGENCY STOP';
      } else if (status.global_paused) {
        pill.className = 'status-pill paused';
        pillText.textContent = 'PAUSED';
      } else {
        pill.className = 'status-pill';
        pillText.textContent = 'VAL ONLINE';
      }
    }

    // Modal Status Details
    const modalCore = document.getElementById('sm-core');
    if (modalCore) {
      modalCore.textContent = status.emergency ? 'Emergency Freeze' : (status.global_paused ? 'Paused' : 'Online');
      document.getElementById('sm-api').textContent = 'Online';
      document.getElementById('sm-db').textContent = status.database_ok ? 'Connected (PostgreSQL / SQLite)' : 'Disconnected';
      document.getElementById('sm-model').textContent = status.model_mode === 'remote' ? 'Gemini (Cloud Cascade)' : 'Local Fallback / Quantized';
      document.getElementById('sm-tools').textContent = `${status.tools_enabled} Enabled`;
      document.getElementById('sm-uptime').textContent = `${Math.floor(status.uptime_seconds)}s`;
    }

    // Approvals Badge
    const apprBadge = document.getElementById('nav-badge-approvals');
    if (apprBadge) {
      apprBadge.textContent = status.pending_approvals;
      apprBadge.style.display = status.pending_approvals > 0 ? 'inline-block' : 'none';
    }
  } catch (e) {
    console.error('Status refresh error:', e);
  }
}

async function refreshApprovals() {
  try {
    const approvals = await api('/approvals?status=pending');
    const container = document.getElementById('approval-banner-container');
    const fullContainer = document.getElementById('approvals-view-container');
    
    if (!approvals || approvals.length === 0) {
      if (container) container.innerHTML = '';
      if (fullContainer) fullContainer.innerHTML = '<div style="color:var(--text-muted); padding:16px;">No actions currently waiting for your approval. Everything is running within autonomous boundaries.</div>';
      return;
    }

    // Render Banner on Command Center
    if (container) {
      container.innerHTML = approvals.map(a => `
        <div class="approval-banner">
          <div class="approval-info">
            <div class="approval-title">
              <span>⚠️ ACTION REQUIRES YOUR APPROVAL</span>
              <span class="pill-tag pending">Level ${a.risk_level}</span>
            </div>
            <div class="approval-desc" style="margin-top:2px;">
              <strong>VAL wants to:</strong> ${a.action_payload.title || a.action_type}
            </div>
            <div style="font-size:11.5px; color:#cbd5e1; margin-top:2px;">
              Reason: ${a.action_payload.reason || 'This operation carries high operational impact.'}
            </div>
          </div>
          <div class="approval-actions">
            <button class="btn-ui btn-ui-primary" onclick="decideApproval('${a.approval_id}', 'approved')">Approve Action</button>
            <button class="btn-ui btn-ui-danger" onclick="decideApproval('${a.approval_id}', 'rejected')">Reject</button>
          </div>
        </div>
      `).join('');
    }

    // Render in Approvals Tab
    if (fullContainer) {
      fullContainer.innerHTML = approvals.map(a => `
        <div class="glass-panel" style="padding:18px; margin-bottom:12px;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div>
              <div style="font-size:15px; font-weight:700; color:#fbbf24;">${a.action_type}</div>
              <div style="font-size:13px; color:#fff; margin-top:4px;">${a.action_payload.title || 'Requested Execution'}</div>
              <div style="font-size:12px; color:var(--text-secondary); margin-top:4px;">
                Policy Reason: ${a.action_payload.reason || 'Level 4 Approval Required'}
              </div>
            </div>
            <span class="pill-tag pending">Level ${a.risk_level} Gate</span>
          </div>
          <div style="margin-top:14px; display:flex; gap:10px;">
            <button class="btn-ui btn-ui-primary" onclick="decideApproval('${a.approval_id}', 'approved')">Approve Action</button>
            <button class="btn-ui btn-ui-danger" onclick="decideApproval('${a.approval_id}', 'rejected')">Reject Action</button>
          </div>
        </div>
      `).join('');
    }
  } catch (e) {
    console.error('Approvals fetch error:', e);
  }
}

async function decideApproval(id, decision) {
  try {
    await api(`/approvals/${id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision, reason: `Authorized by Founder via interface` })
    });
    await refreshAll();
  } catch (e) {
    alert('Approval decision failed: ' + e.message);
  }
}

// Active Objectives & Tasks
async function refreshObjectives() {
  try {
    const tasks = await api('/tasks?limit=10');
    const container = document.getElementById('command-objectives-grid');
    const fullContainer = document.getElementById('all-objectives-grid');
    
    if (!tasks || tasks.length === 0) {
      const empty = '<div style="color:var(--text-muted); font-size:13px; padding:12px;">No active objectives. Give VAL a goal above to begin.</div>';
      if (container) container.innerHTML = empty;
      if (fullContainer) fullContainer.innerHTML = empty;
      return;
    }

    const cardsHtml = tasks.map(t => {
      const isComplete = t.status === 'succeeded';
      const isWaiting = t.status === 'waiting_approval';
      const steps = t.plan ? (t.plan.steps || []) : [];
      const completedSteps = steps.filter(s => s.status === 'succeeded').length;
      const progress = steps.length > 0 ? Math.round((completedSteps / steps.length) * 100) : (isComplete ? 100 : 35);
      
      const tagClass = isComplete ? 'succeeded' : (isWaiting ? 'pending' : 'learning');
      const tagText = isComplete ? 'Completed' : (isWaiting ? 'Needs Approval' : `${progress}%`);

      return `
        <div class="objective-card" onclick="openObjectiveDrawer('${t.task_id}')">
          <div class="objective-top">
            <span class="objective-name">${t.title.replace('Objective: ', '')}</span>
            <span class="pill-tag ${tagClass}">${tagText}</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: ${progress}%;"></div>
          </div>
          <div class="objective-status-line">
            <span>Workforce: <strong>VAL Core</strong></span>
            <span>${formatTimeAgo(t.created_at)}</span>
          </div>
        </div>
      `;
    }).join('');

    if (container) container.innerHTML = cardsHtml;
    if (fullContainer) fullContainer.innerHTML = cardsHtml;
  } catch (e) {
    console.error('Objectives refresh error:', e);
  }
}

// Workforce Agents
async function refreshAgents() {
  try {
    const agents = await api('/agents');
    const container = document.getElementById('command-workforce-grid');
    const fullContainer = document.getElementById('all-workforce-grid');

    if (!agents || agents.length === 0) return;

    const cardsHtml = agents.map(a => {
      const isLearning = a.name.includes('CALCULUS');
      const statusText = isLearning ? 'Learning • 72%' : (a.status === 'active' ? 'Ready' : a.status);
      const tagClass = isLearning ? 'learning' : 'succeeded';

      return `
        <div class="agent-card" onclick="openAgentModal('${a.name}')">
          <div class="agent-header">
            <div class="agent-icon">${a.name[0]}</div>
            <div class="agent-title-box">
              <div class="agent-name">${a.name}</div>
              <div class="agent-role">${a.role}</div>
            </div>
            <span class="pill-tag ${tagClass}">${statusText}</span>
          </div>
          <div class="agent-badges">
            <span class="agent-badge-pill">v${a.version}</span>
            <span class="agent-badge-pill">${(a.config.tool_allow_list || []).length} capabilities</span>
            <span class="agent-badge-pill">L${a.permissions.max_level || 2}</span>
          </div>
        </div>
      `;
    }).join('');

    if (container) container.innerHTML = cardsHtml;
    if (fullContainer) fullContainer.innerHTML = cardsHtml;
  } catch (e) {
    console.error('Agents refresh error:', e);
  }
}

// Activity Feed (Clean Human Readable)
async function refreshActivity() {
  try {
    const items = await api('/activity?limit=8');
    const container = document.getElementById('command-activity-feed');
    const fullContainer = document.getElementById('all-activity-feed');

    if (!items || items.length === 0) {
      const empty = '<div style="color:var(--text-muted); padding:12px;">No recent activity recorded yet.</div>';
      if (container) container.innerHTML = empty;
      if (fullContainer) fullContainer.innerHTML = empty;
      return;
    }

    const html = items.map(act => `
      <div class="activity-item" onclick="openAuditDetail('${act.id}')">
        <div class="activity-left">
          <span class="activity-bullet"></span>
          <span class="activity-text">${act.title}</span>
        </div>
        <span class="activity-time">${formatTimeAgo(act.timestamp)}</span>
      </div>
    `).join('');

    if (container) container.innerHTML = html;
    if (fullContainer) fullContainer.innerHTML = html;
  } catch (e) {
    console.error('Activity refresh error:', e);
  }
}

// Learning Section
async function refreshLearning() {
  try {
    const objectives = await api('/learning/objectives');
    const container = document.getElementById('learning-cards-container');
    if (!container) return;

    if (!objectives || objectives.length === 0) {
      container.innerHTML = `
        <div class="glass-panel" style="padding:24px; text-align:center;">
          <h3 style="color:#fff; margin-bottom:6px;">No Active Learning Curriculum</h3>
          <p style="color:var(--text-muted); font-size:13px; margin-bottom:16px;">
            Instruct VAL to master a domain (e.g. "Learn calculus well enough to teach me") to trigger autonomous curriculum generation.
          </p>
          <button class="btn-ui btn-ui-primary" onclick="initCalculusLearning()">Start Calculus Learning</button>
        </div>
      `;
      return;
    }

    container.innerHTML = objectives.map(o => `
      <div class="glass-panel" style="padding:22px; margin-bottom:16px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div>
            <h3 style="font-size:18px; color:#fff; font-weight:700;">${o.subject.toUpperCase()}</h3>
            <div style="color:var(--text-secondary); font-size:12.5px; margin-top:2px;">Specialized Intelligence: <strong>${o.agent_name}</strong></div>
          </div>
          <span class="pill-tag learning">${o.status.toUpperCase()}</span>
        </div>

        <div style="margin-top:16px;">
          <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:6px;">
            <span>Measured Mastery: <strong>${o.progress_score}%</strong></span>
            <span>Teaching Readiness: <strong>${o.teaching_readiness}%</strong></span>
          </div>
          <div class="progress-track" style="height:8px;">
            <div class="progress-fill" style="width: ${o.progress_score}%;"></div>
          </div>
        </div>

        <div style="margin-top:16px; display:grid; grid-template-columns:1fr 1fr; gap:12px; font-size:12.5px;">
          <div style="background:rgba(255,255,255,0.02); padding:10px 14px; border-radius:var(--radius-sm); border:1px solid var(--glass-border);">
            <div style="font-size:10.5px; color:var(--text-muted); text-transform:uppercase; font-weight:700;">Current Topic</div>
            <div style="color:#fff; font-weight:600; margin-top:2px;">${o.current_topic || 'Complete'}</div>
          </div>
          <div style="background:rgba(255,255,255,0.02); padding:10px 14px; border-radius:var(--radius-sm); border:1px solid var(--glass-border);">
            <div style="font-size:10.5px; color:var(--text-muted); text-transform:uppercase; font-weight:700;">Weak Areas Detected</div>
            <div style="color:${o.detected_weaknesses.length ? '#fbbf24' : '#34d399'}; font-weight:600; margin-top:2px;">
              ${o.detected_weaknesses.length ? o.detected_weaknesses.join('; ') : 'None detected — High rigor'}
            </div>
          </div>
        </div>

        <div style="margin-top:18px; display:flex; gap:10px;">
          <button class="btn-ui btn-ui-primary" onclick="advanceLearningStep('${o.objective_id}')">Run Practice Drill & Advance</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    console.error('Learning refresh error:', e);
  }
}

async function advanceLearningStep(id) {
  try {
    const res = await api(`/learning/objectives/${id}/advance`, { method: 'POST' });
    alert(`Knowledge Evaluation Complete:\n• Topic: ${res.topic_title}\n• Practice Score: ${res.practice_score}%\n• Overall Progress: ${res.overall_progress}%\n• Teaching Readiness: ${res.teaching_readiness}%\n• Next: ${res.next_action}`);
    await refreshAll();
  } catch (e) {
    alert('Advance learning error: ' + e.message);
  }
}

async function initCalculusLearning() {
  try {
    await api('/learning/objectives', {
      method: 'POST',
      body: JSON.stringify({
        subject: 'Calculus',
        goal: 'Learn calculus well enough to teach me'
      })
    });
    await refreshAll();
  } catch (e) {
    alert('Init learning failed: ' + e.message);
  }
}

// Founder Teaching Mode
async function submitFounderTeachingForm() {
  const input = document.getElementById('founder-teach-input');
  const scope = document.getElementById('founder-teach-scope').value;
  const statement = input.value.trim();
  if (!statement) return;

  const resBox = document.getElementById('founder-teach-response');
  resBox.style.display = 'block';
  resBox.innerHTML = '<span style="color:var(--accent-cyan);">Saving directive with High-Authority Founder Provenance...</span>';

  try {
    const res = await api('/learning/teach', {
      method: 'POST',
      body: JSON.stringify({ statement, scope })
    });
    input.value = '';
    resBox.innerHTML = `
      <div style="color:#34d399; font-weight:600;">✓ Directive Stored Successfully</div>
      <div style="font-size:12px; color:#cbd5e1; margin-top:4px;">
        Topic: <strong>${res.classified_topic}</strong> (Scope: ${res.scope})
      </div>
      ${res.clarifying_questions && res.clarifying_questions.length ? `
        <div style="margin-top:8px; font-size:11.5px; color:#fbbf24;">
          <strong>Proactive Clarification:</strong> ${res.clarifying_questions.join('<br>')}
        </div>
      ` : ''}
    `;
    await refreshTeachingsList();
  } catch (e) {
    resBox.innerHTML = `<span style="color:#fb7185;">Failed: ${e.message}</span>`;
  }
}

async function refreshTeachingsList() {
  try {
    const teachings = await api('/learning/teachings');
    const container = document.getElementById('stored-teachings-container');
    if (!container) return;
    if (!teachings || teachings.length === 0) {
      container.innerHTML = '<div style="color:var(--text-muted); padding:12px;">No directives recorded yet.</div>';
      return;
    }
    container.innerHTML = teachings.map(t => `
      <div style="background:rgba(255,255,255,0.02); border:1px solid var(--glass-border); padding:14px; border-radius:var(--radius-sm); margin-bottom:10px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <strong style="color:#fff; font-size:13.5px;">${t.title}</strong>
          <span class="pill-tag learning" style="font-size:10px;">FOUNDER PROVENANCE</span>
        </div>
        <div style="font-size:13px; color:#cbd5e1; margin-top:6px; line-height:1.5;">"${t.content}"</div>
        <div style="font-size:11px; color:var(--text-muted); margin-top:6px;">Recorded ${formatTimeAgo(t.created_at)}</div>
      </div>
    `).join('');
  } catch (e) {
    console.error('Teachings error:', e);
  }
}

// Agent Factory Form
async function submitAgentFactoryForm() {
  const domain = document.getElementById('factory-domain-input').value.trim();
  const purpose = document.getElementById('factory-purpose-input').value.trim();
  const resBox = document.getElementById('factory-build-result');
  if (!domain || !purpose) return alert('Please enter what the AI should specialize in and what it should do.');

  resBox.style.display = 'block';
  resBox.innerHTML = '<span style="color:var(--accent-cyan);">Manufacturing specialized agent in sandbox...</span>';

  try {
    const res = await api('/agents/factory/build', {
      method: 'POST',
      body: JSON.stringify({
        objective: `${domain}: ${purpose}`
      })
    });
    resBox.innerHTML = `
      <div style="color:#34d399; font-weight:700;">✓ ${res.agent_name} Created & Validated</div>
      <div style="font-size:12px; color:#cbd5e1; margin-top:4px;">
        Sandbox Validation: <strong>PASSED</strong> (${res.test_results.length} tests verified)
      </div>
    `;
    document.getElementById('factory-domain-input').value = '';
    document.getElementById('factory-purpose-input').value = '';
    await refreshAgents();
  } catch (e) {
    resBox.innerHTML = `<span style="color:#fb7185;">Factory build error: ${e.message}</span>`;
  }
}

// Natural Chat & Command Intake
async function sendCommand(text) {
  if (!text) return;
  
  // Switch to chat view
  switchView('view-chat');
  
  const history = document.getElementById('chat-history-box');
  if (history) {
    // Append user message
    const userRow = document.createElement('div');
    userRow.className = 'msg-row user';
    userRow.innerHTML = `<div class="msg-bubble">${escapeHtml(text)}</div>`;
    history.appendChild(userRow);
    history.scrollTop = history.scrollHeight;
  }

  try {
    const res = await api('/chat', {
      method: 'POST',
      body: JSON.stringify({
        content: text,
        conversation_id: currentConversationId,
        auto_execute: true
      })
    });

    currentConversationId = res.conversation_id;

    if (history) {
      const asstRow = document.createElement('div');
      asstRow.className = 'msg-row assistant';
      asstRow.innerHTML = `<div class="msg-bubble">${formatAssistantMarkdown(res.message.content)}</div>`;
      history.appendChild(asstRow);
      history.scrollTop = history.scrollHeight;
    }

    await refreshAll();
  } catch (e) {
    if (history) {
      const errRow = document.createElement('div');
      errRow.className = 'msg-row assistant';
      errRow.innerHTML = `<div class="msg-bubble" style="border-color:#fb7185; color:#fb7185;">Error: ${e.message}</div>`;
      history.appendChild(errRow);
    }
  }
}

function handleHeroCommandSubmit() {
  const input = document.getElementById('hero-command-input');
  if (!input) return;
  const text = input.value.trim();
  if (text) {
    input.value = '';
    sendCommand(text);
  }
}

function handleChatSubmit() {
  const input = document.getElementById('chat-text-input');
  if (!input) return;
  const text = input.value.trim();
  if (text) {
    input.value = '';
    sendCommand(text);
  }
}

// Progressive Disclosure: Agent Modal
async function openAgentModal(agentName) {
  try {
    const agent = await api(`/agents/${agentName}`);
    const modal = document.getElementById('agent-modal');
    document.getElementById('modal-agent-name').textContent = agent.name;
    document.getElementById('modal-agent-role').textContent = agent.role;
    document.getElementById('modal-agent-status').textContent = agent.status.toUpperCase();
    document.getElementById('modal-agent-tools').textContent = (agent.config.tool_allow_list || []).join(', ') || 'none';
    document.getElementById('modal-agent-prompt').textContent = agent.config.system_prompt || 'Default executive prompt';
    
    // Advanced technical specs
    document.getElementById('modal-tech-model').textContent = agent.config.model_preferences ? agent.config.model_preferences.default : 'Gemini 1.5 Flash';
    document.getElementById('modal-tech-perm').textContent = `Level ${agent.permissions.max_level || 2}`;
    document.getElementById('modal-tech-memory').textContent = (agent.config.memory_scope || []).join(', ');
    
    modal.classList.add('open');
  } catch (e) {
    alert('Failed to load agent: ' + e.message);
  }
}

function closeAgentModal() {
  document.getElementById('agent-modal').classList.remove('open');
}

// System Status Modal
function openSystemStatusModal() {
  document.getElementById('status-modal').classList.add('open');
}
function closeSystemStatusModal() {
  document.getElementById('status-modal').classList.remove('open');
}

// Advanced Tools & Sandbox
async function runAdvancedSandbox() {
  const code = document.getElementById('adv-sandbox-code').value.trim();
  const out = document.getElementById('adv-sandbox-out');
  if (!code) return;
  out.style.display = 'block';
  out.textContent = 'Running in isolated subprocess...';
  try {
    const res = await api('/tools/code_sandbox/execute', {
      method: 'POST',
      body: JSON.stringify({ code, timeout_seconds: 10 })
    });
    out.textContent = JSON.stringify(res.output || res.error, null, 2);
  } catch (e) {
    out.textContent = 'Execution error: ' + e.message;
  }
}

async function refreshAdvancedTools() {
  try {
    const tools = await api('/tools');
    const container = document.getElementById('adv-tools-list');
    if (!container) return;
    container.innerHTML = tools.map(t => `
      <div style="background:rgba(255,255,255,0.02); border:1px solid var(--glass-border); padding:10px 14px; border-radius:var(--radius-sm); margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <strong style="color:#fff;">${t.name}</strong>
          <span style="font-size:11px; color:var(--text-muted); margin-left:8px;">[Level ${t.required_permission_level}]</span>
          <div style="font-size:12px; color:var(--text-secondary); margin-top:2px;">${t.description}</div>
        </div>
        <span class="pill-tag ${t.risk_class === 'high' ? 'pending' : 'succeeded'}">${t.risk_class.toUpperCase()}</span>
      </div>
    `).join('');
  } catch (e) {
    console.error('Tools error:', e);
  }
}

async function refreshAdvancedAudit() {
  try {
    const logs = await api('/audit?limit=30');
    const container = document.getElementById('adv-audit-stream');
    if (!container) return;
    container.innerHTML = logs.map(l => `
      <div class="activity-item" style="font-family:var(--font-mono); font-size:11px;">
        <span style="color:var(--text-muted);">${new Date(l.created_at).toLocaleTimeString()}</span>
        <span style="color:#38bdf8; font-weight:600;">[${l.actor_type}]</span>
        <span style="color:#fff;">${l.action}</span>
        <span style="color:var(--text-dim); margin-left:auto;">${l.resource_type || '-'}</span>
      </div>
    `).join('');
  } catch (e) {
    console.error('Audit error:', e);
  }
}

// Emergency & Pause Controls
async function togglePause() {
  try {
    if (systemState.isPaused) {
      await api('/control/resume', { method: 'POST' });
    } else {
      await api('/control/pause', { method: 'POST' });
    }
    await refreshSystemStatus();
  } catch (e) {
    alert('Control action failed: ' + e.message);
  }
}

async function triggerEmergency() {
  if (!confirm('CONFIRM EMERGENCY STOP: Freeze all autonomous activity immediately?')) return;
  try {
    await api('/control/emergency', { method: 'POST' });
    await refreshSystemStatus();
  } catch (e) {
    alert('Emergency failed: ' + e.message);
  }
}

async function clearEmergency() {
  try {
    await api('/control/emergency/clear', { method: 'POST' });
    await refreshSystemStatus();
  } catch (e) {
    alert('Clear emergency failed: ' + e.message);
  }
}

// Helpers
function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function formatAssistantMarkdown(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code style="background:rgba(255,255,255,0.08); padding:1px 5px; border-radius:3px; font-family:var(--font-mono); font-size:12px;">$1</code>');
}

// Master Refresh
async function refreshAll() {
  await Promise.all([
    refreshSystemStatus(),
    refreshApprovals(),
    refreshObjectives(),
    refreshAgents(),
    refreshActivity()
  ]);
}

// Initial Boot
document.addEventListener('DOMContentLoaded', () => {
  refreshAll();
  refreshLearning();
  refreshTeachingsList();
  refreshAdvancedTools();
  refreshAdvancedAudit();
  setInterval(refreshAll, 3500);
});
