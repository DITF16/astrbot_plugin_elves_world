/**
 * 精灵对战游戏 - 管理后台 JavaScript
 */

// ==================== 全局状态 ====================
const state = {
    token: localStorage.getItem('auth_token') || '',
    currentPage: 'dashboard',
    players: {
        page: 1,
        limit: 20,
        total: 0
    }
};

// API基础URL
const API_BASE = '/api';

// ==================== 工具函数 ====================

/**
 * 发送API请求
 */
async function api(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    if (state.token) {
        headers['Authorization'] = `Bearer ${state.token}`;
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers
        });

        const data = await response.json();

        if (response.status === 401) {
            logout();
            throw new Error('登录已过期');
        }

        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * 显示Toast消息
 */
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toast-message');

    toast.className = `toast ${type}`;
    toastMessage.textContent = message;
    toast.classList.remove('hidden');

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

/**
 * 显示模态框
 */
function showModal(title, content, onConfirm) {
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');
    const confirmBtn = document.getElementById('modal-confirm-btn');

    modalTitle.textContent = title;
    modalBody.innerHTML = content;

    confirmBtn.onclick = () => {
        if (onConfirm) onConfirm();
    };

    modal.classList.remove('hidden');
}

/**
 * 关闭模态框
 */
function closeModal() {
    document.getElementById('modal').classList.add('hidden');
}

/**
 * 获取属性标签HTML - 与 default_types.json 同步
 */
function getTypeTag(type) {
    const typeNames = {
        fire: '火',
        water: '水',
        grass: '草',
        electric: '雷',
        ice: '冰',
        ground: '地',
        light: '光',
        dark: '暗'
    };
    const name = typeNames[type] || type;
    return `<span class="tag tag-${type}">${name}</span>`;
}

// 生成属性下拉选项的辅助函数
function getTypeOptions(includeEmpty = false) {
    const types = [
        { value: 'fire', name: '火' },
        { value: 'water', name: '水' },
        { value: 'grass', name: '草' },
        { value: 'electric', name: '雷' },
        { value: 'ice', name: '冰' },
        { value: 'ground', name: '地' },
        { value: 'light', name: '光' },
        { value: 'dark', name: '暗' }
    ];

    let options = includeEmpty ? '<option value="">无</option>' : '';
    options += types.map(t => `<option value="${t.value}">${t.name}</option>`).join('');
    return options;
}


/**
 * 获取技能类型标签
 */
function getCategoryTag(category) {
    const names = { physical: '物理', special: '特殊', status: '变化' };
    return `<span class="tag tag-${category}">${names[category] || category}</span>`;
}

/**
 * 获取稀有度星星
 */
function getRarityStars(rarity) {
    return `<span class="rarity-${rarity}">${'★'.repeat(rarity)}</span>`;
}

// ==================== 认证相关 ====================

/**
 * 检查登录状态
 */
async function checkAuth() {
    if (!state.token) {
        showLoginPage();
        return;
    }

    try {
        const result = await api('/check-auth');
        if (result.authenticated) {
            showMainPage();
            loadDashboard();
        } else {
            showLoginPage();
        }
    } catch {
        showLoginPage();
    }
}

/**
 * 登录
 */
async function login(password) {
    try {
        const result = await api('/login', {
            method: 'POST',
            body: JSON.stringify({ password })
        });

        if (result.success) {
            state.token = result.token;
            localStorage.setItem('auth_token', result.token);
            showMainPage();
            loadDashboard();
            showToast('登录成功', 'success');
        } else {
            document.getElementById('login-error').textContent = result.message;
        }
    } catch (error) {
        document.getElementById('login-error').textContent = '登录失败';
    }
}

/**
 * 登出
 */
function logout() {
    state.token = '';
    localStorage.removeItem('auth_token');
    showLoginPage();
    showToast('已退出登录');
}

/**
 * 显示登录页
 */
function showLoginPage() {
    document.getElementById('login-page').classList.remove('hidden');
    document.getElementById('main-page').classList.add('hidden');
}

/**
 * 显示主页
 */
function showMainPage() {
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('main-page').classList.remove('hidden');
}

// ==================== 页面切换 ====================

/**
 * 切换页面
 */
function switchPage(pageName) {
    state.currentPage = pageName;

    // 更新导航高亮
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.page === pageName) {
            item.classList.add('active');
        }
    });

    // 隐藏所有section
    document.querySelectorAll('.section').forEach(section => {
        section.classList.add('hidden');
    });

    // 显示目标section
    const targetSection = document.getElementById(`${pageName}-section`);
    if (targetSection) {
        targetSection.classList.remove('hidden');
    }

    // 更新标题
    const titles = {
        dashboard: '仪表盘',
        monsters: '精灵管理',
        skills: '技能管理',
        regions: '区域管理',
        bosses: 'BOSS管理',
        players: '玩家管理',
        types: '属性配置',
        settings: '系统设置'
    };
    document.getElementById('page-title').textContent = titles[pageName] || pageName;

    // 加载数据
    loadPageData(pageName);
}

/**
 * 加载页面数据
 */
function loadPageData(pageName) {
    switch (pageName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'monsters':
            loadMonsters();
            break;
        case 'skills':
            loadSkills();
            break;
        case 'regions':
            loadRegions();
            break;
        case 'bosses':
            loadBosses();
            break;
        case 'players':
            loadPlayers();
            break;
        case 'types':
            loadTypes();
            break;
    }
}

// ==================== 仪表盘 ====================

async function loadDashboard() {
    try {
        const result = await api('/dashboard');
        if (result.success) {
            const data = result.data;
            document.getElementById('stat-players').textContent = data.total_players || 0;
            document.getElementById('stat-monsters').textContent = data.total_monsters || 0;
            document.getElementById('stat-battles').textContent = data.total_battles || 0;
            document.getElementById('stat-templates').textContent = data.monster_templates || 0;
            document.getElementById('info-skills').textContent = data.skill_count || 0;
            document.getElementById('info-regions').textContent = data.region_count || 0;
            document.getElementById('info-bosses').textContent = data.boss_count || 0;
        }
    } catch (error) {
        showToast('加载仪表盘失败', 'error');
    }
}

// ==================== 精灵管理 ====================

async function loadMonsters() {
    try {
        const result = await api('/monsters');
        if (result.success) {
            renderMonstersTable(result.data);
        }
    } catch (error) {
        showToast('加载精灵列表失败', 'error');
    }
}

function renderMonstersTable(monsters) {
    const tbody = document.getElementById('monsters-table-body');

    if (!monsters || monsters.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    <div class="empty-icon">🐾</div>
                    <p>暂无精灵数据</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = monsters.map(m => `
        <tr>
            <td><code>${m.id}</code></td>
            <td>${m.name}</td>
            <td>${(m.types || []).map(t => getTypeTag(t)).join(' ')}</td>
            <td>${getRarityStars(m.rarity || 3)}</td>
            <td>
                HP:${m.base_stats?.hp || 0} 
                攻:${m.base_stats?.attack || 0} 
                防:${m.base_stats?.defense || 0}
            </td>
            <td class="table-actions">
                <button class="btn btn-secondary btn-small" onclick="editMonster('${m.id}')">编辑</button>
                <button class="btn btn-danger btn-small" onclick="deleteMonster('${m.id}')">删除</button>
            </td>
        </tr>
    `).join('');
}

function showMonsterModal(monsterId = null) {
    const isEdit = !!monsterId;
    const title = isEdit ? '编辑精灵' : '添加精灵';

    const content = `
        <form id="monster-form">
            <div class="form-row">
                <div class="form-group">
                    <label>名称 *</label>
                    <input type="text" name="name" required>
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>属性1 *</label>
                    <select name="type1" required>${getTypeOptions()}</select>
                </div>
                <div class="form-group">
                    <label>属性2</label>
                    <select name="type2">${getTypeOptions(true)}</select>
                </div>
            </div>
            
            <div class="form-group">
                <label>稀有度</label>
                <select name="rarity">
                    <option value="1">★ 普通</option>
                    <option value="2">★★ 优秀</option>
                    <option value="3" selected>★★★ 稀有</option>
                    <option value="4">★★★★ 史诗</option>
                    <option value="5">★★★★★ 传说</option>
                </select>
            </div>
            
            <h4 style="margin: 20px 0 16px;">基础属性</h4>
            <div class="form-row-3">
                <div class="form-group">
                    <label>HP</label>
                    <input type="number" name="hp" value="50" min="1">
                </div>
                <div class="form-group">
                    <label>攻击</label>
                    <input type="number" name="attack" value="50" min="1">
                </div>
                <div class="form-group">
                    <label>防御</label>
                    <input type="number" name="defense" value="50" min="1">
                </div>
            </div>
            <div class="form-row-3">
                <div class="form-group">
                    <label>特攻</label>
                    <input type="number" name="sp_attack" value="50" min="1">
                </div>
                <div class="form-group">
                    <label>特防</label>
                    <input type="number" name="sp_defense" value="50" min="1">
                </div>
                <div class="form-group">
                    <label>速度</label>
                    <input type="number" name="speed" value="50" min="1">
                </div>
            </div>
            
            <div class="form-group">
                <label>初始技能 (用逗号分隔)</label>
                <input type="text" name="skills" placeholder="火球术, 烈焰爪, 火焰吐息">
            </div>
            
            <div class="form-group">
                <label>描述</label>
                <textarea name="description" placeholder="精灵的描述文字..."></textarea>
            </div>
        </form>
    `;

    showModal(title, content, async () => {
        await saveMonster(isEdit);
    });

    // 如果是编辑，加载数据
    if (isEdit) {
        loadMonsterData(monsterId);
    }
}

async function loadMonsterData(monsterId) {
    try {
        const result = await api(`/monsters/${monsterId}`);
        if (result.success) {
            const m = result.data;
            const form = document.getElementById('monster-form');

            form.querySelector('[name="id"]').value = m.id;
            form.querySelector('[name="name"]').value = m.name;
            form.querySelector('[name="type1"]').value = m.types?.[0] || 'normal';
            form.querySelector('[name="type2"]').value = m.types?.[1] || '';
            form.querySelector('[name="rarity"]').value = m.rarity || 3;
            form.querySelector('[name="hp"]').value = m.base_stats?.hp || 50;
            form.querySelector('[name="attack"]').value = m.base_stats?.attack || 50;
            form.querySelector('[name="defense"]').value = m.base_stats?.defense || 50;
            form.querySelector('[name="sp_attack"]').value = m.base_stats?.sp_attack || 50;
            form.querySelector('[name="sp_defense"]').value = m.base_stats?.sp_defense || 50;
            form.querySelector('[name="speed"]').value = m.base_stats?.speed || 50;
            form.querySelector('[name="skills"]').value = (m.skills || []).join(', ');
            form.querySelector('[name="description"]').value = m.description || '';
        }
    } catch (error) {
        showToast('加载精灵数据失败', 'error');
    }
}

async function saveMonster(isEdit) {
    const form = document.getElementById('monster-form');
    const formData = new FormData(form);

    const types = [formData.get('type1')];
    if (formData.get('type2')) {
        types.push(formData.get('type2'));
    }

    const skillsStr = formData.get('skills') || '';
    const skills = skillsStr.split(',').map(s => s.trim()).filter(s => s);

    const data = {
        id: formData.get('id'),
        name: formData.get('name'),
        types: types,
        rarity: parseInt(formData.get('rarity')),
        base_stats: {
            hp: parseInt(formData.get('hp')),
            attack: parseInt(formData.get('attack')),
            defense: parseInt(formData.get('defense')),
            sp_attack: parseInt(formData.get('sp_attack')),
            sp_defense: parseInt(formData.get('sp_defense')),
            speed: parseInt(formData.get('speed'))
        },
        skills: skills,
        description: formData.get('description')
    };

    try {
        const endpoint = isEdit ? `/monsters/${data.id}` : '/monsters';
        const method = isEdit ? 'PUT' : 'POST';

        const result = await api(endpoint, {
            method: method,
            body: JSON.stringify(data)
        });

        if (result.success) {
            closeModal();
            showToast(isEdit ? '更新成功' : '创建成功', 'success');
            loadMonsters();
        } else {
            showToast(result.message || '保存失败', 'error');
        }
    } catch (error) {
        showToast('保存失败', 'error');
    }
}

function editMonster(monsterId) {
    showMonsterModal(monsterId);
}

async function deleteMonster(monsterId) {
    if (!confirm(`确定要删除精灵 "${monsterId}" 吗？`)) {
        return;
    }

    try {
        const result = await api(`/monsters/${monsterId}`, { method: 'DELETE' });
        if (result.success) {
            showToast('删除成功', 'success');
            loadMonsters();
        } else {
            showToast(result.message || '删除失败', 'error');
        }
    } catch (error) {
        showToast('删除失败', 'error');
    }
}

// ==================== 技能管理 ====================

async function loadSkills() {
    try {
        const result = await api('/skills');
        if (result.success) {
            renderSkillsTable(result.data);
        }
    } catch (error) {
        showToast('加载技能列表失败', 'error');
    }
}

function renderSkillsTable(skills) {
    const tbody = document.getElementById('skills-table-body');

    if (!skills || skills.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state">
                    <div class="empty-icon">⚔️</div>
                    <p>暂无技能数据</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = skills.map(s => `
        <tr>
            <td><code>${s.id}</code></td>
            <td>${s.name}</td>
            <td>${getTypeTag(s.type || 'normal')}</td>
            <td>${getCategoryTag(s.category || 'physical')}</td>
            <td>${s.power || '-'}</td>
            <td>${s.accuracy || 100}%</td>
            <td class="table-actions">
                <button class="btn btn-secondary btn-small" onclick="editSkill('${s.id}')">编辑</button>
                <button class="btn btn-danger btn-small" onclick="deleteSkill('${s.id}')">删除</button>
            </td>
        </tr>
    `).join('');
}

function showSkillModal(skillId = null) {
    const isEdit = !!skillId;
    const title = isEdit ? '编辑技能' : '添加技能';

    const content = `
        <form id="skill-form">
            <div class="form-row">
                <div class="form-group">
                    <label>名称 *</label>
                    <input type="text" name="name" required>
                </div>
            </div>
            
            <div class="form-row-3">
                <div class="form-group">
                    <label>属性</label>
                    <select name="type">
                        <option value="fire">火</option>
                        <option value="water">水</option>
                        <option value="grass">草</option>
                        <option value="electric">雷</option>
                        <option value="ice">冰</option>
                        <option value="ground">地</option>
                        <option value="light">光</option>
                        <option value="dark">暗</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>分类</label>
                    <select name="category">
                        <option value="physical">物理</option>
                        <option value="special">特殊</option>
                        <option value="status">变化</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>优先度</label>
                    <input type="number" name="priority" value="0" min="-7" max="7">
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>威力</label>
                    <input type="number" name="power" value="0" min="0">
                    <div class="hint">变化技能填0</div>
                </div>
                <div class="form-group">
                    <label>命中率</label>
                    <input type="number" name="accuracy" value="100" min="0" max="100">
                </div>
            </div>
            
            <div class="form-group">
                <label>描述</label>
                <textarea name="description" placeholder="技能的描述..."></textarea>
            </div>
        </form>
    `;

    showModal(title, content, async () => {
        await saveSkill(isEdit);
    });

    if (isEdit) {
        loadSkillData(skillId);
    }
}

async function loadSkillData(skillId) {
    try {
        const result = await api(`/skills/${skillId}`);
        if (result.success) {
            const s = result.data;
            const form = document.getElementById('skill-form');

            form.querySelector('[name="id"]').value = s.id;
            form.querySelector('[name="name"]').value = s.name;
            form.querySelector('[name="type"]').value = s.type || 'normal';
            form.querySelector('[name="category"]').value = s.category || 'physical';
            form.querySelector('[name="priority"]').value = s.priority || 0;
            form.querySelector('[name="power"]').value = s.power || 0;
            form.querySelector('[name="accuracy"]').value = s.accuracy || 100;
            form.querySelector('[name="description"]').value = s.description || '';
        }
    } catch (error) {
        showToast('加载技能数据失败', 'error');
    }
}

async function saveSkill(isEdit) {
    const form = document.getElementById('skill-form');
    const formData = new FormData(form);

    const data = {
        id: formData.get('id'),
        name: formData.get('name'),
        type: formData.get('type'),
        category: formData.get('category'),
        priority: parseInt(formData.get('priority')) || 0,
        power: parseInt(formData.get('power')) || 0,
        accuracy: parseInt(formData.get('accuracy')) || 100,
        description: formData.get('description'),
        effects: []
    };

    try {
        const endpoint = isEdit ? `/skills/${data.id}` : '/skills';
        const method = isEdit ? 'PUT' : 'POST';

        const result = await api(endpoint, {
            method: method,
            body: JSON.stringify(data)
        });

        if (result.success) {
            closeModal();
            showToast(isEdit ? '更新成功' : '创建成功', 'success');
            loadSkills();
        } else {
            showToast(result.message || '保存失败', 'error');
        }
    } catch (error) {
        showToast('保存失败', 'error');
    }
}

function editSkill(skillId) {
    showSkillModal(skillId);
}

async function deleteSkill(skillId) {
    if (!confirm(`确定要删除技能 "${skillId}" 吗？`)) {
        return;
    }

    try {
        const result = await api(`/skills/${skillId}`, { method: 'DELETE' });
        if (result.success) {
            showToast('删除成功', 'success');
            loadSkills();
        } else {
            showToast(result.message || '删除失败', 'error');
        }
    } catch (error) {
        showToast('删除失败', 'error');
    }
}

// ==================== 区域管理 ====================

async function loadRegions() {
    try {
        const result = await api('/regions');
        if (result.success) {
            renderRegionsTable(result.data);
        }
    } catch (error) {
        showToast('加载区域列表失败', 'error');
    }
}

function renderRegionsTable(regions) {
    const tbody = document.getElementById('regions-table-body');

    if (!regions || regions.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    <div class="empty-icon">🗺️</div>
                    <p>暂无区域数据</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = regions.map(r => `
        <tr>
            <td><code>${r.id}</code></td>
            <td>${r.name}</td>
            <td>Lv.${r.level_range?.[0] || 1} - ${r.level_range?.[1] || 10}</td>
            <td>⚡${r.stamina_cost || 10}</td>
            <td>${(r.wild_monsters || []).length}种</td>
            <td class="table-actions">
                <button class="btn btn-secondary btn-small" onclick="editRegion('${r.id}')">编辑</button>
                <button class="btn btn-danger btn-small" onclick="deleteRegion('${r.id}')">删除</button>
            </td>
        </tr>
    `).join('');
}

function showRegionModal(regionId = null) {
    const isEdit = !!regionId;
    const title = isEdit ? '编辑区域' : '添加区域';

    const content = `
        <form id="region-form">
            <div class="form-row">
                <div class="form-group">
                    <label>名称 *</label>
                    <input type="text" name="name" required>
                </div>
            </div>
            
            <div class="form-row-3">
                <div class="form-group">
                    <label>最低等级</label>
                    <input type="number" name="level_min" value="1" min="1">
                </div>
                <div class="form-group">
                    <label>最高等级</label>
                    <input type="number" name="level_max" value="10" min="1">
                </div>
                <div class="form-group">
                    <label>体力消耗</label>
                    <input type="number" name="stamina_cost" value="10" min="1">
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>地图尺寸</label>
                    <select name="map_size">
                        <option value="small">小 (4x4)</option>
                        <option value="medium" selected>中 (5x5)</option>
                        <option value="large">大 (6x6)</option>
                        <option value="huge">巨大 (8x8)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>解锁条件</label>
                    <input type="text" name="unlock_requires" placeholder="可选，如 boss:forest_boss">
                </div>
            </div>
            
            <div class="form-group">
                <label>野生精灵 (每行一个: 精灵名:权重)</label>
                <textarea name="wild_monsters" rows="4" placeholder="烈焰龙:10&#10;水灵精:15&#10;青叶狐:20"></textarea>
                <div class="hint">权重越高出现概率越大</div>
            </div>
            
            <div class="form-group">
                <label>描述</label>
                <textarea name="description" placeholder="区域的描述..."></textarea>
            </div>
        </form>
    `;

    showModal(title, content, async () => {
        await saveRegion(isEdit);
    });

    if (isEdit) {
        loadRegionData(regionId);
    }
}

async function loadRegionData(regionId) {
    try {
        const result = await api(`/regions`);
        if (result.success) {
            const region = result.data.find(r => r.id === regionId);
            if (region) {
                const form = document.getElementById('region-form');

                form.querySelector('[name="id"]').value = region.id;
                form.querySelector('[name="name"]').value = region.name;
                form.querySelector('[name="level_min"]').value = region.level_range?.[0] || 1;
                form.querySelector('[name="level_max"]').value = region.level_range?.[1] || 10;
                form.querySelector('[name="stamina_cost"]').value = region.stamina_cost || 10;
                form.querySelector('[name="map_size"]').value = region.map_size || 'medium';
                form.querySelector('[name="unlock_requires"]').value = region.unlock_requires || '';

                const wildMonsters = (region.wild_monsters || [])
                    .map(m => `${m.id}:${m.weight || 10}`)
                    .join('\n');
                form.querySelector('[name="wild_monsters"]').value = wildMonsters;
                form.querySelector('[name="description"]').value = region.description || '';
            }
        }
    } catch (error) {
        showToast('加载区域数据失败', 'error');
    }
}

async function saveRegion(isEdit) {
    const form = document.getElementById('region-form');
    const formData = new FormData(form);

    // 解析野生精灵
    const wildMonstersStr = formData.get('wild_monsters') || '';
    const wildMonsters = wildMonstersStr.split('\n')
        .map(line => line.trim())
        .filter(line => line)
        .map(line => {
            const [id, weight] = line.split(':');
            return { id: id.trim(), weight: parseInt(weight) || 10 };
        });

    const data = {
        id: formData.get('id'),
        name: formData.get('name'),
        level_range: [
            parseInt(formData.get('level_min')) || 1,
            parseInt(formData.get('level_max')) || 10
        ],
        stamina_cost: parseInt(formData.get('stamina_cost')) || 10,
        map_size: formData.get('map_size'),
        unlock_requires: formData.get('unlock_requires') || null,
        wild_monsters: wildMonsters,
        description: formData.get('description')
    };

    try {
        const endpoint = isEdit ? `/regions/${data.id}` : '/regions';
        const method = isEdit ? 'PUT' : 'POST';

        const result = await api(endpoint, {
            method: method,
            body: JSON.stringify(data)
        });

        if (result.success) {
            closeModal();
            showToast(isEdit ? '更新成功' : '创建成功', 'success');
            loadRegions();
        } else {
            showToast(result.message || '保存失败', 'error');
        }
    } catch (error) {
        showToast('保存失败', 'error');
    }
}

function editRegion(regionId) {
    showRegionModal(regionId);
}

async function deleteRegion(regionId) {
    if (!confirm(`确定要删除区域 "${regionId}" 吗？`)) {
        return;
    }

    try {
        const result = await api(`/regions/${regionId}`, { method: 'DELETE' });
        if (result.success) {
            showToast('删除成功', 'success');
            loadRegions();
        } else {
            showToast(result.message || '删除失败', 'error');
        }
    } catch (error) {
        showToast('删除失败', 'error');
    }
}

// ==================== BOSS管理 ====================

async function loadBosses() {
    try {
        const result = await api('/bosses');
        if (result.success) {
            renderBossesTable(result.data);
        }
    } catch (error) {
        showToast('加载BOSS列表失败', 'error');
    }
}

function renderBossesTable(bosses) {
    const tbody = document.getElementById('bosses-table-body');

    if (!bosses || bosses.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    <div class="empty-icon">👹</div>
                    <p>暂无BOSS数据</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = bosses.map(b => `
        <tr>
            <td><code>${b.id}</code></td>
            <td>${b.name}</td>
            <td>Lv.${b.level || 10}</td>
            <td>${(b.types || []).map(t => getTypeTag(t)).join(' ')}</td>
            <td>${b.region || '-'}</td>
            <td class="table-actions">
                <button class="btn btn-secondary btn-small" onclick="editBoss('${b.id}')">编辑</button>
                <button class="btn btn-danger btn-small" onclick="deleteBoss('${b.id}')">删除</button>
            </td>
        </tr>
    `).join('');
}

function showBossModal(bossId = null) {
    const isEdit = !!bossId;
    const title = isEdit ? '编辑BOSS' : '添加BOSS';

    const content = `
        <form id="boss-form">
            <div class="form-row">
                <div class="form-group">
                    <label>名称 *</label>
                    <input type="text" name="name" required>
                </div>
            </div>
            
            <div class="form-row-3">
                <div class="form-group">
                    <label>等级</label>
                    <input type="number" name="level" value="20" min="1">
                </div>
                <div class="form-group">
                    <label>属性1</label>
                    <select name="type1">
                        <option value="fire">🔥 火</option>
                        <option value="water">💧 水</option>
                        <option value="grass">🌿 草</option>
                        <option value="electric">⚡ 雷</option>
                        <option value="ice">❄️ 冰</option>
                        <option value="ground">🏔️ 地</option>
                        <option value="light">✨ 光</option>
                        <option value="dark">🌑 暗</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>所在区域</label>
                    <input type="text" name="region" placeholder="新手森林">
                </div>
            </div>
            
            <h4 style="margin: 20px 0 16px;">基础属性</h4>
            <div class="form-row-3">
                <div class="form-group">
                    <label>HP</label>
                    <input type="number" name="hp" value="200" min="1">
                </div>
                <div class="form-group">
                    <label>攻击</label>
                    <input type="number" name="attack" value="80" min="1">
                </div>
                <div class="form-group">
                    <label>防御</label>
                    <input type="number" name="defense" value="80" min="1">
                </div>
            </div>
            <div class="form-row-3">
                <div class="form-group">
                    <label>特攻</label>
                    <input type="number" name="sp_attack" value="80" min="1">
                </div>
                <div class="form-group">
                    <label>特防</label>
                    <input type="number" name="sp_defense" value="80" min="1">
                </div>
                <div class="form-group">
                    <label>速度</label>
                    <input type="number" name="speed" value="60" min="1">
                </div>
            </div>
            
            <div class="form-group">
                <label>技能 (用逗号分隔)</label>
                <input type="text" name="skills" placeholder="藤鞭, 飞叶快刀, 光合作用">
            </div>
            
            <h4 style="margin: 20px 0 16px;">奖励设置</h4>
            <div class="form-row-3">
                <div class="form-group">
                    <label>金币奖励</label>
                    <input type="number" name="reward_coins" value="500" min="0">
                </div>
                <div class="form-group">
                    <label>经验奖励</label>
                    <input type="number" name="reward_exp" value="200" min="0">
                </div>
                <div class="form-group">
                    <label>钻石奖励</label>
                    <input type="number" name="reward_diamonds" value="10" min="0">
                </div>
            </div>
        </form>
    `;

    showModal(title, content, async () => {
        await saveBoss(isEdit);
    });

    if (isEdit) {
        loadBossData(bossId);
    }
}

async function loadBossData(bossId) {
    try {
        const result = await api('/bosses');
        if (result.success) {
            const boss = result.data.find(b => b.id === bossId);
            if (boss) {
                const form = document.getElementById('boss-form');

                form.querySelector('[name="id"]').value = boss.id;
                form.querySelector('[name="name"]').value = boss.name;
                form.querySelector('[name="level"]').value = boss.level || 20;
                form.querySelector('[name="type1"]').value = boss.types?.[0] || 'normal';
                form.querySelector('[name="region"]').value = boss.region || '';
                form.querySelector('[name="hp"]').value = boss.base_stats?.hp || 200;
                form.querySelector('[name="attack"]').value = boss.base_stats?.attack || 80;
                form.querySelector('[name="defense"]').value = boss.base_stats?.defense || 80;
                form.querySelector('[name="sp_attack"]').value = boss.base_stats?.sp_attack || 80;
                form.querySelector('[name="sp_defense"]').value = boss.base_stats?.sp_defense || 80;
                form.querySelector('[name="speed"]').value = boss.base_stats?.speed || 60;
                form.querySelector('[name="skills"]').value = (boss.skills || []).join(', ');
                form.querySelector('[name="reward_coins"]').value = boss.rewards?.coins || 500;
                form.querySelector('[name="reward_exp"]').value = boss.rewards?.exp || 200;
                form.querySelector('[name="reward_diamonds"]').value = boss.rewards?.diamonds || 10;
            }
        }
    } catch (error) {
        showToast('加载BOSS数据失败', 'error');
    }
}

async function saveBoss(isEdit) {
    const form = document.getElementById('boss-form');
    const formData = new FormData(form);

    const skillsStr = formData.get('skills') || '';
    const skills = skillsStr.split(',').map(s => s.trim()).filter(s => s);

    const data = {
        id: formData.get('id'),
        name: formData.get('name'),
        level: parseInt(formData.get('level')) || 20,
        types: [formData.get('type1')],
        region: formData.get('region') || null,
        base_stats: {
            hp: parseInt(formData.get('hp')) || 200,
            attack: parseInt(formData.get('attack')) || 80,
            defense: parseInt(formData.get('defense')) || 80,
            sp_attack: parseInt(formData.get('sp_attack')) || 80,
            sp_defense: parseInt(formData.get('sp_defense')) || 80,
            speed: parseInt(formData.get('speed')) || 60
        },
        skills: skills,
        rewards: {
            coins: parseInt(formData.get('reward_coins')) || 500,
            exp: parseInt(formData.get('reward_exp')) || 200,
            diamonds: parseInt(formData.get('reward_diamonds')) || 10
        }
    };

    try {
        const endpoint = isEdit ? `/bosses/${data.id}` : '/bosses';
        const method = isEdit ? 'PUT' : 'POST';

        const result = await api(endpoint, {
            method: method,
            body: JSON.stringify(data)
        });

        if (result.success) {
            closeModal();
            showToast(isEdit ? '更新成功' : '创建成功', 'success');
            loadBosses();
        } else {
            showToast(result.message || '保存失败', 'error');
        }
    } catch (error) {
        showToast('保存失败', 'error');
    }
}

function editBoss(bossId) {
    showBossModal(bossId);
}

async function deleteBoss(bossId) {
    if (!confirm(`确定要删除BOSS "${bossId}" 吗？`)) {
        return;
    }

    try {
        const result = await api(`/bosses/${bossId}`, { method: 'DELETE' });
        if (result.success) {
            showToast('删除成功', 'success');
            loadBosses();
        } else {
            showToast(result.message || '删除失败', 'error');
        }
    } catch (error) {
        showToast('删除失败', 'error');
    }
}

// ==================== 玩家管理 ====================

async function loadPlayers(page = 1) {
    state.players.page = page;

    try {
        const result = await api(`/players?page=${page}&limit=${state.players.limit}`);
        if (result.success) {
            state.players.total = result.total;
            renderPlayersTable(result.data);
            renderPlayersPagination();
        }
    } catch (error) {
        showToast('加载玩家列表失败', 'error');
    }
}

function renderPlayersTable(players) {
    const tbody = document.getElementById('players-table-body');

    if (!players || players.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state">
                    <div class="empty-icon">👥</div>
                    <p>暂无玩家数据</p>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = players.map(p => `
        <tr>
            <td><code>${p.user_id}</code></td>
            <td>${p.name || '-'}</td>
            <td>Lv.${p.level || 1}</td>
            <td>💰${p.coins || 0}</td>
            <td>${p.monster_count || 0}</td>
            <td>${p.wins || 0}胜 / ${p.losses || 0}负</td>
            <td class="table-actions">
                <button class="btn btn-secondary btn-small" onclick="showPlayerDetail('${p.user_id}')">详情</button>
                <button class="btn btn-primary btn-small" onclick="showGiveModal('${p.user_id}')">发放</button>
            </td>
        </tr>
    `).join('');
}

function renderPlayersPagination() {
    const pagination = document.getElementById('players-pagination');
    const totalPages = Math.ceil(state.players.total / state.players.limit);

    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '';

    // 上一页
    if (state.players.page > 1) {
        html += `<button onclick="loadPlayers(${state.players.page - 1})">上一页</button>`;
    }

    // 页码
    for (let i = 1; i <= totalPages; i++) {
        if (i === state.players.page) {
            html += `<button class="active">${i}</button>`;
        } else if (Math.abs(i - state.players.page) <= 2 || i === 1 || i === totalPages) {
            html += `<button onclick="loadPlayers(${i})">${i}</button>`;
        } else if (Math.abs(i - state.players.page) === 3) {
            html += `<span>...</span>`;
        }
    }

    // 下一页
    if (state.players.page < totalPages) {
        html += `<button onclick="loadPlayers(${state.players.page + 1})">下一页</button>`;
    }

    pagination.innerHTML = html;
}

function searchPlayers() {
    const keyword = document.getElementById('player-search').value.trim();
    // TODO: 实现搜索功能
    showToast('搜索功能开发中', 'info');
}

async function showPlayerDetail(userId) {
    try {
        const result = await api(`/players/${userId}`);
        if (!result.success) {
            showToast('获取玩家信息失败', 'error');
            return;
        }

        const { player, monsters } = result.data;

        const content = `
            <div class="player-detail">
                <div class="player-info-card">
                    <h4>📋 基本信息</h4>
                    <div class="info-row"><span>ID</span><span>${player.user_id}</span></div>
                    <div class="info-row"><span>名称</span><span>${player.name || '-'}</span></div>
                    <div class="info-row"><span>等级</span><span>Lv.${player.level || 1}</span></div>
                    <div class="info-row"><span>经验</span><span>${player.exp || 0}</span></div>
                    <div class="info-row"><span>金币</span><span>💰${player.coins || 0}</span></div>
                    <div class="info-row"><span>钻石</span><span>💎${player.diamonds || 0}</span></div>
                    <div class="info-row"><span>体力</span><span>⚡${player.stamina || 0}/100</span></div>
                </div>
                <div class="player-info-card">
                    <h4>📊 战绩统计</h4>
                    <div class="info-row"><span>胜场</span><span>${player.wins || 0}</span></div>
                    <div class="info-row"><span>败场</span><span>${player.losses || 0}</span></div>
                    <div class="info-row"><span>胜率</span><span>${player.wins > 0 ? Math.round(player.wins / (player.wins + player.losses) * 100) : 0}%</span></div>
                    <div class="info-row"><span>精灵数</span><span>${monsters.length}</span></div>
                </div>
            </div>
            <div style="margin-top: 20px;">
                <h4>🐾 拥有的精灵 (${monsters.length})</h4>
                <div class="player-monsters-list">
                    ${monsters.length > 0 ? monsters.map(m => `
                        <div class="player-monster-item">
                            <span>${m.nickname || m.name} Lv.${m.level}</span>
                            <span>HP: ${m.current_hp}/${m.max_hp}</span>
                        </div>
                    `).join('') : '<p style="padding: 20px; color: #999;">暂无精灵</p>'}
                </div>
            </div>
        `;

        showModal(`玩家详情 - ${player.name || userId}`, content, null);
        document.getElementById('modal-confirm-btn').style.display = 'none';

    } catch (error) {
        showToast('获取玩家信息失败', 'error');
    }
}

function showGiveModal(userId) {
    const content = `
        <form id="give-form">
            <input type="hidden" name="user_id" value="${userId}">
            <div class="form-row">
                <div class="form-group">
                    <label>金币</label>
                    <input type="number" name="coins" value="0" min="0">
                </div>
                <div class="form-group">
                    <label>钻石</label>
                    <input type="number" name="diamonds" value="0" min="0">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>经验</label>
                    <input type="number" name="exp" value="0" min="0">
                </div>
                <div class="form-group">
                    <label>体力</label>
                    <input type="number" name="stamina" value="0" min="0">
                </div>
            </div>
        </form>
    `;

    showModal('发放奖励', content, async () => {
        await giveToPlayer(userId);
    });

    document.getElementById('modal-confirm-btn').style.display = '';
}

async function giveToPlayer(userId) {
    const form = document.getElementById('give-form');
    const formData = new FormData(form);

    const data = {
        coins: parseInt(formData.get('coins')) || 0,
        diamonds: parseInt(formData.get('diamonds')) || 0,
        exp: parseInt(formData.get('exp')) || 0,
        stamina: parseInt(formData.get('stamina')) || 0
    };

    if (data.coins === 0 && data.diamonds === 0 && data.exp === 0 && data.stamina === 0) {
        showToast('请至少填写一项奖励', 'error');
        return;
    }


    try {
        const result = await api(`/players/${userId}/give`, {
            method: 'POST',
            body: JSON.stringify(data)
        });

        if (result.success) {
            closeModal();
            showToast('发放成功', 'success');
            loadPlayers(state.players.page);
        } else {
            showToast(result.message || '发放失败', 'error');
        }
    } catch (error) {
        showToast('发放失败', 'error');
    }
}

// ==================== 属性配置 ====================

async function loadTypes() {
    try {
        const result = await api('/types');
        if (result.success) {
            renderTypesGrid(result.data);
        }
    } catch (error) {
        showToast('加载属性配置失败', 'error');
    }
}

function renderTypesGrid(types) {
    const grid = document.getElementById('types-grid');

    if (!types || Object.keys(types).length === 0) {
        grid.innerHTML = '<p class="empty-state">暂无属性配置</p>';
        return;
    }

    const typeIcons = {
        fire: '🔥', water: '💧', grass: '🌿', electric: '⚡',
        ice: '❄️', fighting: '🥊', poison: '☠️', ground: '🏔️',
        flying: '🦅', psychic: '🔮', bug: '🐛', rock: '🪨',
        ghost: '👻', dragon: '🐲', dark: '🌑', steel: '⚙️',
        fairy: '✨', normal: '⚪'
    };

    const typeNames = {
        fire: '火', water: '水', grass: '草', electric: '电',
        ice: '冰', fighting: '格斗', poison: '毒', ground: '地面',
        flying: '飞行', psychic: '超能', bug: '虫', rock: '岩石',
        ghost: '幽灵', dragon: '龙', dark: '恶', steel: '钢',
        fairy: '妖精', normal: '普通'
    };

    grid.innerHTML = Object.entries(types).map(([key, type]) => {
        const icon = typeIcons[key] || '❓';
        const name = type.name || typeNames[key] || key;

        const strongAgainst = (type.strong_against || [])
            .map(t => typeNames[t] || t).join(', ') || '无';
        const weakAgainst = (type.weak_against || [])
            .map(t => typeNames[t] || t).join(', ') || '无';

        return `
            <div class="type-card">
                <div class="type-icon">${icon}</div>
                <div class="type-name">${name}</div>
                <div class="type-relations">
                    <div style="color: #22c55e;">克制: ${strongAgainst}</div>
                    <div style="color: #ef4444;">被克: ${weakAgainst}</div>
                </div>
            </div>
        `;
    }).join('');
}

// ==================== 系统设置 ====================

async function reloadConfig() {
    if (!confirm('确定要重新加载所有配置吗？')) {
        return;
    }

    try {
        const result = await api('/config/reload', { method: 'POST' });
        if (result.success) {
            showToast('配置已重新加载', 'success');
            // 刷新当前页面数据
            loadPageData(state.currentPage);
        } else {
            showToast(result.message || '重载失败', 'error');
        }
    } catch (error) {
        showToast('重载失败', 'error');
    }
}

async function backupConfig() {
    try {
        const result = await api('/config/backup', { method: 'POST' });
        if (result.success) {
            showToast(result.message || '备份成功', 'success');
        } else {
            showToast(result.message || '备份失败', 'error');
        }
    } catch (error) {
        showToast('备份失败', 'error');
    }
}

function confirmResetAll() {
    const content = `
        <div style="text-align: center; padding: 20px;">
            <div style="font-size: 4rem; margin-bottom: 20px;">⚠️</div>
            <h3 style="color: #ef4444; margin-bottom: 16px;">危险操作！</h3>
            <p style="margin-bottom: 20px;">此操作将删除所有玩家数据，且不可恢复！</p>
            <p>请输入 <strong>RESET</strong> 确认操作：</p>
            <input type="text" id="reset-confirm-input" style="margin-top: 12px; padding: 10px; width: 200px; text-align: center; font-size: 16px;">
        </div>
    `;

    showModal('确认重置', content, async () => {
        const input = document.getElementById('reset-confirm-input');
        if (input.value !== 'RESET') {
            showToast('确认文字不正确', 'error');
            return;
        }

        // TODO: 调用重置API
        showToast('功能开发中', 'info');
        closeModal();
    });
}

// ==================== 事件绑定 ====================

document.addEventListener('DOMContentLoaded', () => {
    // 检查认证状态
    checkAuth();

    // 登录表单
    document.getElementById('login-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const password = document.getElementById('password').value;
        login(password);
    });

    // 登出按钮
    document.getElementById('logout-btn').addEventListener('click', () => {
        if (confirm('确定要退出登录吗？')) {
            logout();
        }
    });

    // 导航切换
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            if (page) {
                switchPage(page);
            }
        });
    });

    // 重载配置按钮
    document.getElementById('reload-config-btn').addEventListener('click', reloadConfig);

    // 点击模态框外部关闭
    document.getElementById('modal').addEventListener('click', (e) => {
        if (e.target.id === 'modal') {
            closeModal();
        }
    });

    // ESC键关闭模态框
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
        }
    });
});

// ==================== 全局函数暴露 ====================
// 这些函数需要在HTML中通过onclick调用

window.showMonsterModal = showMonsterModal;
window.editMonster = editMonster;
window.deleteMonster = deleteMonster;

window.showSkillModal = showSkillModal;
window.editSkill = editSkill;
window.deleteSkill = deleteSkill;

window.showRegionModal = showRegionModal;
window.editRegion = editRegion;
window.deleteRegion = deleteRegion;

window.showBossModal = showBossModal;
window.editBoss = editBoss;
window.deleteBoss = deleteBoss;

window.showPlayerDetail = showPlayerDetail;
window.showGiveModal = showGiveModal;
window.searchPlayers = searchPlayers;
window.loadPlayers = loadPlayers;

window.reloadConfig = reloadConfig;
window.backupConfig = backupConfig;
window.confirmResetAll = confirmResetAll;

window.closeModal = closeModal;

