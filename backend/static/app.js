const API_BASE = '/api';

// --- State ---
let currentFilters = {
    category: 'all',
    date: 'all',
    score_min: 0,
    trust_levels: [], // array of HIGH, MEDIUM, LOW
    search: '',
    sort_by: 'published_at',
    page: 1
};
let globalStats = {};

// --- Utilities ---
async function apiCall(endpoint, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
        if (!response.ok) throw new Error('API Request Failed');
        return await response.json();
    } catch (err) {
        console.error(err);
        return null;
    }
}

function getIsoDateFrom(val) {
    if (val === 'all') return '';
    const d = new Date();
    if (val === 'today') {
        d.setHours(0, 0, 0, 0);
    } else if (val === 'week') {
        d.setDate(d.getDate() - 7);
    } else if (val === 'month') {
        d.setMonth(d.getMonth() - 1);
    }
    return d.toISOString();
}

// --- Common UI Handling ---
document.addEventListener('DOMContentLoaded', () => {
    // Theme
    const toggleBtn = document.getElementById('themeToggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const root = document.documentElement;
            const isDark = root.getAttribute('data-theme') === 'dark';
            root.setAttribute('data-theme', isDark ? 'light' : 'dark');
        });
    }

    // Manual Collect
    const collectBtn = document.getElementById('collectBtn');
    if (collectBtn) {
        collectBtn.addEventListener('click', async () => {
            const originalHtml = collectBtn.innerHTML; // Store original text
            collectBtn.innerHTML = '実行中...';
            collectBtn.disabled = true;

            try {
                await apiCall('/collect', { method: 'POST' });

                const checkStatus = setInterval(async () => {
                    const statusData = await apiCall('/collect/status');

                    if (statusData) {
                        if (statusData.is_collecting) {
                            collectBtn.innerHTML = statusData.message || '収集中...';
                        } else {
                            clearInterval(checkStatus);

                            if (statusData.last_error) {
                                collectBtn.innerHTML = 'エラー: ' + statusData.last_error.substring(0, 20) + '...';
                                console.error("Collection Error:", statusData.last_error);
                            } else {
                                collectBtn.innerHTML = '収集完了';
                            }

                            // Reload articles after brief delay to show completion message
                            setTimeout(() => {
                                loadStats();
                                loadArticles();

                                // Revert button after 5 seconds to give time to read errors
                                setTimeout(() => {
                                    collectBtn.innerHTML = originalHtml;
                                    collectBtn.disabled = false;
                                }, 5000);
                            }, 1000);
                        }
                    }
                }, 3000);
            } catch (err) {
                collectBtn.innerHTML = '通信エラー';
                setTimeout(() => {
                    collectBtn.innerHTML = originalHtml;
                    collectBtn.disabled = false;
                }, 3000);
            }
        });
    }

    // Global Search Bar -> Redirects to search.html for AI Search
    const searchBar = document.getElementById('globalSearch');
    if (searchBar) {
        searchBar.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && e.target.value.trim() !== '') {
                // If already on search page, skip redirect
                if (window.location.pathname.includes('search.html')) return;
                window.location.href = `/search.html?q=${encodeURIComponent(e.target.value.trim())}`;
            }
        });
    }
});

// --- Article Rendering ---
function renderArticleCard(article) {
    const d = new Date(article.published_at);
    const dateStr = `${d.getFullYear()}/${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')}`;
    const tags = JSON.parse(article.tags || '[]');
    const companyTags = JSON.parse(article.company_tags || '[]');

    let tagsHtml = '';
    companyTags.forEach(t => tagsHtml += `<span class="tag company-tag">${t}</span>`);
    tags.forEach(t => tagsHtml += `<span class="tag">${t}</span>`);

    const clipIcon = article.is_clipped ? '★' : '☆';

    return `
        <div class="article-card">
            <div class="card-top-border priority-${article.priority_label}"></div>
            
            <div class="card-header">
                <span class="priority-badge priority-${article.priority_label}">${article.priority_label}</span>
                <span class="trust-badge trust-${article.trust_level}">${article.trust_level}</span>
            </div>
            
            <div class="article-title">
                <a href="${article.url}" target="_blank">${article.title}</a>
            </div>
            
            <div class="article-meta">
                <span>${article.source_name}</span> • <span>${dateStr}</span>
            </div>
            
            <div class="article-summary">${article.summary_ja ? article.summary_ja.replace(/\n/g, '<br>') : '要約なし'}</div>
            
            ${article.business_point ? `<div class="business-point">${article.business_point}</div>` : ''}
            
            <div class="score-bar-container">
                <div class="score-info">
                    <span>AI Score</span>
                    <span>${article.score}/100</span>
                </div>
                <div class="score-track">
                    <div class="score-fill" style="width: ${article.score}%; background: ${article.score >= 80 ? 'var(--trust-high)' : article.score >= 50 ? 'var(--trust-medium)' : 'var(--trust-low)'}"></div>
                </div>
            </div>
            
            <div class="tags-container">
                ${tagsHtml}
            </div>
            
            <div class="card-footer">
                <button class="action-btn" onclick="toggleClip(${article.id})" title="クリップ">${clipIcon}</button>
            </div>
        </div>
    `;
}

async function toggleClip(id) {
    // Simple toggle logic (for full implementation we would check current state)
    // Assume we just clip it to "default" for now if unhandled in UI state
    await apiCall(`/articles/${id}/clip`, {
        method: 'POST',
        body: JSON.stringify({ folder: 'default' })
    });
    alert('クリップしました！');
    if (window.location.pathname.includes('clips.html')) {
        location.reload();
    }
}

// --- Browse Page specific ---
function initBrowseParams() {
    // Category bindings
    document.querySelectorAll('.filter-btn[data-type="category"]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const target = e.currentTarget;
            document.querySelectorAll('.filter-btn[data-type="category"]').forEach(b => b.classList.remove('active'));
            target.classList.add('active');
            currentFilters.category = target.dataset.val;
            currentFilters.page = 1;
            loadArticles();
        });
    });

    // Date bindings
    document.querySelectorAll('.filter-btn[data-type="date"]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const target = e.currentTarget;
            document.querySelectorAll('.filter-btn[data-type="date"]').forEach(b => b.classList.remove('active'));
            target.classList.add('active');
            currentFilters.date = target.dataset.val;
            currentFilters.page = 1;
            loadArticles();
        });
    });

    // Score Range
    const scoreRange = document.getElementById('scoreRange');
    const scoreVal = document.getElementById('scoreVal');
    if (scoreRange) {
        scoreRange.addEventListener('change', (e) => {
            currentFilters.score_min = parseInt(e.target.value);
            scoreVal.textContent = e.target.value;
            currentFilters.page = 1;
            loadArticles();
        });
        scoreRange.addEventListener('input', (e) => {
            scoreVal.textContent = e.target.value;
        });
    }

    // Trust Level Array Bindings
    document.querySelectorAll('.trust-toggle').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const target = e.currentTarget;
            target.classList.toggle('active');
            const val = target.dataset.val;
            if (target.classList.contains('active')) {
                if (!currentFilters.trust_levels.includes(val)) currentFilters.trust_levels.push(val);
            } else {
                currentFilters.trust_levels = currentFilters.trust_levels.filter(v => v !== val);
            }
            currentFilters.page = 1;
            loadArticles();
        });
    });

    // Sort Bindings
    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            currentFilters.sort_by = e.target.value;
            currentFilters.page = 1;
            loadArticles();
        });
    }

    // Pagination
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentFilters.page > 1) {
                currentFilters.page--;
                loadArticles();
            }
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            currentFilters.page++;
            loadArticles();
        });
    }
}

async function loadStats() {
    const st = await apiCall('/stats');
    if (st) {
        document.getElementById('statsPanel').innerHTML = `
            総記事数: ${st.total_articles}<br>
            今日の記事: ${st.today_articles}<br>
            平均スコア: ${st.avg_score}<br>
            高信頼度: ${st.high_trust_count}
        `;
    }
}

async function loadArticles() {
    const grid = document.getElementById('articlesGrid');
    const loadEl = document.getElementById('loading');
    if (!grid || !loadEl) return;

    loadEl.style.display = 'block';
    grid.innerHTML = '';

    try {
        const params = new URLSearchParams({
            page: currentFilters.page,
            per_page: 20,
            sort_by: currentFilters.sort_by
        });

        if (currentFilters.category !== 'all') params.append('category', currentFilters.category);
        if (currentFilters.date !== 'all') params.append('date_from', getIsoDateFrom(currentFilters.date));
        if (currentFilters.score_min > 0) params.append('score_min', currentFilters.score_min);
        // Note: The FastAPI backend currently is setup for a single trust_level. If the user wants multiple "HIGH,MEDIUM", you'd usually pass it as a list, but our Python endpoint accepts a single string. Let's just pass the first one or skip if multiple unless backend updated. For now, pass first active.
        if (currentFilters.trust_levels.length > 0) params.append('trust_level', currentFilters.trust_levels[0]);

        const data = await apiCall(`/articles?${params}`);
        if (!data) return;

        document.getElementById('resultsCount').textContent = `${data.total}件中 ${(data.page - 1) * data.per_page + 1}〜${Math.min(data.page * data.per_page, data.total)}件`;

        if (data.articles.length === 0) {
            grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted); background: var(--bg-secondary); border-radius: 12px; border: 1px dashed var(--border-color);">まだデータがありません。手動収集を実行してください。</div>';
        } else {
            data.articles.forEach(art => {
                grid.innerHTML += renderArticleCard(art);
            });
        }

        // Pagination
        const pBtn = document.getElementById('pagination');
        if (pBtn) {
            pBtn.style.display = data.total_pages > 1 ? 'block' : 'none';
            document.getElementById('pageInfo').textContent = `${data.page} / ${data.total_pages}`;
            document.getElementById('prevBtn').disabled = data.page === 1;
            document.getElementById('nextBtn').disabled = data.page === data.total_pages;
        }

    } catch (e) {
        console.error(e);
        grid.innerHTML = '<div style="grid-column: 1/-1; color: var(--breaking);">データの読み込みに失敗しました</div>';
    } finally {
        loadEl.style.display = 'none';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}
