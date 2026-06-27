import { computed, nextTick, onMounted, ref, watch } from 'vue';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import { api, upload } from './api';
const md = new MarkdownIt({ breaks: true, linkify: true });
const render = (value) => DOMPurify.sanitize(md.render(value || ''));
const user = ref(null), authMode = ref('login'), username = ref(''), password = ref(''), error = ref('');
const conversations = ref([]), activeId = ref(''), messages = ref([]), input = ref(''), sending = ref(false), aborter = ref(null);
const settingsOpen = ref(false), settingsTab = ref('model'), notice = ref(''), userMenuOpen = ref(false);
const sidebarCollapsed = ref(false), convMenuId = ref(''), renameId = ref(''), renameTitle = ref('');
const confirmDialog = ref({ show: false, title: '', message: '', onConfirm: () => { } });
const menuPos = ref({ top: 0, left: 0 });
function openConvMenu(id, ev) { const rect = ev.target.getBoundingClientRect(); menuPos.value = { top: rect.top, left: rect.right + 4 }; convMenuId.value = convMenuId.value === id ? '' : id; }
const model = ref({ api_key: '', base_url: 'https://ark.cn-beijing.volces.com/api/v3', model: 'deepseek-v4-flash-260425', api_key_masked: '' });
const modelConfigured = ref(false), connectionStatus = ref('idle');
const showApiKey = ref(false), apiKeyLoaded = ref(false), connectionMessage = ref('');
const confidential = ref([]), publicEntries = ref([]);
const confForm = ref({ text: '', category: '', confidential_level: 'high', summary: '', enabled: true });
const confParaphrases = ref([]), confKeywords = ref([]), confNegatives = ref([]);
const newParaphrase = ref(''), newKeyword = ref(''), newNegative = ref('');
const showConfAdvanced = ref(false);
const confUnlocked = ref(false), confUnlockError = ref(''), confUnlockPassword = ref(''), pubForm = ref({ entity_type: 'phone', value: '', label: '', enabled: true });
const chatTitle = computed(() => conversations.value.find(x => x.id === activeId.value)?.title || '新对话');
async function boot() { try {
    user.value = await api('/auth/me');
    await Promise.all([loadConversations(), loadModelConfig()]);
}
catch {
    user.value = null;
} }
async function authenticate() { error.value = ''; try {
    user.value = await api(`/auth/${authMode.value}`, { method: 'POST', body: JSON.stringify({ username: username.value, password: password.value }) });
    await Promise.all([loadConversations(), loadModelConfig()]);
}
catch (e) {
    error.value = e.message;
} }
async function logout() { await api('/auth/logout', { method: 'POST' }); user.value = null; conversations.value = []; messages.value = []; }
async function loadConversations() { conversations.value = await api('/conversations'); if (conversations.value.length && !activeId.value)
    await openConversation(conversations.value[0].id); }
async function createConversation() { const item = await api('/conversations', { method: 'POST', body: JSON.stringify({ title: '新对话' }) }); conversations.value.unshift(item); await openConversation(item.id); }
async function openConversation(id) { activeId.value = id; messages.value = await api(`/conversations/${id}/messages`); await scrollBottom(); }
async function removeConversation(id) { confirmDialog.value = { show: true, title: '删除对话', message: '确定要删除这个对话吗？此操作不可撤销。', onConfirm: async () => { await api(`/conversations/${id}`, { method: 'DELETE' }); if (activeId.value === id) {
        activeId.value = '';
        messages.value = [];
    } await loadConversations(); } }; }
function startRename(item) { renameId.value = item.id; renameTitle.value = item.title; convMenuId.value = ''; }
async function submitRename() { if (!renameTitle.value.trim())
    return; await api(`/conversations/${renameId.value}`, { method: 'PATCH', body: JSON.stringify({ title: renameTitle.value.trim() }) }); renameId.value = ''; await loadConversations(); }
async function scrollBottom() { await nextTick(); document.querySelector('.messages')?.scrollTo({ top: 999999, behavior: 'smooth' }); }
function decisionFor(index) { const item = messages.value[index]; if (item.role !== 'assistant')
    return null; const previous = messages.value.slice(0, index).reverse().find(x => x.role === 'user' && x.action); if (item.action)
    return { ...item, safe_content: item.safe_content || previous?.safe_content }; return null; }
async function copyMessage(content) { await navigator.clipboard.writeText(content); notice.value = '已复制回复'; }
async function regenerate(index) { const previous = messages.value.slice(0, index).reverse().find(x => x.role === 'user'); if (!previous || sending.value)
    return; input.value = previous.content; await send(); }
async function send() {
    const content = input.value.trim();
    if (!content || sending.value)
        return;
    if (!modelConfigured.value) {
        notice.value = '请先配置模型后再发送消息';
        await openSettings('model');
        return;
    }
    if (!activeId.value)
        await createConversation();
    input.value = '';
    sending.value = true;
    const local = { id: crypto.randomUUID(), role: 'user', content, risk_types: [], status: 'complete' };
    const assistant = { id: crypto.randomUUID(), role: 'assistant', content: '', risk_types: [], status: 'thinking' };
    messages.value.push(local, assistant);
    await scrollBottom();
    aborter.value = new AbortController();
    try {
        const response = await fetch(`/api/conversations/${activeId.value}/messages/stream`, { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }), signal: aborter.value.signal });
        if (!response.ok)
            throw new Error((await response.json()).detail || '发送失败');
        const reader = response.body.getReader(), decoder = new TextDecoder();
        let buffer = '';
        while (true) {
            const { done, value } = await reader.read();
            if (done)
                break;
            buffer += decoder.decode(value, { stream: true });
            const frames = buffer.split('\n\n');
            buffer = frames.pop() || '';
            for (const frame of frames) {
                const lines = frame.split('\n'), event = lines.find(x => x.startsWith('event:'))?.slice(6).trim(), dataLine = lines.find(x => x.startsWith('data:'))?.slice(5).trim();
                if (!event || !dataLine)
                    continue;
                const data = JSON.parse(dataLine);
                if (event === 'decision') {
                    local.id = data.message_id;
                    assistant.action = data.action;
                    assistant.risk_score = data.risk_score;
                    assistant.guardrail_message = data.message;
                    assistant.safe_content = data.safe_input;
                    assistant.risk_types = data.risk_types || [];
                }
                if (event === 'delta') {
                    assistant.status = 'streaming';
                    assistant.content += data.text;
                    await scrollBottom();
                }
                if (event === 'complete') {
                    assistant.id = data.message_id;
                    assistant.status = 'complete';
                    if (data.blocked && !assistant.content)
                        assistant.content = assistant.guardrail_message || '该内容已被安全策略阻止，未发送给模型。';
                }
                if (event === 'error') {
                    assistant.status = 'error';
                    assistant.content = data.message;
                    notice.value = data.message;
                }
            }
        }
        await loadConversations();
    }
    catch (e) {
        if (e.name !== 'AbortError') {
            assistant.status = 'error';
            assistant.content = e.message;
            notice.value = e.message;
        }
        else {
            assistant.status = 'interrupted';
            assistant.content = assistant.content || '已停止生成';
        }
    }
    finally {
        sending.value = false;
        aborter.value = null;
    }
}
function stop() { aborter.value?.abort(); sending.value = false; }
async function openSettings(tab = 'model') { settingsTab.value = tab; settingsOpen.value = true; confUnlocked.value = false; confidential.value = []; await refreshSettings(); }
async function loadModelConfig(loadSecret = false) { const x = await api('/settings/model'); modelConfigured.value = !!x.configured; apiKeyLoaded.value = false; if (x.configured) {
    model.value = { api_key: '', api_key_masked: x.api_key_masked, base_url: x.base_url, model: x.model };
    if (loadSecret) {
        const secret = await api('/settings/model/secret');
        model.value.api_key = secret.api_key;
        apiKeyLoaded.value = true;
    }
}
else {
    model.value.api_key = '';
    model.value.api_key_masked = '';
    apiKeyLoaded.value = true;
} showApiKey.value = false; connectionStatus.value = 'idle'; connectionMessage.value = ''; }
async function refreshSettings() {
    if (settingsTab.value === 'model')
        await loadModelConfig(true);
    if (settingsTab.value === 'confidential')
        confidential.value = await api('/libraries/confidential');
    if (settingsTab.value === 'public')
        publicEntries.value = await api('/libraries/public');
}
function modelPayload() { return { base_url: model.value.base_url, model: model.value.model, ...(model.value.api_key ? { api_key: model.value.api_key } : {}) }; }
async function saveModel() { try {
    if (modelConfigured.value && apiKeyLoaded.value && !model.value.api_key) {
        await api('/settings/model', { method: 'DELETE' });
        notice.value = '模型配置已删除';
        await loadModelConfig(true);
        return;
    }
    await api('/settings/model', { method: 'PUT', body: JSON.stringify(modelPayload()) });
    notice.value = '模型配置已保存';
    await loadModelConfig(true);
}
catch (e) {
    notice.value = e.message;
} }
async function testModel() { connectionStatus.value = 'testing'; connectionMessage.value = '正在连接模型服务…'; try {
    const result = await api('/settings/model/test', { method: 'POST', body: JSON.stringify(modelPayload()) });
    connectionStatus.value = 'ok';
    connectionMessage.value = result.message;
    notice.value = '模型连接正常';
}
catch (e) {
    connectionStatus.value = 'error';
    connectionMessage.value = e.message;
    notice.value = e.message;
} }
function removeFromList(arr, idx) { arr.splice(idx, 1); }
function addParaphrase() { const v = newParaphrase.value.trim(); if (v && !confParaphrases.value.includes(v)) {
    confParaphrases.value.push(v);
} newParaphrase.value = ''; }
function addKeyword() { const v = newKeyword.value.trim(); if (v && !confKeywords.value.includes(v)) {
    confKeywords.value.push(v);
} newKeyword.value = ''; }
function addNegative() { const v = newNegative.value.trim(); if (v && !confNegatives.value.includes(v)) {
    confNegatives.value.push(v);
} newNegative.value = ''; }
async function addConf() {
    const f = confForm.value;
    await api('/libraries/confidential', { method: 'POST', body: JSON.stringify({
            text: f.text,
            category: f.category || 'confidential',
            confidential_level: f.confidential_level || 'high',
            summary: f.summary || null,
            paraphrases: confParaphrases.value,
            negative_samples: confNegatives.value,
            keywords: confKeywords.value,
            enabled: true
        }) });
    confForm.value = { text: '', category: '', confidential_level: 'high', summary: '', enabled: true };
    confParaphrases.value = [];
    confKeywords.value = [];
    confNegatives.value = [];
    await refreshSettings();
}
async function unlockConf() {
    confUnlockError.value = '';
    try {
        await api('/auth/verify-password', { method: 'POST', body: JSON.stringify({ password: confUnlockPassword.value }) });
        confUnlocked.value = true;
        confidential.value = await api('/libraries/confidential');
    }
    catch (e) {
        confUnlockError.value = '密码错误';
    }
    confUnlockPassword.value = '';
}
function lockConf() { confUnlocked.value = false; confidential.value = []; }
async function addPublic() { await api('/libraries/public', { method: 'POST', body: JSON.stringify(pubForm.value) }); pubForm.value = { entity_type: 'phone', value: '', label: '', enabled: true }; await refreshSettings(); }
async function delEntry(kind, id) { await api(`/libraries/${kind}/${id}`, { method: 'DELETE' }); await refreshSettings(); }
async function importFile(kind, event) {
    const input = event.target;
    const file = input.files?.[0];
    if (!file)
        return;
    try {
        const x = await upload(`/libraries/${kind}/import`, file);
        notice.value = `已导入 ${x.imported_count} 条，失败 ${x.error_count} 条`;
        await refreshSettings();
    }
    catch (e) {
        notice.value = `导入失败: ${e.message}`;
    }
    finally {
        input.value = '';
    }
}
function downloadTemplate(kind) {
    const lines = kind === 'confidential'
        ? [JSON.stringify({ fact_text: "公司Q3营收预计增长30%", category: "财务数据", confidential_level: "high", summary: "Q3财务预测", paraphrases: ["第三季度收入预计提升三成", "Q3营收增长约30%"], negative_samples: ["今年Q2营收是多少？", "上市公司财报公开数据"], keywords: ["Q3", "营收", "增长", "财务预测"] })]
        : [JSON.stringify({ entity_type: "phone", value: "13800138000", label: "客服电话" }), JSON.stringify({ entity_type: "email", value: "support@example.com", label: "客服邮箱" })];
    const blob = new Blob([lines.join('\n') + '\n'], { type: 'application/jsonl' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = kind === 'confidential' ? '保密库模板.jsonl' : '公开库模板.jsonl';
    a.click();
    URL.revokeObjectURL(a.href);
}
let noticeTimer;
watch(notice, (v) => { clearTimeout(noticeTimer); if (v)
    noticeTimer = setTimeout(() => { notice.value = ''; }, 3000); });
onMounted(boot);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
if (!__VLS_ctx.user) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.main, __VLS_intrinsicElements.main)({
        ...{ class: "auth-page" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "auth-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "brand-mark" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.form, __VLS_intrinsicElements.form)({
        ...{ onSubmit: (__VLS_ctx.authenticate) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
        autocomplete: "username",
        required: true,
        minlength: "3",
    });
    (__VLS_ctx.username);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
        type: "password",
        autocomplete: "current-password",
        required: true,
        minlength: "8",
    });
    (__VLS_ctx.password);
    if (__VLS_ctx.error) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "error" },
        });
        (__VLS_ctx.error);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ class: "primary" },
    });
    (__VLS_ctx.authMode === 'login' ? '登录' : '创建账号');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(!__VLS_ctx.user))
                    return;
                __VLS_ctx.authMode = __VLS_ctx.authMode === 'login' ? 'register' : 'login';
            } },
        ...{ class: "link" },
    });
    (__VLS_ctx.authMode === 'login' ? '没有账号？立即注册' : '已有账号？返回登录');
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.main, __VLS_intrinsicElements.main)({
        ...{ class: "workspace" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.aside, __VLS_intrinsicElements.aside)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.user))
                    return;
                __VLS_ctx.convMenuId = '';
                __VLS_ctx.renameId = '';
            } },
        ...{ class: (['sidebar', { collapsed: __VLS_ctx.sidebarCollapsed }]) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "logo" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.createConversation) },
        ...{ class: "new-chat" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "history" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    for (const [item] of __VLS_getVForSourceType((__VLS_ctx.conversations))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.user))
                        return;
                    __VLS_ctx.openConversation(item.id);
                } },
            key: (item.id),
            ...{ class: (['conversation', { active: item.id === __VLS_ctx.activeId }]) },
        });
        if (__VLS_ctx.renameId === item.id) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                ...{ onBlur: (__VLS_ctx.submitRename) },
                ...{ onKeydown: (__VLS_ctx.submitRename) },
                ...{ onKeydown: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.renameId === item.id))
                            return;
                        __VLS_ctx.renameId = '';
                    } },
                ...{ onClick: () => { } },
                ...{ class: "rename-input" },
            });
            (__VLS_ctx.renameTitle);
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.title);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!!(__VLS_ctx.renameId === item.id))
                            return;
                        __VLS_ctx.openConvMenu(item.id, $event);
                    } },
                ...{ class: "conv-menu-btn" },
            });
        }
        if (__VLS_ctx.convMenuId === item.id && __VLS_ctx.renameId !== item.id) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ onClick: () => { } },
                ...{ class: "conv-menu" },
                ...{ style: ({ position: 'fixed', top: __VLS_ctx.menuPos.top + 'px', left: __VLS_ctx.menuPos.left + 'px' }) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.convMenuId === item.id && __VLS_ctx.renameId !== item.id))
                            return;
                        __VLS_ctx.startRename(item);
                    } },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.convMenuId === item.id && __VLS_ctx.renameId !== item.id))
                            return;
                        __VLS_ctx.convMenuId = '';
                        __VLS_ctx.removeConversation(item.id);
                    } },
            });
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "profile" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.user))
                    return;
                __VLS_ctx.openSettings();
            } },
        ...{ class: "settings-btn" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.user))
                    return;
                __VLS_ctx.userMenuOpen = false;
                __VLS_ctx.convMenuId = '';
            } },
        ...{ class: "chat" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.user))
                    return;
                __VLS_ctx.sidebarCollapsed = !__VLS_ctx.sidebarCollapsed;
            } },
        ...{ class: "sidebar-toggle" },
        title: (__VLS_ctx.sidebarCollapsed ? '展开侧栏' : '折叠侧栏'),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        viewBox: "0 0 24 24",
        width: "18",
        height: "18",
        fill: "none",
        stroke: "currentColor",
        'stroke-width': "2",
        'stroke-linecap': "round",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.line)({
        x1: "3",
        y1: "6",
        x2: "21",
        y2: "6",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.line)({
        x1: "3",
        y1: "12",
        x2: "21",
        y2: "12",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.line)({
        x1: "3",
        y1: "18",
        x2: "21",
        y2: "18",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    (__VLS_ctx.chatTitle);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "header-right" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.user))
                    return;
                __VLS_ctx.openSettings('model');
            } },
        ...{ class: (['model-status', { healthy: __VLS_ctx.modelConfigured && __VLS_ctx.connectionStatus !== 'error' }]) },
        title: (__VLS_ctx.modelConfigured ? (__VLS_ctx.connectionStatus === 'error' ? '模型连接异常' : '模型配置正常') : '未配置模型'),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "status-dot" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
    (__VLS_ctx.modelConfigured ? __VLS_ctx.model.model : '未配置模型');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: () => { } },
        ...{ class: "account-menu" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.user))
                    return;
                __VLS_ctx.userMenuOpen = !__VLS_ctx.userMenuOpen;
            } },
        ...{ class: "account-trigger" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        viewBox: "0 0 24 24",
        width: "17",
        height: "17",
        fill: "none",
        stroke: "currentColor",
        'stroke-width': "2",
        'stroke-linecap': "round",
        'stroke-linejoin': "round",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
        d: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.circle)({
        cx: "12",
        cy: "7",
        r: "4",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.user.username);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        viewBox: "0 0 24 24",
        width: "14",
        height: "14",
        fill: "none",
        stroke: "currentColor",
        'stroke-width': "2",
        'stroke-linecap': "round",
        'stroke-linejoin': "round",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
        d: "m6 9 6 6 6-6",
    });
    if (__VLS_ctx.userMenuOpen) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "account-dropdown" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "account-identity" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.user.username);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.user))
                        return;
                    if (!(__VLS_ctx.userMenuOpen))
                        return;
                    __VLS_ctx.userMenuOpen = false;
                    __VLS_ctx.logout();
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
            viewBox: "0 0 24 24",
            width: "16",
            height: "16",
            fill: "none",
            stroke: "currentColor",
            'stroke-width': "2",
            'stroke-linecap': "round",
            'stroke-linejoin': "round",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
            d: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.polyline)({
            points: "16 17 21 12 16 7",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.line)({
            x1: "21",
            y1: "12",
            x2: "9",
            y2: "12",
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "messages" },
    });
    if (!__VLS_ctx.messages.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "welcome" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    }
    for (const [item, index] of __VLS_getVForSourceType((__VLS_ctx.messages))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.article, __VLS_intrinsicElements.article)({
            key: (item.id),
            ...{ class: (['message', item.role]) },
        });
        if (item.role === 'assistant' && __VLS_ctx.decisionFor(index)) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: (['decision', __VLS_ctx.decisionFor(index)?.action]) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            (__VLS_ctx.decisionFor(index)?.action === 'pass' ? '✓ 安全通过' : __VLS_ctx.decisionFor(index)?.action === 'redact' ? '◐ 已脱敏处理' : '⊘ 已阻止发送');
            if (__VLS_ctx.decisionFor(index)?.risk_score != null) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (Math.round((__VLS_ctx.decisionFor(index)?.risk_score || 0) * 100));
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            (__VLS_ctx.decisionFor(index)?.guardrail_message);
            if (__VLS_ctx.decisionFor(index)?.action === 'redact') {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.details, __VLS_intrinsicElements.details)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.summary, __VLS_intrinsicElements.summary)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({});
                (__VLS_ctx.decisionFor(index)?.safe_content);
            }
        }
        if (item.role === 'user') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "bubble" },
            });
            (item.content);
        }
        else if (item.status === 'thinking') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "thinking" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.action ? '正在思考' : '正在进行安全检测');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({});
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "answer" },
            });
            __VLS_asFunctionalDirective(__VLS_directives.vHtml)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.render(item.content)) }, null, null);
        }
        if (item.role === 'assistant' && item.status === 'complete' && item.content) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "message-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(item.role === 'assistant' && item.status === 'complete' && item.content))
                            return;
                        __VLS_ctx.copyMessage(item.content);
                    } },
                title: "复制回复",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(item.role === 'assistant' && item.status === 'complete' && item.content))
                            return;
                        __VLS_ctx.regenerate(index);
                    } },
                title: "重新生成",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.footer, __VLS_intrinsicElements.footer)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: (['composer', { disabled: !__VLS_ctx.modelConfigured }]) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.textarea, __VLS_intrinsicElements.textarea)({
        ...{ onKeydown: (__VLS_ctx.send) },
        value: (__VLS_ctx.input),
        placeholder: (__VLS_ctx.modelConfigured ? '输入消息，Enter 发送，Shift+Enter 换行' : '请先在设置中配置模型'),
        disabled: (__VLS_ctx.sending || !__VLS_ctx.modelConfigured),
    });
    if (__VLS_ctx.sending) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.stop) },
            ...{ class: "stop" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.send) },
            ...{ class: "send" },
            disabled: (!__VLS_ctx.modelConfigured),
            title: "发送消息",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
            viewBox: "0 0 24 24",
            'aria-hidden': "true",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
            d: "M4 12h14m-6-6 6 6-6 6",
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
    (__VLS_ctx.modelConfigured ? '模型输出可能存在误差，重要信息请核实' : '配置 API Key、模型地址和模型名称后才能开始对话');
    if (__VLS_ctx.settingsOpen) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.user))
                        return;
                    if (!(__VLS_ctx.settingsOpen))
                        return;
                    __VLS_ctx.settingsOpen = false;
                } },
            ...{ class: "modal" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
            ...{ class: "settings" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.user))
                        return;
                    if (!(__VLS_ctx.settingsOpen))
                        return;
                    __VLS_ctx.settingsOpen = false;
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.nav, __VLS_intrinsicElements.nav)({});
        for (const [tab] of __VLS_getVForSourceType((['model', 'confidential', 'public']))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        __VLS_ctx.settingsTab = tab;
                        __VLS_ctx.refreshSettings();
                    } },
                key: (tab),
                ...{ class: ({ active: __VLS_ctx.settingsTab === tab }) },
            });
            ({ model: '模型配置', confidential: '保密库', public: '公开库' }[tab]);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "panel" },
        });
        if (__VLS_ctx.settingsTab === 'model') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.form, __VLS_intrinsicElements.form)({
                ...{ onSubmit: (__VLS_ctx.saveModel) },
                ...{ class: "form" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "password-input" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                type: (__VLS_ctx.showApiKey ? 'text' : 'password'),
                required: (!__VLS_ctx.modelConfigured),
                placeholder: "输入 API Key",
                autocomplete: "new-password",
            });
            (__VLS_ctx.model.api_key);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'model'))
                            return;
                        __VLS_ctx.showApiKey = !__VLS_ctx.showApiKey;
                    } },
                type: "button",
                title: (__VLS_ctx.showApiKey ? '隐藏 API Key' : '显示 API Key'),
            });
            (__VLS_ctx.showApiKey ? '◉' : '👁');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                required: true,
            });
            (__VLS_ctx.model.base_url);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                required: true,
            });
            (__VLS_ctx.model.model);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "connection-result" },
                ...{ class: (__VLS_ctx.connectionStatus) },
            });
            if (__VLS_ctx.connectionMessage) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (__VLS_ctx.connectionMessage);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (__VLS_ctx.testModel) },
                type: "button",
                disabled: (__VLS_ctx.connectionStatus === 'testing' || !__VLS_ctx.model.api_key),
            });
            (__VLS_ctx.connectionStatus === 'testing' ? '测试中…' : '测试连接');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ class: "primary" },
            });
        }
        if (__VLS_ctx.settingsTab === 'confidential') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-header" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'confidential'))
                            return;
                        __VLS_ctx.downloadTemplate('confidential');
                    } },
                ...{ class: "link-btn" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
                ...{ class: "upload-btn" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                ...{ onChange: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'confidential'))
                            return;
                        __VLS_ctx.importFile('confidential', $event);
                    } },
                type: "file",
                accept: ".jsonl",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "section-desc" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.form, __VLS_intrinsicElements.form)({
                ...{ onSubmit: (__VLS_ctx.addConf) },
                ...{ class: "conf-form" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
                ...{ class: "field-label" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "required" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.textarea, __VLS_intrinsicElements.textarea)({
                value: (__VLS_ctx.confForm.text),
                placeholder: "需要保护的机密信息，建议一句话描述一个事实，如：公司Q3营收预计增长30%",
                required: true,
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "form-row" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "field" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
                ...{ class: "field-label" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
                value: (__VLS_ctx.confForm.category),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "财务数据",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "产品规划",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "客户信息",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "源代码",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "商业战略",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "人事信息",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "技术机密",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "法务",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "其他",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "field" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
                ...{ class: "field-label" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "level-buttons" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'confidential'))
                            return;
                        __VLS_ctx.confForm.confidential_level = 'high';
                    } },
                type: "button",
                ...{ class: (['level-btn', { active: __VLS_ctx.confForm.confidential_level === 'high' }]) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'confidential'))
                            return;
                        __VLS_ctx.confForm.confidential_level = 'medium';
                    } },
                type: "button",
                ...{ class: (['level-btn', { active: __VLS_ctx.confForm.confidential_level === 'medium' }]) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'confidential'))
                            return;
                        __VLS_ctx.confForm.confidential_level = 'low';
                    } },
                type: "button",
                ...{ class: (['level-btn', { active: __VLS_ctx.confForm.confidential_level === 'low' }]) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
                ...{ class: "field-label" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "tag-list" },
            });
            for (const [p, i] of __VLS_getVForSourceType((__VLS_ctx.confParaphrases))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (i),
                    ...{ class: "tag-item" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (p);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.user))
                                return;
                            if (!(__VLS_ctx.settingsOpen))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'confidential'))
                                return;
                            __VLS_ctx.removeFromList(__VLS_ctx.confParaphrases, i);
                        } },
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "tag-input wide" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                ...{ onKeydown: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'confidential'))
                            return;
                        __VLS_ctx.addParaphrase();
                    } },
                placeholder: "用不同说法描述同一事实，按回车添加，提高检测命中率",
            });
            (__VLS_ctx.newParaphrase);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'confidential'))
                            return;
                        __VLS_ctx.addParaphrase();
                    } },
                type: "button",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'confidential'))
                            return;
                        __VLS_ctx.showConfAdvanced = !__VLS_ctx.showConfAdvanced;
                    } },
                type: "button",
                ...{ class: "toggle-advanced" },
            });
            (__VLS_ctx.showConfAdvanced ? '▲ 收起高级配置' : '▼ 高级配置');
            if (__VLS_ctx.showConfAdvanced) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "advanced-section" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "field" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
                    ...{ class: "field-label" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                    placeholder: "一句话概括这个事实，如：Q3财务预测",
                });
                (__VLS_ctx.confForm.summary);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "field" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
                    ...{ class: "field-label" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "tag-list" },
                });
                for (const [k, i] of __VLS_getVForSourceType((__VLS_ctx.confKeywords))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                        key: (i),
                        ...{ class: "tag-item" },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                    (k);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                        ...{ onClick: (...[$event]) => {
                                if (!!(!__VLS_ctx.user))
                                    return;
                                if (!(__VLS_ctx.settingsOpen))
                                    return;
                                if (!(__VLS_ctx.settingsTab === 'confidential'))
                                    return;
                                if (!(__VLS_ctx.showConfAdvanced))
                                    return;
                                __VLS_ctx.removeFromList(__VLS_ctx.confKeywords, i);
                            } },
                    });
                }
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "tag-input wide" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                    ...{ onKeydown: (...[$event]) => {
                            if (!!(!__VLS_ctx.user))
                                return;
                            if (!(__VLS_ctx.settingsOpen))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'confidential'))
                                return;
                            if (!(__VLS_ctx.showConfAdvanced))
                                return;
                            __VLS_ctx.addKeyword();
                        } },
                    placeholder: "输入关键词（便于检索），按回车添加",
                });
                (__VLS_ctx.newKeyword);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.user))
                                return;
                            if (!(__VLS_ctx.settingsOpen))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'confidential'))
                                return;
                            if (!(__VLS_ctx.showConfAdvanced))
                                return;
                            __VLS_ctx.addKeyword();
                        } },
                    type: "button",
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "field" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "label-row" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
                    ...{ class: "field-label" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "field-hint inline" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "tag-list" },
                });
                for (const [n, i] of __VLS_getVForSourceType((__VLS_ctx.confNegatives))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                        key: (i),
                        ...{ class: "tag-item" },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                    (n);
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                        ...{ onClick: (...[$event]) => {
                                if (!!(!__VLS_ctx.user))
                                    return;
                                if (!(__VLS_ctx.settingsOpen))
                                    return;
                                if (!(__VLS_ctx.settingsTab === 'confidential'))
                                    return;
                                if (!(__VLS_ctx.showConfAdvanced))
                                    return;
                                __VLS_ctx.removeFromList(__VLS_ctx.confNegatives, i);
                            } },
                    });
                }
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "tag-input wide" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                    ...{ onKeydown: (...[$event]) => {
                            if (!!(!__VLS_ctx.user))
                                return;
                            if (!(__VLS_ctx.settingsOpen))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'confidential'))
                                return;
                            if (!(__VLS_ctx.showConfAdvanced))
                                return;
                            __VLS_ctx.addNegative();
                        } },
                    placeholder: "输入反例，按回车添加",
                });
                (__VLS_ctx.newNegative);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.user))
                                return;
                            if (!(__VLS_ctx.settingsOpen))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'confidential'))
                                return;
                            if (!(__VLS_ctx.showConfAdvanced))
                                return;
                            __VLS_ctx.addNegative();
                        } },
                    type: "button",
                });
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "form-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ class: "primary" },
                type: "submit",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "vault-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "vault-header" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            if (__VLS_ctx.confUnlocked) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.user))
                                return;
                            if (!(__VLS_ctx.settingsOpen))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'confidential'))
                                return;
                            if (!(__VLS_ctx.confUnlocked))
                                return;
                            __VLS_ctx.lockConf();
                        } },
                    ...{ class: "link-btn" },
                });
            }
            if (!__VLS_ctx.confUnlocked) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "vault-lock" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                    ...{ onKeydown: (...[$event]) => {
                            if (!!(!__VLS_ctx.user))
                                return;
                            if (!(__VLS_ctx.settingsOpen))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'confidential'))
                                return;
                            if (!(!__VLS_ctx.confUnlocked))
                                return;
                            __VLS_ctx.unlockConf();
                        } },
                    ...{ onInput: (...[$event]) => {
                            if (!!(!__VLS_ctx.user))
                                return;
                            if (!(__VLS_ctx.settingsOpen))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'confidential'))
                                return;
                            if (!(!__VLS_ctx.confUnlocked))
                                return;
                            __VLS_ctx.confUnlockError = '';
                        } },
                    type: "password",
                    placeholder: "输入密码查看保密库内容",
                });
                (__VLS_ctx.confUnlockPassword);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.user))
                                return;
                            if (!(__VLS_ctx.settingsOpen))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'confidential'))
                                return;
                            if (!(!__VLS_ctx.confUnlocked))
                                return;
                            __VLS_ctx.unlockConf();
                        } },
                    ...{ class: "primary" },
                });
                if (__VLS_ctx.confUnlockError) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "error" },
                    });
                    (__VLS_ctx.confUnlockError);
                }
            }
            else {
                if (!__VLS_ctx.confidential.length) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                        ...{ class: "vault-empty" },
                    });
                }
                else {
                    for (const [x] of __VLS_getVForSourceType((__VLS_ctx.confidential))) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                            ...{ class: "entry" },
                            key: (x.id),
                        });
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
                        (x.category || '未分类');
                        (x.confidential_level || 'high');
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                        (x.text);
                        if (x.summary) {
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.small, __VLS_intrinsicElements.small)({});
                            (x.summary);
                        }
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                            ...{ onClick: (...[$event]) => {
                                    if (!!(!__VLS_ctx.user))
                                        return;
                                    if (!(__VLS_ctx.settingsOpen))
                                        return;
                                    if (!(__VLS_ctx.settingsTab === 'confidential'))
                                        return;
                                    if (!!(!__VLS_ctx.confUnlocked))
                                        return;
                                    if (!!(!__VLS_ctx.confidential.length))
                                        return;
                                    __VLS_ctx.delEntry('confidential', x.id);
                                } },
                        });
                    }
                }
            }
        }
        if (__VLS_ctx.settingsTab === 'public') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-header" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "section-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'public'))
                            return;
                        __VLS_ctx.downloadTemplate('public');
                    } },
                ...{ class: "link-btn" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
                ...{ class: "upload-btn" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                ...{ onChange: (...[$event]) => {
                        if (!!(!__VLS_ctx.user))
                            return;
                        if (!(__VLS_ctx.settingsOpen))
                            return;
                        if (!(__VLS_ctx.settingsTab === 'public'))
                            return;
                        __VLS_ctx.importFile('public', $event);
                    } },
                type: "file",
                accept: ".jsonl",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "section-desc" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.form, __VLS_intrinsicElements.form)({
                ...{ onSubmit: (__VLS_ctx.addPublic) },
                ...{ class: "inline-form compact" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
                value: (__VLS_ctx.pubForm.entity_type),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "phone",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "email",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "id_card",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                value: "bank_card",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                placeholder: "值，如 13800138000",
                required: true,
            });
            (__VLS_ctx.pubForm.value);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input, __VLS_intrinsicElements.input)({
                placeholder: "备注，如 客服电话",
            });
            (__VLS_ctx.pubForm.label);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ class: "primary" },
            });
            for (const [x] of __VLS_getVForSourceType((__VLS_ctx.publicEntries))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "entry" },
                    key: (x.id),
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.b, __VLS_intrinsicElements.b)({});
                (x.entity_type);
                (x.label);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
                (x.value);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.user))
                                return;
                            if (!(__VLS_ctx.settingsOpen))
                                return;
                            if (!(__VLS_ctx.settingsTab === 'public'))
                                return;
                            __VLS_ctx.delEntry('public', x.id);
                        } },
                });
            }
        }
    }
    if (__VLS_ctx.confirmDialog.show) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.user))
                        return;
                    if (!(__VLS_ctx.confirmDialog.show))
                        return;
                    __VLS_ctx.confirmDialog.show = false;
                } },
            ...{ class: "modal" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "confirm-dialog" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
        (__VLS_ctx.confirmDialog.title);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (__VLS_ctx.confirmDialog.message);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "confirm-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.user))
                        return;
                    if (!(__VLS_ctx.confirmDialog.show))
                        return;
                    __VLS_ctx.confirmDialog.show = false;
                } },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.user))
                        return;
                    if (!(__VLS_ctx.confirmDialog.show))
                        return;
                    __VLS_ctx.confirmDialog.onConfirm();
                    __VLS_ctx.confirmDialog.show = false;
                } },
            ...{ class: "danger" },
        });
    }
    const __VLS_0 = {}.Transition;
    /** @type {[typeof __VLS_components.Transition, typeof __VLS_components.Transition, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        name: "toast",
    }));
    const __VLS_2 = __VLS_1({
        name: "toast",
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    __VLS_3.slots.default;
    if (__VLS_ctx.notice) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.user))
                        return;
                    if (!(__VLS_ctx.notice))
                        return;
                    __VLS_ctx.notice = '';
                } },
            ...{ class: "toast" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.notice);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({});
    }
    var __VLS_3;
}
/** @type {__VLS_StyleScopedClasses['auth-page']} */ ;
/** @type {__VLS_StyleScopedClasses['auth-card']} */ ;
/** @type {__VLS_StyleScopedClasses['brand-mark']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['link']} */ ;
/** @type {__VLS_StyleScopedClasses['workspace']} */ ;
/** @type {__VLS_StyleScopedClasses['logo']} */ ;
/** @type {__VLS_StyleScopedClasses['new-chat']} */ ;
/** @type {__VLS_StyleScopedClasses['history']} */ ;
/** @type {__VLS_StyleScopedClasses['rename-input']} */ ;
/** @type {__VLS_StyleScopedClasses['conv-menu-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['conv-menu']} */ ;
/** @type {__VLS_StyleScopedClasses['profile']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chat']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['header-right']} */ ;
/** @type {__VLS_StyleScopedClasses['status-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['account-menu']} */ ;
/** @type {__VLS_StyleScopedClasses['account-trigger']} */ ;
/** @type {__VLS_StyleScopedClasses['account-dropdown']} */ ;
/** @type {__VLS_StyleScopedClasses['account-identity']} */ ;
/** @type {__VLS_StyleScopedClasses['messages']} */ ;
/** @type {__VLS_StyleScopedClasses['welcome']} */ ;
/** @type {__VLS_StyleScopedClasses['bubble']} */ ;
/** @type {__VLS_StyleScopedClasses['thinking']} */ ;
/** @type {__VLS_StyleScopedClasses['answer']} */ ;
/** @type {__VLS_StyleScopedClasses['message-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['stop']} */ ;
/** @type {__VLS_StyleScopedClasses['send']} */ ;
/** @type {__VLS_StyleScopedClasses['modal']} */ ;
/** @type {__VLS_StyleScopedClasses['settings']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['form']} */ ;
/** @type {__VLS_StyleScopedClasses['password-input']} */ ;
/** @type {__VLS_StyleScopedClasses['connection-result']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['section-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['link-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['section-desc']} */ ;
/** @type {__VLS_StyleScopedClasses['conf-form']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['required']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['field']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['field']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['level-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-list']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-item']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-input']} */ ;
/** @type {__VLS_StyleScopedClasses['wide']} */ ;
/** @type {__VLS_StyleScopedClasses['toggle-advanced']} */ ;
/** @type {__VLS_StyleScopedClasses['advanced-section']} */ ;
/** @type {__VLS_StyleScopedClasses['field']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['field']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-list']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-item']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-input']} */ ;
/** @type {__VLS_StyleScopedClasses['wide']} */ ;
/** @type {__VLS_StyleScopedClasses['field']} */ ;
/** @type {__VLS_StyleScopedClasses['label-row']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['field-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['inline']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-list']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-item']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-input']} */ ;
/** @type {__VLS_StyleScopedClasses['wide']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['vault-section']} */ ;
/** @type {__VLS_StyleScopedClasses['vault-header']} */ ;
/** @type {__VLS_StyleScopedClasses['link-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['vault-lock']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['vault-empty']} */ ;
/** @type {__VLS_StyleScopedClasses['entry']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['section-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['link-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['section-desc']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-form']} */ ;
/** @type {__VLS_StyleScopedClasses['compact']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['entry']} */ ;
/** @type {__VLS_StyleScopedClasses['modal']} */ ;
/** @type {__VLS_StyleScopedClasses['confirm-dialog']} */ ;
/** @type {__VLS_StyleScopedClasses['confirm-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['danger']} */ ;
/** @type {__VLS_StyleScopedClasses['toast']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            render: render,
            user: user,
            authMode: authMode,
            username: username,
            password: password,
            error: error,
            conversations: conversations,
            activeId: activeId,
            messages: messages,
            input: input,
            sending: sending,
            settingsOpen: settingsOpen,
            settingsTab: settingsTab,
            notice: notice,
            userMenuOpen: userMenuOpen,
            sidebarCollapsed: sidebarCollapsed,
            convMenuId: convMenuId,
            renameId: renameId,
            renameTitle: renameTitle,
            confirmDialog: confirmDialog,
            menuPos: menuPos,
            openConvMenu: openConvMenu,
            model: model,
            modelConfigured: modelConfigured,
            connectionStatus: connectionStatus,
            showApiKey: showApiKey,
            connectionMessage: connectionMessage,
            confidential: confidential,
            publicEntries: publicEntries,
            confForm: confForm,
            confParaphrases: confParaphrases,
            confKeywords: confKeywords,
            confNegatives: confNegatives,
            newParaphrase: newParaphrase,
            newKeyword: newKeyword,
            newNegative: newNegative,
            showConfAdvanced: showConfAdvanced,
            confUnlocked: confUnlocked,
            confUnlockError: confUnlockError,
            confUnlockPassword: confUnlockPassword,
            pubForm: pubForm,
            chatTitle: chatTitle,
            authenticate: authenticate,
            logout: logout,
            createConversation: createConversation,
            openConversation: openConversation,
            removeConversation: removeConversation,
            startRename: startRename,
            submitRename: submitRename,
            decisionFor: decisionFor,
            copyMessage: copyMessage,
            regenerate: regenerate,
            send: send,
            stop: stop,
            openSettings: openSettings,
            refreshSettings: refreshSettings,
            saveModel: saveModel,
            testModel: testModel,
            removeFromList: removeFromList,
            addParaphrase: addParaphrase,
            addKeyword: addKeyword,
            addNegative: addNegative,
            addConf: addConf,
            unlockConf: unlockConf,
            lockConf: lockConf,
            addPublic: addPublic,
            delEntry: delEntry,
            importFile: importFile,
            downloadTemplate: downloadTemplate,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
