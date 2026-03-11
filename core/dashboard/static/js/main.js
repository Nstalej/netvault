/**
 * NetVault - Core JavaScript
 */

async function fetchData(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            // Special handling for 404/401 but generally just log
            console.warn(`HTTP ${response.status} from ${url}`);
            return null;
        }
        return await response.json();
    } catch (e) {
        console.error(`Error fetching ${url}:`, e);
        return null;
    }
}


function renderDeviceStatus(status) {
    const config = {
        online: { label: 'Online', class: 'status-online', icon: '●' },
        offline: { label: 'Offline', class: 'status-offline', icon: '●' },
        warning: { label: 'Warning', class: 'status-warning', icon: '▲' },
        unknown: { label: 'Unknown', class: 'status-unknown', icon: '?' }
    };
    const normalized = String(status || 'unknown').toLowerCase();
    const s = config[normalized] || config.unknown;
    return `<span class="badge ${s.class}">${s.icon} ${s.label}</span>`;
}

function updateLastRefreshed() {
    const el = document.getElementById('last-updated');
    if (el) {
        const now = new Date();
        el.textContent = `Updated: ${now.toLocaleTimeString()}`;
    }
}

// Global Refresh Function (to be extended by pages)
async function refreshData() {
    const app = document.getElementById('app');
    app.classList.add('loading');

    // Call page-specific refresh logic if it exists
    if (typeof refreshPageData === 'function') {
        await refreshPageData();
    }

    // Refresh common health info
    const health = await fetchData('/api/v1/health');
    if (health) {
        // We could update more global elements here if needed
    }

    updateLastRefreshed();
    app.classList.remove('loading');
}

// Global Actions
async function runAudit(deviceId = 0, type = 'network') {
    if (!confirm(`Start ${deviceId === 0 ? 'global network' : 'device'} audit?`)) return;

    const result = await fetchData(`/api/v1/audit/run?device_id=${deviceId}&audit_type=${type}`, { method: 'POST' });
    if (result) {
        alert('Audit triggered successfully');
        refreshData();
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    refreshData();
    // Auto refresh every 30s
    setInterval(refreshData, 30000);
});
