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
        items: '物品管理',
        players: '玩家管理',
        natures: '性格管理',
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
        case 'items':
            loadItems();
            break;
        case 'players':
            loadPlayers();
            break;
        case 'natures':
            loadNatures();
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
        // 改为使用查询参数:
        const result = await api(`/monsters/detail?id=${encodeURIComponent(monsterId)}`);
        if (result.success) {
            const m = result.data;
            const form = document.getElementById('monster-form');
            form.querySelector('[name="name"]').value = m.name;
            form.querySelector('[name="type1"]').value = m.types?.[0] || 'fire';
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

            // 保存原始ID用于更新（存到表单的data属性）
            form.dataset.originalId = m.id;
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
    // 编辑时用原始ID，新建时用名称作为ID
    const originalId = form.dataset.originalId;
    const newId = formData.get('name');  // 用名称作为ID
    const data = {
        id: newId,
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
        const endpoint = isEdit
            ? `/monsters/update?id=${encodeURIComponent(originalId)}`
            : '/monsters';
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
        const result = await api(`/monsters/delete?id=${encodeURIComponent(monsterId)}`, { method: 'DELETE' });
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
                        <option value="normal">普通</option>
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

            <div class="form-group">
                <label>技能效果 <button type="button" class="btn btn-secondary btn-small" onclick="addSkillEffect()">+ 添加效果</button></label>
                <div id="skill-effects-container"></div>
                <div class="hint">可添加多个效果，如：中毒、麻痹、属性变化、护盾、回血等</div>
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
        const result = await api(`/skills/detail?id=${encodeURIComponent(skillId)}`);
        if (result.success) {
            const s = result.data;
            const form = document.getElementById('skill-form');
            form.querySelector('[name="name"]').value = s.name;
            form.querySelector('[name="type"]').value = s.type || 'fire';
            form.querySelector('[name="category"]').value = s.category || 'physical';
            form.querySelector('[name="priority"]').value = s.priority || 0;
            form.querySelector('[name="power"]').value = s.power || 0;
            form.querySelector('[name="accuracy"]').value = s.accuracy || 100;
            form.querySelector('[name="description"]').value = s.description || '';

            // 保存原始ID
            form.dataset.originalId = s.id;
            
            // 渲染技能效果
            renderSkillEffects(s.effects || []);
        }
    } catch (error) {
        showToast('加载技能数据失败', 'error');
    }
}

async function saveSkill(isEdit) {
    const form = document.getElementById('skill-form');
    const formData = new FormData(form);
    const originalId = form.dataset.originalId;
    const newId = formData.get('name');
    const data = {
        id: newId,
        name: formData.get('name'),
        type: formData.get('type'),
        category: formData.get('category'),
        priority: parseInt(formData.get('priority')) || 0,
        power: parseInt(formData.get('power')) || 0,
        accuracy: parseInt(formData.get('accuracy')) || 100,
        description: formData.get('description'),
        effects: collectSkillEffects()
    };
    try {
        const endpoint = isEdit
            ? `/skills/update?id=${encodeURIComponent(originalId)}`
            : '/skills';
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
        const result = await api(`/skills/delete?id=${encodeURIComponent(skillId)}`, { method: 'DELETE' });
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

// ==================== 技能效果配置 ====================

// 效果类型定义 - 包含所有支持的效果
const SKILL_EFFECT_TYPES = {
    // 状态效果
    'poison': { name: '中毒', category: 'status', hasValue: true, valueLabel: '每回合伤害%', hasDuration: true, hasChance: true },
    'burn': { name: '烧伤', category: 'status', hasValue: true, valueLabel: '每回合伤害%', hasDuration: true, hasChance: true },
    'paralyze': { name: '麻痹', category: 'status', hasValue: false, hasDuration: true, hasChance: true },
    'sleep': { name: '睡眠', category: 'status', hasValue: false, hasDuration: true, hasChance: true },
    'freeze': { name: '冰冻', category: 'status', hasValue: false, hasDuration: true, hasChance: true },
    'confuse': { name: '混乱', category: 'status', hasValue: false, hasDuration: true, hasChance: true },
    
    // 回复效果
    'heal': { name: '治疗', category: 'recovery', hasValue: true, valueLabel: '回复HP%', hasDuration: false, hasChance: false, targetSelf: true },
    'regen': { name: '持续回复', category: 'recovery', hasValue: true, valueLabel: '每回合回复%', hasDuration: true, hasChance: false, targetSelf: true },
    'drain': { name: '吸血', category: 'recovery', hasValue: true, valueLabel: '吸取伤害%', hasDuration: false, hasChance: false, targetSelf: true },
    
    // 护盾效果
    'shield': { name: '护盾', category: 'defense', hasValue: true, valueLabel: '护盾值%HP', hasDuration: true, hasChance: false, targetSelf: true },
    
    // 属性提升 (自身)
    'attack_up': { name: '攻击提升', category: 'buff', hasValue: true, valueLabel: '提升%', hasDuration: true, hasChance: false, targetSelf: true },
    'defense_up': { name: '防御提升', category: 'buff', hasValue: true, valueLabel: '提升%', hasDuration: true, hasChance: false, targetSelf: true },
    'sp_attack_up': { name: '特攻提升', category: 'buff', hasValue: true, valueLabel: '提升%', hasDuration: true, hasChance: false, targetSelf: true },
    'sp_defense_up': { name: '特防提升', category: 'buff', hasValue: true, valueLabel: '提升%', hasDuration: true, hasChance: false, targetSelf: true },
    'speed_up': { name: '速度提升', category: 'buff', hasValue: true, valueLabel: '提升%', hasDuration: true, hasChance: false, targetSelf: true },
    'accuracy_up': { name: '命中提升', category: 'buff', hasValue: true, valueLabel: '提升%', hasDuration: true, hasChance: false, targetSelf: true },
    'evasion_up': { name: '闪避提升', category: 'buff', hasValue: true, valueLabel: '提升%', hasDuration: true, hasChance: false, targetSelf: true },
    'critical_up': { name: '暴击提升', category: 'buff', hasValue: true, valueLabel: '提升%', hasDuration: true, hasChance: false, targetSelf: true },
    
    // 属性降低 (敌方)
    'attack_down': { name: '攻击降低', category: 'debuff', hasValue: true, valueLabel: '降低%', hasDuration: true, hasChance: true },
    'defense_down': { name: '防御降低', category: 'debuff', hasValue: true, valueLabel: '降低%', hasDuration: true, hasChance: true },
    'sp_attack_down': { name: '特攻降低', category: 'debuff', hasValue: true, valueLabel: '降低%', hasDuration: true, hasChance: true },
    'sp_defense_down': { name: '特防降低', category: 'debuff', hasValue: true, valueLabel: '降低%', hasDuration: true, hasChance: true },
    'speed_down': { name: '速度降低', category: 'debuff', hasValue: true, valueLabel: '降低%', hasDuration: true, hasChance: true },
    'accuracy_down': { name: '命中降低', category: 'debuff', hasValue: true, valueLabel: '降低%', hasDuration: true, hasChance: true },
    'evasion_down': { name: '闪避降低', category: 'debuff', hasValue: true, valueLabel: '降低%', hasDuration: true, hasChance: true },
    
    // 特殊效果
    'recoil': { name: '反伤', category: 'special', hasValue: true, valueLabel: '反伤%', hasDuration: false, hasChance: false },
    'priority_up': { name: '先制', category: 'special', hasValue: true, valueLabel: '优先级', hasDuration: false, hasChance: false },
    'multi_hit': { name: '多段攻击', category: 'special', hasValue: true, valueLabel: '攻击次数', hasDuration: false, hasChance: false },
    'flinch': { name: '畏缩', category: 'special', hasValue: false, hasDuration: false, hasChance: true },
};

// 效果类别中文名
const EFFECT_CATEGORIES = {
    'status': '💀 状态异常',
    'recovery': '💚 回复效果',
    'defense': '🛡️ 防御效果',
    'buff': '⬆️ 属性提升',
    'debuff': '⬇️ 属性降低',
    'special': '✨ 特殊效果'
};

// 当前技能的效果列表
let currentSkillEffects = [];

// 添加技能效果
function addSkillEffect(effectData = null) {
    const container = document.getElementById('skill-effects-container');
    const effectIndex = container.children.length;
    
    const effect = effectData || {
        type: 'poison',
        value: 10,
        chance: 100,
        duration: 3,
        target: 'enemy'
    };
    
    const effectDiv = document.createElement('div');
    effectDiv.className = 'effect-item';
    effectDiv.dataset.index = effectIndex;
    
    // 获取效果类型信息
    const effectInfo = SKILL_EFFECT_TYPES[effect.type] || SKILL_EFFECT_TYPES['poison'];
    
    effectDiv.innerHTML = `
        <div class="effect-header">
            <span class="effect-title">效果 #${effectIndex + 1}</span>
            <button type="button" class="btn btn-danger btn-small" onclick="removeSkillEffect(${effectIndex})">删除</button>
        </div>
        <div class="effect-body">
            <div class="form-row">
                <div class="form-group">
                    <label>效果类型</label>
                    <select class="effect-type" onchange="onEffectTypeChange(${effectIndex})">
                        ${Object.entries(EFFECT_CATEGORIES).map(([catKey, catName]) => `
                            <optgroup label="${catName}">
                                ${Object.entries(SKILL_EFFECT_TYPES)
                                    .filter(([_, info]) => info.category === catKey)
                                    .map(([key, info]) => `
                                        <option value="${key}" ${effect.type === key ? 'selected' : ''}>${info.name}</option>
                                    `).join('')}
                            </optgroup>
                        `).join('')}
                    </select>
                </div>
                <div class="form-group effect-value-group" style="${effectInfo.hasValue ? '' : 'display:none'}">
                    <label class="effect-value-label">${effectInfo.valueLabel || '数值'}</label>
                    <input type="number" class="effect-value" value="${effect.value || 10}" min="0">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group effect-chance-group" style="${effectInfo.hasChance ? '' : 'display:none'}">
                    <label>触发几率 %</label>
                    <input type="number" class="effect-chance" value="${effect.chance || 100}" min="0" max="100">
                </div>
                <div class="form-group effect-duration-group" style="${effectInfo.hasDuration ? '' : 'display:none'}">
                    <label>持续回合</label>
                    <input type="number" class="effect-duration" value="${effect.duration || 3}" min="1" max="10">
                </div>
                <div class="form-group effect-target-group">
                    <label>目标</label>
                    <select class="effect-target">
                        <option value="enemy" ${effect.target === 'enemy' ? 'selected' : ''}>敌方</option>
                        <option value="self" ${effect.target === 'self' ? 'selected' : ''}>自身</option>
                    </select>
                </div>
            </div>
        </div>
    `;
    
    container.appendChild(effectDiv);
    
    // 设置默认目标
    if (effectInfo.targetSelf) {
        effectDiv.querySelector('.effect-target').value = 'self';
    }
}

// 效果类型改变时更新UI
function onEffectTypeChange(index) {
    const container = document.getElementById('skill-effects-container');
    const effectDiv = container.children[index];
    const typeSelect = effectDiv.querySelector('.effect-type');
    const effectType = typeSelect.value;
    const effectInfo = SKILL_EFFECT_TYPES[effectType];
    
    // 更新数值组
    const valueGroup = effectDiv.querySelector('.effect-value-group');
    const valueLabel = effectDiv.querySelector('.effect-value-label');
    if (effectInfo.hasValue) {
        valueGroup.style.display = '';
        valueLabel.textContent = effectInfo.valueLabel || '数值';
    } else {
        valueGroup.style.display = 'none';
    }
    
    // 更新几率组
    const chanceGroup = effectDiv.querySelector('.effect-chance-group');
    chanceGroup.style.display = effectInfo.hasChance ? '' : 'none';
    
    // 更新持续回合组
    const durationGroup = effectDiv.querySelector('.effect-duration-group');
    durationGroup.style.display = effectInfo.hasDuration ? '' : 'none';
    
    // 更新默认目标
    const targetSelect = effectDiv.querySelector('.effect-target');
    if (effectInfo.targetSelf) {
        targetSelect.value = 'self';
    } else if (effectInfo.category === 'status' || effectInfo.category === 'debuff') {
        targetSelect.value = 'enemy';
    }
}

// 删除技能效果
function removeSkillEffect(index) {
    const container = document.getElementById('skill-effects-container');
    const effectDiv = container.querySelector(`[data-index="${index}"]`);
    if (effectDiv) {
        effectDiv.remove();
        // 重新编号
        Array.from(container.children).forEach((div, i) => {
            div.dataset.index = i;
            div.querySelector('.effect-title').textContent = `效果 #${i + 1}`;
            // 更新删除按钮的onclick
            div.querySelector('.btn-danger').onclick = () => removeSkillEffect(i);
            // 更新类型选择的onchange
            div.querySelector('.effect-type').onchange = () => onEffectTypeChange(i);
        });
    }
}

// 收集所有效果数据
function collectSkillEffects() {
    const container = document.getElementById('skill-effects-container');
    const effects = [];
    
    Array.from(container.children).forEach(effectDiv => {
        const effectType = effectDiv.querySelector('.effect-type').value;
        const effectInfo = SKILL_EFFECT_TYPES[effectType];
        
        const effect = {
            type: effectType,
            target: effectDiv.querySelector('.effect-target').value
        };
        
        if (effectInfo.hasValue) {
            effect.value = parseInt(effectDiv.querySelector('.effect-value').value) || 0;
        }
        
        if (effectInfo.hasChance) {
            effect.chance = parseInt(effectDiv.querySelector('.effect-chance').value) || 100;
        }
        
        if (effectInfo.hasDuration) {
            effect.duration = parseInt(effectDiv.querySelector('.effect-duration').value) || 3;
        }
        
        effects.push(effect);
    });
    
    return effects;
}

// 渲染已有的效果列表
function renderSkillEffects(effects) {
    const container = document.getElementById('skill-effects-container');
    container.innerHTML = '';
    
    if (effects && effects.length > 0) {
        effects.forEach(effect => {
            addSkillEffect(effect);
        });
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
                form.querySelector('[name="name"]').value = region.name;
                form.querySelector('[name="level_min"]').value = region.level_range?.[0] || 1;
                form.querySelector('[name="level_max"]').value = region.level_range?.[1] || 10;
                form.querySelector('[name="stamina_cost"]').value = region.stamina_cost || 10;
                form.querySelector('[name="map_size"]').value = region.map_size || 'medium';
                form.querySelector('[name="unlock_requires"]').value = region.unlock_requires || '';
                const wildMonsters = (region.wild_monsters || [])
                    .map(m => `${m.monster_id || m.id || m.name}:${m.weight || 10}`)
                    .join('\n');
                form.querySelector('[name="wild_monsters"]').value = wildMonsters;
                form.querySelector('[name="description"]').value = region.description || '';

                // 新增：保存原始ID
                form.dataset.originalId = region.id;
            }
        }
    } catch (error) {
        showToast('加载区域数据失败', 'error');
    }
}

async function saveRegion(isEdit) {
    const form = document.getElementById('region-form');
    const formData = new FormData(form);
    const wildMonstersStr = formData.get('wild_monsters') || '';
    const wildMonsters = wildMonstersStr.split('\n')
        .map(line => line.trim())
        .filter(line => line)
        .map(line => {
            const [id, weight] = line.split(':');
            return { monster_id: id.trim(), weight: parseInt(weight) || 10 };
        });
    const originalId = form.dataset.originalId;
    const newId = formData.get('name');
    const data = {
        id: newId,
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
        const endpoint = isEdit
            ? `/regions/update?id=${encodeURIComponent(originalId)}`
            : '/regions';
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
        const result = await api(`/regions/delete?id=${encodeURIComponent(regionId)}`, { method: 'DELETE' });
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
                form.querySelector('[name="name"]').value = boss.name;
                form.querySelector('[name="level"]').value = boss.level || 20;
                form.querySelector('[name="type1"]').value = boss.types?.[0] || 'fire';
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

                // 新增：保存原始ID
                form.dataset.originalId = boss.id;
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
    const originalId = form.dataset.originalId;
    const newId = formData.get('name');
    const data = {
        id: newId,
        name: formData.get('name'),
        level: parseInt(formData.get('level')) || 20,
        types: [formData.get('type1')],
        region: formData.get('region'),
        base_stats: {
            hp: parseInt(formData.get('hp')),
            attack: parseInt(formData.get('attack')),
            defense: parseInt(formData.get('defense')),
            sp_attack: parseInt(formData.get('sp_attack')),
            sp_defense: parseInt(formData.get('sp_defense')),
            speed: parseInt(formData.get('speed'))
        },
        skills: skills,
        rewards: {
            coins: parseInt(formData.get('reward_coins')) || 500,
            exp: parseInt(formData.get('reward_exp')) || 200,
            diamonds: parseInt(formData.get('reward_diamonds')) || 10
        }
    };
    try {
        const endpoint = isEdit
            ? `/bosses/update?id=${encodeURIComponent(originalId)}`
            : '/bosses';
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
        const result = await api(`/bosses/delete?id=${encodeURIComponent(bossId)}`, { method: 'DELETE' });
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

// ==================== 物品管理 ====================

// 物品类型映射
const itemTypeNames = {
    capture: '捕捉', heal: '治疗', revive: '复活', evolution: '进化',
    stamina: '体力', exp: '经验', buff: '增益', tool: '道具', gift: '礼包', material: '材料',
    special: '特殊', subscription: '订阅'  // 新增类型
};


// 物品类型详细说明（供管理员参考）
const itemTypeDescriptions = {
    capture: {
        name: '🔮 捕捉球类',
        desc: '用于捕捉野生精灵，不同精灵球有不同的捕捉加成效果',
        usage: '探索/战斗中遇到野生精灵时使用'
    },
    heal: {
        name: '💊 治疗药品',
        desc: '恢复精灵HP或治疗异常状态（中毒、灼伤等）',
        usage: '背包中使用，需指定目标精灵序号'
    },
    revive: {
        name: '💖 复活药',
        desc: '复活已濒死的精灵，恢复一定比例HP',
        usage: '背包中使用，需指定濒死精灵序号'
    },
    stamina: {
        name: '⚡ 体力药水',
        desc: '恢复玩家体力值，用于探索和战斗',
        usage: '背包中直接使用'
    },
    exp: {
        name: '🍬 经验道具',
        desc: '为精灵提供经验值，加速升级',
        usage: '背包中使用，需指定目标精灵序号'
    },
    evolution: {
        name: '💎 进化石',
        desc: '特定属性的进化道具，用于进化精灵',
        usage: '精灵满足进化条件时在进化菜单使用'
    },
    buff: {
        name: '⚔️ 战斗增益',
        desc: '提升精灵战斗属性（攻击/防御/速度/暴击等）',
        usage: '【仅战斗中使用】选择道具菜单使用，效果持续数回合'
    },
    tool: {
        name: '🔧 工具道具',
        desc: '各类功能性道具',
        usage: '根据道具功能在相应场景使用'
    },
    gift: {
        name: '🎁 礼包',
        desc: '包含多种奖励的礼包，开启获得随机道具/货币',
        usage: '背包中直接使用开启'
    },
    material: {
        name: '📦 材料',
        desc: '用于合成或特殊用途的材料，部分为BOSS掉落的稀有道具',
        usage: '收集材料用于后续合成系统（开发中）'
    },
    special: {
        name: '⚗️ 特殊道具',
        desc: '属性重置、技能遗忘、技能学习等高级功能道具',
        usage: '背包中使用，需指定目标精灵序号。如：属性重置药剂可重新生成精灵IV值'
    },
    subscription: {
        name: '🎫 订阅道具',
        desc: '月卡等持续生效的特权道具，每日签到领取奖励',
        usage: '背包中激活，之后每日签到自动发放奖励'
    }
};

/**
 * 显示物品类型说明弹窗
 */
function showItemTypeHelp() {
    let content = '<div style="max-height:400px;overflow-y:auto;">';
    content += '<table class="help-table" style="width:100%;border-collapse:collapse;">';
    content += '<tr style="background:#333;"><th style="padding:8px;text-align:left;">类型</th><th style="padding:8px;text-align:left;">说明</th><th style="padding:8px;text-align:left;">使用场景</th></tr>';
    
    for (const [type, info] of Object.entries(itemTypeDescriptions)) {
        content += `<tr style="border-bottom:1px solid #444;">
            <td style="padding:8px;white-space:nowrap;">${info.name}</td>
            <td style="padding:8px;">${info.desc}</td>
            <td style="padding:8px;color:#888;">${info.usage}</td>
        </tr>`;
    }
    
    content += '</table></div>';
    content += '<p style="margin-top:15px;color:#888;font-size:12px;">💡 提示：buff类型道具只能在战斗中使用，special类型需要指定精灵序号</p>';
    
    showModal('📖 物品类型说明', content, null);
}


// 缓存物品数据用于筛选
let allItemsCache = [];

/**
 * 加载物品列表
 */
async function loadItems() {
    try {
        const result = await api('/items');
        if (result.success) {
            allItemsCache = result.data;
            renderItemsTable(result.data);
        }
    } catch (error) {
        showToast('加载物品失败', 'error');
    }
}

/**
 * 筛选物品
 */
function filterItems() {
    const typeFilter = document.getElementById('item-type-filter').value;
    const shopFilter = document.getElementById('item-shop-filter').value;
    
    let filtered = allItemsCache;
    
    if (typeFilter) {
        filtered = filtered.filter(item => item.type === typeFilter);
    }
    if (shopFilter !== '') {
        const shopAvailable = shopFilter === 'true';
        filtered = filtered.filter(item => item.shop_available === shopAvailable);
    }
    
    renderItemsTable(filtered);
}

/**
 * 渲染物品表格
 */
function renderItemsTable(items) {
    const tbody = document.getElementById('items-table-body');
    tbody.innerHTML = items.map(item => `
        <tr>
            <td><code>${item.id}</code></td>
            <td>${item.name}</td>
            <td><span class="tag tag-item-${item.type}">${itemTypeNames[item.type] || item.type}</span></td>
            <td>${getRarityStars(item.rarity || 1)}</td>
            <td>${item.price > 0 ? item.price : '-'}</td>
            <td>${item.currency === 'diamonds' ? '💎钻石' : '💰金币'}</td>
            <td>${item.shop_available ? '<span class="status-online">上架</span>' : '<span class="status-offline">下架</span>'}</td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="showItemModal('${item.id}')">编辑</button>
                <button class="btn btn-sm btn-danger" onclick="deleteItem('${item.id}')">删除</button>
            </td>
        </tr>
    `).join('');
}

/**
 * 显示物品编辑模态框
 */
async function showItemModal(itemId = null) {
    let item = {
        id: '', name: '', description: '', type: 'heal', rarity: 1,
        price: 100, currency: 'coins', shop_available: true,
        sellable: true, sell_price: 50, effect: {}
    };
    
    if (itemId) {
        try {
            const result = await api(`/items/detail?id=${itemId}`);
            if (result.success) {
                item = result.data;
            }
        } catch (error) {
            showToast('获取物品信息失败', 'error');
            return;
        }
    }
    
    const isEdit = !!itemId;
    const title = isEdit ? `编辑物品: ${item.name}` : '添加新物品';
    
    const content = `
        <form id="item-form" class="modal-form">
            <div class="form-row">
                <div class="form-group">
                    <label>物品ID *</label>
                    <input type="text" name="id" value="${item.id}" ${isEdit ? 'readonly' : 'required'} 
                           placeholder="如: super_potion">
                </div>
                <div class="form-group">
                    <label>物品名称 *</label>
                    <input type="text" name="name" value="${item.name}" required placeholder="如: 超级药水">
                </div>
            </div>
            <div class="form-group">
                <label>描述</label>
                <textarea name="description" rows="2" placeholder="物品描述...">${item.description || ''}</textarea>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>类型</label>
                    <select name="type">
                        <option value="capture" ${item.type === 'capture' ? 'selected' : ''}>捕捉道具</option>
                        <option value="heal" ${item.type === 'heal' ? 'selected' : ''}>治疗药水</option>
                        <option value="revive" ${item.type === 'revive' ? 'selected' : ''}>复活道具</option>
                        <option value="evolution" ${item.type === 'evolution' ? 'selected' : ''}>进化石</option>
                        <option value="stamina" ${item.type === 'stamina' ? 'selected' : ''}>体力道具</option>
                        <option value="exp" ${item.type === 'exp' ? 'selected' : ''}>经验道具</option>
                        <option value="buff" ${item.type === 'buff' ? 'selected' : ''}>增益道具</option>
                        <option value="tool" ${item.type === 'tool' ? 'selected' : ''}>工具道具</option>
                        <option value="gift" ${item.type === 'gift' ? 'selected' : ''}>礼包</option>
                        <option value="material" ${item.type === 'material' ? 'selected' : ''}>材料</option>
                        <option value="special" ${item.type === 'special' ? 'selected' : ''}>✨特殊道具（重置IV/技能遗忘/技能学习）</option>
                        <option value="subscription" ${item.type === 'subscription' ? 'selected' : ''}>🎫订阅道具（月卡等持续生效）</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>稀有度</label>
                    <select name="rarity">
                        <option value="1" ${item.rarity === 1 ? 'selected' : ''}>★ 普通</option>
                        <option value="2" ${item.rarity === 2 ? 'selected' : ''}>★★ 优秀</option>
                        <option value="3" ${item.rarity === 3 ? 'selected' : ''}>★★★ 稀有</option>
                        <option value="4" ${item.rarity === 4 ? 'selected' : ''}>★★★★ 史诗</option>
                        <option value="5" ${item.rarity === 5 ? 'selected' : ''}>★★★★★ 传说</option>
                    </select>
                </div>
            </div>
            <div class="form-section">
                <h4>💰 商店设置</h4>
                <div class="form-row">
                    <div class="form-group">
                        <label>购买价格</label>
                        <input type="number" name="price" value="${item.price || 0}" min="0">
                    </div>
                    <div class="form-group">
                        <label>货币类型</label>
                        <select name="currency">
                            <option value="coins" ${item.currency === 'coins' ? 'selected' : ''}>💰 金币</option>
                            <option value="diamonds" ${item.currency === 'diamonds' ? 'selected' : ''}>💎 钻石</option>
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>
                            <input type="checkbox" name="shop_available" ${item.shop_available ? 'checked' : ''}>
                            在商店出售
                        </label>
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" name="sellable" ${item.sellable ? 'checked' : ''}>
                            允许玩家出售
                        </label>
                    </div>
                </div>
                <div class="form-group">
                    <label>出售价格 (玩家卖出获得金币)</label>
                    <input type="number" name="sell_price" value="${item.sell_price || 0}" min="0">
                </div>
            </div>
            <div class="form-section">
                <h4>✨ 效果设置</h4>
                <div class="form-row">
                    <div class="form-group">
                        <label>治疗HP</label>
                        <input type="number" name="effect_heal_hp" value="${item.effect?.heal_hp || 0}" min="0">
                    </div>
                    <div class="form-group">
                        <label>治疗HP百分比</label>
                        <input type="number" name="effect_heal_percent" value="${item.effect?.heal_percent || 0}" min="0" max="100">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>恢复体力</label>
                        <input type="number" name="effect_restore_stamina" value="${item.effect?.restore_stamina || 0}" min="0">
                    </div>
                    <div class="form-group">
                        <label>经验值</label>
                        <input type="number" name="effect_exp" value="${item.effect?.exp || 0}" min="0">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>捕捉率加成</label>
                        <input type="number" name="effect_catch_rate" value="${item.effect?.catch_rate || 0}" step="0.1" min="0">
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" name="effect_revive" ${item.effect?.revive ? 'checked' : ''}>
                            可复活精灵
                        </label>
                    </div>
                </div>
            </div>
        </form>
    `;
    
    showModal(title, content, () => saveItem(isEdit));
}

/**
 * 保存物品
 */
async function saveItem(isEdit) {
    const form = document.getElementById('item-form');
    const formData = new FormData(form);
    
    const item = {
        id: formData.get('id'),
        name: formData.get('name'),
        description: formData.get('description'),
        type: formData.get('type'),
        rarity: parseInt(formData.get('rarity')),
        price: parseInt(formData.get('price')) || 0,
        currency: formData.get('currency'),
        shop_available: form.querySelector('[name="shop_available"]').checked,
        sellable: form.querySelector('[name="sellable"]').checked,
        sell_price: parseInt(formData.get('sell_price')) || 0,
        effect: {}
    };
    
    // 收集效果数据
    const healHp = parseInt(formData.get('effect_heal_hp')) || 0;
    const healPercent = parseInt(formData.get('effect_heal_percent')) || 0;
    const restoreStamina = parseInt(formData.get('effect_restore_stamina')) || 0;
    const exp = parseInt(formData.get('effect_exp')) || 0;
    const catchRate = parseFloat(formData.get('effect_catch_rate')) || 0;
    const revive = form.querySelector('[name="effect_revive"]').checked;
    
    if (healHp > 0) item.effect.heal_hp = healHp;
    if (healPercent > 0) item.effect.heal_percent = healPercent;
    if (restoreStamina > 0) item.effect.restore_stamina = restoreStamina;
    if (exp > 0) item.effect.exp = exp;
    if (catchRate > 0) item.effect.catch_rate = catchRate;
    if (revive) item.effect.revive = true;
    
    try {
        const endpoint = isEdit ? '/items/update' : '/items';
        const result = await api(endpoint, {
            method: isEdit ? 'PUT' : 'POST',
            body: JSON.stringify(item)
        });
        
        if (result.success) {
            showToast(isEdit ? '物品已更新' : '物品已创建', 'success');
            closeModal();
            loadItems();
        } else {
            showToast(result.message || '保存失败', 'error');
        }
    } catch (error) {
        showToast('保存物品失败', 'error');
    }
}

/**
 * 删除物品
 */
async function deleteItem(itemId) {
    if (!confirm(`确定要删除物品 "${itemId}" 吗？`)) return;
    
    try {
        const result = await api(`/items?id=${itemId}`, { method: 'DELETE' });
        if (result.success) {
            showToast('物品已删除', 'success');
            loadItems();
        } else {
            showToast(result.message || '删除失败', 'error');
        }
    } catch (error) {
        showToast('删除物品失败', 'error');
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

// ==================== 性格管理 ====================

/**
 * 获取属性名称映射
 */
function getStatName(stat) {
    const statNames = {
        hp: '生命',
        attack: '攻击',
        defense: '防御',
        sp_attack: '特攻',
        sp_defense: '特防',
        speed: '速度'
    };
    return statNames[stat] || stat || '无';
}

/**
 * 获取属性选项HTML
 */
function getStatOptions(selected = '') {
    const stats = [
        { value: '', label: '无' },
        { value: 'hp', label: '生命' },
        { value: 'attack', label: '攻击' },
        { value: 'defense', label: '防御' },
        { value: 'sp_attack', label: '特攻' },
        { value: 'sp_defense', label: '特防' },
        { value: 'speed', label: '速度' }
    ];
    return stats.map(s => 
        `<option value="${s.value}" ${s.value === selected ? 'selected' : ''}>${s.label}</option>`
    ).join('');
}

async function loadNatures() {
    try {
        const result = await api('/natures');
        if (result.success) {
            renderNaturesTable(result.data);
        }
    } catch (error) {
        showToast('加载性格列表失败', 'error');
    }
}

function renderNaturesTable(natures) {
    const tbody = document.getElementById('natures-table-body');

    if (!natures || Object.keys(natures).length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state">
                    <div class="empty-icon">🎭</div>
                    <p>暂无性格数据</p>
                </td>
            </tr>
        `;
        return;
    }

    // 计算总权重用于显示概率
    const totalWeight = Object.values(natures).reduce((sum, n) => sum + (n.weight || 10), 0);

    tbody.innerHTML = Object.entries(natures).map(([key, n]) => {
        const buffStr = n.buff_stat ? `${getStatName(n.buff_stat)} +${n.buff_percent || 10}%` : '-';
        const debuffStr = n.debuff_stat ? `${getStatName(n.debuff_stat)} -${n.debuff_percent || 10}%` : '-';
        const weight = n.weight || 10;
        const probability = ((weight / totalWeight) * 100).toFixed(1);
        
        return `
        <tr>
            <td><code>${n.id || key}</code></td>
            <td>${n.name}</td>
            <td style="color: #22c55e;">${buffStr}</td>
            <td style="color: #ef4444;">${debuffStr}</td>
            <td><span class="weight-badge">${weight}</span> <small style="color:#888;">(${probability}%)</small></td>
            <td>${n.description || '-'}</td>
            <td class="table-actions">
                <button class="btn btn-secondary btn-small" onclick="editNature('${n.id || key}')">编辑</button>
                <button class="btn btn-danger btn-small" onclick="deleteNature('${n.id || key}')">删除</button>
            </td>
        </tr>
    `}).join('');
}

function showNatureModal(natureId = null) {
    const isEdit = !!natureId;
    const title = isEdit ? '编辑性格' : '添加性格';

    const content = `
        <form id="nature-form">
            <div class="form-row">
                <div class="form-group">
                    <label>ID (英文标识) *</label>
                    <input type="text" name="id" required ${isEdit ? 'readonly style="background:#f0f0f0;"' : ''} placeholder="如: brave, timid">
                </div>
                <div class="form-group">
                    <label>名称 *</label>
                    <input type="text" name="name" required placeholder="如: 勇敢, 胆小">
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>增益属性</label>
                    <select name="buff_stat">
                        ${getStatOptions()}
                    </select>
                </div>
                <div class="form-group">
                    <label>增益百分比</label>
                    <input type="number" name="buff_percent" value="10" min="0" max="100">
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>减益属性</label>
                    <select name="debuff_stat">
                        ${getStatOptions()}
                    </select>
                </div>
                <div class="form-group">
                    <label>减益百分比</label>
                    <input type="number" name="debuff_percent" value="10" min="0" max="100">
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label>生成权重</label>
                    <input type="number" name="weight" value="10" min="1" max="100">
                    <small style="color:#888;">权重越高，随机到的概率越大</small>
                </div>
            </div>
            
            <div class="form-group">
                <label>描述</label>
                <input type="text" name="description" placeholder="如: 攻击+10%, 速度-10%">
            </div>
        </form>
    `;

    showModal(title, content, async () => {
        await saveNature(isEdit);
    });

    if (isEdit) {
        loadNatureData(natureId);
    }
}

async function loadNatureData(natureId) {
    try {
        const result = await api(`/natures/detail?id=${encodeURIComponent(natureId)}`);
        if (result.success) {
            const n = result.data;
            const form = document.getElementById('nature-form');
            form.querySelector('[name="id"]').value = n.id || natureId;
            form.querySelector('[name="name"]').value = n.name || '';
            form.querySelector('[name="buff_stat"]').value = n.buff_stat || '';
            form.querySelector('[name="buff_percent"]').value = n.buff_percent || 10;
            form.querySelector('[name="debuff_stat"]').value = n.debuff_stat || '';
            form.querySelector('[name="debuff_percent"]').value = n.debuff_percent || 10;
            form.querySelector('[name="weight"]').value = n.weight || 10;
            form.querySelector('[name="description"]').value = n.description || '';
            
            // 保存原始ID
            form.dataset.originalId = n.id || natureId;
        }
    } catch (error) {
        showToast('加载性格数据失败', 'error');
    }
}

async function saveNature(isEdit) {
    const form = document.getElementById('nature-form');
    const formData = new FormData(form);
    const originalId = form.dataset.originalId;
    const natureId = formData.get('id');
    
    // 构建数据，处理空值
    const buffStat = formData.get('buff_stat');
    const debuffStat = formData.get('debuff_stat');
    
    const data = {
        id: natureId,
        name: formData.get('name'),
        buff_stat: buffStat || null,
        buff_percent: buffStat ? parseInt(formData.get('buff_percent')) || 10 : 0,
        debuff_stat: debuffStat || null,
        debuff_percent: debuffStat ? parseInt(formData.get('debuff_percent')) || 10 : 0,
        weight: parseInt(formData.get('weight')) || 10,
        description: formData.get('description') || ''
    };

    // 自动生成描述（如果为空）
    if (!data.description) {
        const parts = [];
        if (data.buff_stat) parts.push(`${getStatName(data.buff_stat)}+${data.buff_percent}%`);
        if (data.debuff_stat) parts.push(`${getStatName(data.debuff_stat)}-${data.debuff_percent}%`);
        data.description = parts.length > 0 ? parts.join(', ') : '性格平衡，无加成无减益';
    }

    try {
        const endpoint = isEdit
            ? `/natures/update?id=${encodeURIComponent(originalId)}`
            : '/natures';
        const method = isEdit ? 'PUT' : 'POST';
        const result = await api(endpoint, {
            method: method,
            body: JSON.stringify(data)
        });
        if (result.success) {
            closeModal();
            showToast(isEdit ? '更新成功' : '创建成功', 'success');
            loadNatures();
        } else {
            showToast(result.message || '保存失败', 'error');
        }
    } catch (error) {
        showToast('保存失败', 'error');
    }
}

function editNature(natureId) {
    showNatureModal(natureId);
}

async function deleteNature(natureId) {
    if (!confirm(`确定要删除性格 "${natureId}" 吗？\n\n注意：已有该性格的精灵不会受影响，但新生成的精灵将无法获得此性格。`)) {
        return;
    }
    try {
        const result = await api(`/natures/delete?id=${encodeURIComponent(natureId)}`, { method: 'DELETE' });
        if (result.success) {
            showToast('删除成功', 'success');
            loadNatures();
        } else {
            showToast(result.message || '删除失败', 'error');
        }
    } catch (error) {
        showToast('删除失败', 'error');
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
// 性格管理函数
window.showNatureModal = showNatureModal;
window.editNature = editNature;
window.deleteNature = deleteNature;



window.showMonsterModal = showMonsterModal;
window.editMonster = editMonster;
window.deleteMonster = deleteMonster;

window.showSkillModal = showSkillModal;
window.editSkill = editSkill;
window.deleteSkill = deleteSkill;
window.addSkillEffect = addSkillEffect;
window.removeSkillEffect = removeSkillEffect;
window.onEffectTypeChange = onEffectTypeChange;

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

