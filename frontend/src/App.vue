<script setup lang="ts">
import {computed,nextTick,onMounted,ref,watch} from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import {api,upload} from './api'

type User={id:string;username:string}
type Conversation={id:string;title:string;created_at:string;updated_at:string}
type Message={id:string;role:string;content:string;safe_content?:string;action?:'pass'|'redact'|'block';risk_score?:number;guardrail_message?:string;risk_types:string[];status:string}
type Confidential={id:string;text:string;category:string;confidential_level:string;summary:string|null;paraphrases:string[];negative_samples:string[];keywords:string[];enabled:boolean}
type PublicEntry={id:string;entity_type:string;value:string;label:string;enabled:boolean}
const md=new MarkdownIt({breaks:true,linkify:true})
const render=(value:string)=>DOMPurify.sanitize(md.render(value||''))
const user=ref<User|null>(null),authMode=ref<'login'|'register'>('login'),username=ref(''),password=ref(''),error=ref('')
const conversations=ref<Conversation[]>([]),activeId=ref(''),messages=ref<Message[]>([]),input=ref(''),sending=ref(false),aborter=ref<AbortController|null>(null)
const settingsOpen=ref(false),settingsTab=ref<'model'|'confidential'|'public'>('model'),notice=ref(''),userMenuOpen=ref(false)
const sidebarCollapsed=ref(false),convMenuId=ref(''),renameId=ref(''),renameTitle=ref('')
const confirmDialog=ref<{show:boolean;title:string;message:string;onConfirm:()=>void}>({show:false,title:'',message:'',onConfirm:()=>{}})
const menuPos=ref({top:0,left:0})
function openConvMenu(id:string,ev:Event){const rect=(ev.target as HTMLElement).getBoundingClientRect();menuPos.value={top:rect.top,left:rect.right+4};convMenuId.value=convMenuId.value===id?'':id}
const model=ref({api_key:'',base_url:'https://ark.cn-beijing.volces.com/api/v3',model:'deepseek-v4-flash-260425',api_key_masked:''})
const modelConfigured=ref(false),connectionStatus=ref<'idle'|'testing'|'ok'|'error'>('idle')
const showApiKey=ref(false),apiKeyLoaded=ref(false),connectionMessage=ref('')
const confidential=ref<Confidential[]>([]),publicEntries=ref<PublicEntry[]>([])
const confForm=ref({text:'',category:'',confidential_level:'high',summary:'',enabled:true})
const confParaphrases=ref<string[]>([]),confKeywords=ref<string[]>([]),confNegatives=ref<string[]>([])
const newParaphrase=ref(''),newKeyword=ref(''),newNegative=ref('')
const showConfAdvanced=ref(false)
const confUnlocked=ref(false),confUnlockError=ref(''),confUnlockPassword=ref(''),pubForm=ref({entity_type:'phone',value:'',label:'',enabled:true})
const chatTitle=computed(()=>conversations.value.find(x=>x.id===activeId.value)?.title||'新对话')

async function boot(){try{user.value=await api('/auth/me');await Promise.all([loadConversations(),loadModelConfig()])}catch{user.value=null}}
async function authenticate(){error.value='';try{user.value=await api(`/auth/${authMode.value}`,{method:'POST',body:JSON.stringify({username:username.value,password:password.value})});await Promise.all([loadConversations(),loadModelConfig()])}catch(e:any){error.value=e.message}}
async function logout(){await api('/auth/logout',{method:'POST'});user.value=null;conversations.value=[];messages.value=[]}
async function loadConversations(){conversations.value=await api('/conversations');if(conversations.value.length&&!activeId.value)await openConversation(conversations.value[0].id)}
async function createConversation(){const item=await api<Conversation>('/conversations',{method:'POST',body:JSON.stringify({title:'新对话'})});conversations.value.unshift(item);await openConversation(item.id)}
async function openConversation(id:string){activeId.value=id;messages.value=await api(`/conversations/${id}/messages`);await scrollBottom()}
async function removeConversation(id:string){confirmDialog.value={show:true,title:'删除对话',message:'确定要删除这个对话吗？此操作不可撤销。',onConfirm:async()=>{await api(`/conversations/${id}`,{method:'DELETE'});if(activeId.value===id){activeId.value='';messages.value=[]}await loadConversations()}}}
function startRename(item:Conversation){renameId.value=item.id;renameTitle.value=item.title;convMenuId.value=''}
async function submitRename(){if(!renameTitle.value.trim())return;await api(`/conversations/${renameId.value}`,{method:'PATCH',body:JSON.stringify({title:renameTitle.value.trim()})});renameId.value='';await loadConversations()}
async function scrollBottom(){await nextTick();document.querySelector('.messages')?.scrollTo({top:999999,behavior:'smooth'})}
function decisionFor(index:number){const item=messages.value[index];if(item.role!=='assistant')return null;const previous=messages.value.slice(0,index).reverse().find(x=>x.role==='user'&&x.action);if(item.action)return {...item,safe_content:item.safe_content||previous?.safe_content};return null}
async function copyMessage(content:string){await navigator.clipboard.writeText(content);notice.value='已复制回复'}
async function regenerate(index:number){const previous=messages.value.slice(0,index).reverse().find(x=>x.role==='user');if(!previous||sending.value)return;input.value=previous.content;await send()}

async function send(){
  const content=input.value.trim();if(!content||sending.value)return;if(!modelConfigured.value){notice.value='请先配置模型后再发送消息';await openSettings('model');return}if(!activeId.value)await createConversation()
  input.value='';sending.value=true;const local:Message={id:crypto.randomUUID(),role:'user',content,risk_types:[],status:'complete'};const assistant:Message={id:crypto.randomUUID(),role:'assistant',content:'',risk_types:[],status:'thinking'};messages.value.push(local,assistant);await scrollBottom()
  aborter.value=new AbortController()
  try{
    const response=await fetch(`/api/conversations/${activeId.value}/messages/stream`,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({content}),signal:aborter.value.signal})
    if(!response.ok)throw new Error((await response.json()).detail||'发送失败')
    const reader=response.body!.getReader(),decoder=new TextDecoder();let buffer=''
    while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const frames=buffer.split('\n\n');buffer=frames.pop()||''
      for(const frame of frames){const lines=frame.split('\n'),event=lines.find(x=>x.startsWith('event:'))?.slice(6).trim(),dataLine=lines.find(x=>x.startsWith('data:'))?.slice(5).trim();if(!event||!dataLine)continue;const data=JSON.parse(dataLine)
        if(event==='decision'){local.id=data.message_id;assistant.action=data.action;assistant.risk_score=data.risk_score;assistant.guardrail_message=data.message;assistant.safe_content=data.safe_input;assistant.risk_types=data.risk_types||[]}
        if(event==='delta'){assistant.status='streaming';assistant.content+=data.text;await scrollBottom()}
        if(event==='complete'){assistant.id=data.message_id;assistant.status='complete';if(data.blocked&&!assistant.content)assistant.content=assistant.guardrail_message||'该内容已被安全策略阻止，未发送给模型。'}
        if(event==='error'){assistant.status='error';assistant.content=data.message;notice.value=data.message}
      }
    }
    await loadConversations()
  }catch(e:any){if(e.name!=='AbortError'){assistant.status='error';assistant.content=e.message;notice.value=e.message}else{assistant.status='interrupted';assistant.content=assistant.content||'已停止生成'}}finally{sending.value=false;aborter.value=null}
}
function stop(){aborter.value?.abort();sending.value=false}
async function openSettings(tab:typeof settingsTab.value='model'){settingsTab.value=tab;settingsOpen.value=true;confUnlocked.value=false;confidential.value=[];await refreshSettings()}
async function loadModelConfig(loadSecret=false){const x:any=await api('/settings/model');modelConfigured.value=!!x.configured;apiKeyLoaded.value=false;if(x.configured){model.value={api_key:'',api_key_masked:x.api_key_masked,base_url:x.base_url,model:x.model};if(loadSecret){const secret:any=await api('/settings/model/secret');model.value.api_key=secret.api_key;apiKeyLoaded.value=true}}else{model.value.api_key='';model.value.api_key_masked='';apiKeyLoaded.value=true}showApiKey.value=false;connectionStatus.value='idle';connectionMessage.value=''}
async function refreshSettings(){
  if(settingsTab.value==='model')await loadModelConfig(true)
  if(settingsTab.value==='confidential')confidential.value=await api('/libraries/confidential')
  if(settingsTab.value==='public')publicEntries.value=await api('/libraries/public')
}
function modelPayload(){return {base_url:model.value.base_url,model:model.value.model,...(model.value.api_key?{api_key:model.value.api_key}:{})}}
async function saveModel(){try{if(modelConfigured.value&&apiKeyLoaded.value&&!model.value.api_key){await api('/settings/model',{method:'DELETE'});notice.value='模型配置已删除';await loadModelConfig(true);return}await api('/settings/model',{method:'PUT',body:JSON.stringify(modelPayload())});notice.value='模型配置已保存';await loadModelConfig(true)}catch(e:any){notice.value=e.message}}
async function testModel(){connectionStatus.value='testing';connectionMessage.value='正在连接模型服务…';try{const result:any=await api('/settings/model/test',{method:'POST',body:JSON.stringify(modelPayload())});connectionStatus.value='ok';connectionMessage.value=result.message;notice.value='模型连接正常'}catch(e:any){connectionStatus.value='error';connectionMessage.value=e.message;notice.value=e.message}}
function removeFromList(arr:string[],idx:number){arr.splice(idx,1)}
function addParaphrase(){const v=newParaphrase.value.trim();if(v&&!confParaphrases.value.includes(v)){confParaphrases.value.push(v)}newParaphrase.value=''}
function addKeyword(){const v=newKeyword.value.trim();if(v&&!confKeywords.value.includes(v)){confKeywords.value.push(v)}newKeyword.value=''}
function addNegative(){const v=newNegative.value.trim();if(v&&!confNegatives.value.includes(v)){confNegatives.value.push(v)}newNegative.value=''}
async function addConf(){
  const f=confForm.value
  await api('/libraries/confidential',{method:'POST',body:JSON.stringify({
    text:f.text,
    category:f.category||'confidential',
    confidential_level:f.confidential_level||'high',
    summary:f.summary||null,
    paraphrases:confParaphrases.value,
    negative_samples:confNegatives.value,
    keywords:confKeywords.value,
    enabled:true
  })})
  confForm.value={text:'',category:'',confidential_level:'high',summary:'',enabled:true}
  confParaphrases.value=[];confKeywords.value=[];confNegatives.value=[]
  await refreshSettings()
}
async function unlockConf(){
  confUnlockError.value=''
  try{
    await api('/auth/verify-password',{method:'POST',body:JSON.stringify({password:confUnlockPassword.value})})
    confUnlocked.value=true
    confidential.value=await api('/libraries/confidential')
  }catch(e:any){
    confUnlockError.value='密码错误'
  }
  confUnlockPassword.value=''
}
function lockConf(){confUnlocked.value=false;confidential.value=[]}
async function addPublic(){await api('/libraries/public',{method:'POST',body:JSON.stringify(pubForm.value)});pubForm.value={entity_type:'phone',value:'',label:'',enabled:true};await refreshSettings()}
async function delEntry(kind:'confidential'|'public',id:string){await api(`/libraries/${kind}/${id}`,{method:'DELETE'});await refreshSettings()}
async function importFile(kind:'confidential'|'public',event:Event){
  const input=event.target as HTMLInputElement
  const file=input.files?.[0]
  if(!file)return
  try{
    const x=await upload(`/libraries/${kind}/import`,file)
    notice.value=`已导入 ${x.imported_count} 条，失败 ${x.error_count} 条`
    await refreshSettings()
  }catch(e:any){
    notice.value=`导入失败: ${e.message}`
  }finally{
    input.value=''
  }
}

function downloadTemplate(kind:'confidential'|'public'){
  const lines=kind==='confidential'
    ?[JSON.stringify({fact_text:"公司Q3营收预计增长30%",category:"财务数据",confidential_level:"high",summary:"Q3财务预测",paraphrases:["第三季度收入预计提升三成","Q3营收增长约30%"],negative_samples:["今年Q2营收是多少？","上市公司财报公开数据"],keywords:["Q3","营收","增长","财务预测"]})]
    :[JSON.stringify({entity_type:"phone",value:"13800138000",label:"客服电话"}),JSON.stringify({entity_type:"email",value:"support@example.com",label:"客服邮箱"})]
  const blob=new Blob([lines.join('\n')+'\n'],{type:'application/jsonl'})
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=kind==='confidential'?'保密库模板.jsonl':'公开库模板.jsonl';a.click();URL.revokeObjectURL(a.href)}
let noticeTimer:ReturnType<typeof setTimeout>
watch(notice,(v)=>{clearTimeout(noticeTimer);if(v)noticeTimer=setTimeout(()=>{notice.value=''},3000)})
onMounted(boot)
</script>

<template>
  <main v-if="!user" class="auth-page"><section class="auth-card"><div class="brand-mark">G</div><h1>LLM Guardrails</h1><p>安全、隔离的智能对话工作台</p><form @submit.prevent="authenticate"><label>用户名<input v-model="username" autocomplete="username" required minlength="3"></label><label>密码<input v-model="password" type="password" autocomplete="current-password" required minlength="8"></label><div v-if="error" class="error">{{error}}</div><button class="primary">{{authMode==='login'?'登录':'创建账号'}}</button></form><button class="link" @click="authMode=authMode==='login'?'register':'login'">{{authMode==='login'?'没有账号？立即注册':'已有账号？返回登录'}}</button></section></main>
  <main v-else class="workspace">
    <aside :class="['sidebar',{collapsed:sidebarCollapsed}]" @click="convMenuId='';renameId=''"><div class="logo"><span>G</span><b>Guardrails</b></div><button class="new-chat" @click="createConversation">＋ <span>新对话</span></button><div class="history"><small>历史对话</small><div v-for="item in conversations" :key="item.id" :class="['conversation',{active:item.id===activeId}]" @click="openConversation(item.id)"><template v-if="renameId===item.id"><input class="rename-input" v-model="renameTitle" @blur="submitRename" @keydown.enter="submitRename" @keydown.escape="renameId=''" @click.stop></template><template v-else><span>{{item.title}}</span><button class="conv-menu-btn" @click.stop="openConvMenu(item.id,$event)">⋯</button></template><div v-if="convMenuId===item.id&&renameId!==item.id" class="conv-menu" @click.stop :style="{position:'fixed',top:menuPos.top+'px',left:menuPos.left+'px'}"><button @click="startRename(item)">✏️ 重命名</button><button @click="convMenuId='';removeConversation(item.id)">🗑️ 删除</button></div></div></div><div class="profile"><button @click="openSettings()" class="settings-btn">⚙ <span>设置</span></button></div></aside>
    <section class="chat" @click="userMenuOpen=false;convMenuId=''"><header><button class="sidebar-toggle" @click="sidebarCollapsed=!sidebarCollapsed" :title="sidebarCollapsed?'展开侧栏':'折叠侧栏'"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg></button><h2>{{chatTitle}}</h2><div class="header-right"><button :class="['model-status',{healthy:modelConfigured&&connectionStatus!=='error'}]" @click="openSettings('model')" :title="modelConfigured?(connectionStatus==='error'?'模型连接异常':'模型配置正常'):'未配置模型'"><span class="status-dot"></span><b>{{modelConfigured?model.model:'未配置模型'}}</b></button><div class="account-menu" @click.stop><button class="account-trigger" @click="userMenuOpen=!userMenuOpen"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg><span>{{user.username}}</span><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg></button><div v-if="userMenuOpen" class="account-dropdown"><div class="account-identity"><strong>{{user.username}}</strong></div><button @click="userMenuOpen=false;logout()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>退出登录</button></div></div></div></header><div class="messages">
      <div v-if="!messages.length" class="welcome"><h1>有什么可以帮助您的？</h1><p>输入内容将在发送给模型前经过安全检测</p></div>
      <article v-for="(item,index) in messages" :key="item.id" :class="['message',item.role]">
        <div v-if="item.role==='assistant'&&decisionFor(index)" :class="['decision',decisionFor(index)?.action]"><b>{{decisionFor(index)?.action==='pass'?'✓ 安全通过':decisionFor(index)?.action==='redact'?'◐ 已脱敏处理':'⊘ 已阻止发送'}}</b><span v-if="decisionFor(index)?.risk_score!=null">风险 {{Math.round((decisionFor(index)?.risk_score||0)*100)}}%</span><small>{{decisionFor(index)?.guardrail_message}}</small><details v-if="decisionFor(index)?.action==='redact'"><summary>查看发送给模型的内容</summary><pre>{{decisionFor(index)?.safe_content}}</pre></details></div>
        <div v-if="item.role==='user'" class="bubble">{{item.content}}</div><div v-else-if="item.status==='thinking'" class="thinking"><span>{{item.action?'正在思考':'正在进行安全检测'}}</span><i></i><i></i><i></i></div><div v-else class="answer" v-html="render(item.content)"></div>
        <div v-if="item.role==='assistant'&&item.status==='complete'&&item.content" class="message-actions"><button @click="copyMessage(item.content)" title="复制回复">⧉ <span>复制</span></button><button @click="regenerate(index)" title="重新生成">↻ <span>重新生成</span></button></div>
      </article>
    </div><footer><div :class="['composer',{disabled:!modelConfigured}]"><textarea v-model="input" :placeholder="modelConfigured?'输入消息，Enter 发送，Shift+Enter 换行':'请先在设置中配置模型'" @keydown.enter.exact.prevent="send" :disabled="sending||!modelConfigured"></textarea><button v-if="sending" class="stop" @click="stop">■</button><button v-else class="send" @click="send" :disabled="!modelConfigured" title="发送消息"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h14m-6-6 6 6-6 6"/></svg></button></div><small>{{modelConfigured?'模型输出可能存在误差，重要信息请核实':'配置 API Key、模型地址和模型名称后才能开始对话'}}</small></footer></section>
    <div v-if="settingsOpen" class="modal" @click.self="settingsOpen=false"><section class="settings"><header><h2>设置</h2><button @click="settingsOpen=false">×</button></header><nav><button v-for="tab in ['model','confidential','public']" :key="tab" :class="{active:settingsTab===tab}" @click="settingsTab=tab as any;refreshSettings()">{{({model:'模型配置',confidential:'保密库',public:'公开库'} as any)[tab]}}</button></nav><div class="panel">
      <form v-if="settingsTab==='model'" @submit.prevent="saveModel" class="form"><h3>模型配置</h3><label>API Key<div class="password-input"><input v-model="model.api_key" :type="showApiKey?'text':'password'" :required="!modelConfigured" placeholder="输入 API Key" autocomplete="new-password"><button type="button" @click="showApiKey=!showApiKey" :title="showApiKey?'隐藏 API Key':'显示 API Key'">{{showApiKey?'◉':'👁'}}</button></div></label><label>Base URL<input v-model="model.base_url" required></label><label>模型名<input v-model="model.model" required></label><div class="connection-result" :class="connectionStatus"><span v-if="connectionMessage">{{connectionMessage}}</span></div><div><button type="button" @click="testModel" :disabled="connectionStatus==='testing'||!model.api_key">{{connectionStatus==='testing'?'测试中…':'测试连接'}}</button><button class="primary">保存</button></div></form>
      <div v-if="settingsTab==='confidential'"><div class="section-header"><h3>保密库</h3><div class="section-actions"><button class="link-btn" @click="downloadTemplate('confidential')">📥 下载模板</button><label class="upload-btn">📤 导入 JSONL<input type="file" accept=".jsonl" @change="importFile('confidential',$event)"></label></div></div><p class="section-desc">与这些事实相似的用户输入将被检测并阻止发送给模型。</p>
      <form class="conf-form" @submit.prevent="addConf">
        <label class="field-label">保密事实 <span class="required">*</span></label>
        <textarea v-model="confForm.text" placeholder="需要保护的机密信息，建议一句话描述一个事实，如：公司Q3营收预计增长30%" required></textarea>
        <div class="form-row"><div class="field"><label class="field-label">分类</label><select v-model="confForm.category"><option value="财务数据">财务数据</option><option value="产品规划">产品规划</option><option value="客户信息">客户信息</option><option value="源代码">源代码</option><option value="商业战略">商业战略</option><option value="人事信息">人事信息</option><option value="技术机密">技术机密</option><option value="法务">法务</option><option value="其他">其他</option></select></div><div class="field"><label class="field-label">保密等级</label><div class="level-buttons"><button type="button" :class="['level-btn',{active:confForm.confidential_level==='high'}]" @click="confForm.confidential_level='high'"><b>High</b><small>直接阻止</small></button><button type="button" :class="['level-btn',{active:confForm.confidential_level==='medium'}]" @click="confForm.confidential_level='medium'"><b>Medium</b><small>提醒+阻止</small></button><button type="button" :class="['level-btn',{active:confForm.confidential_level==='low'}]" @click="confForm.confidential_level='low'"><b>Low</b><small>仅提醒</small></button></div></div></div>
        <label class="field-label">同义表达</label>
        <div class="tag-list"><div v-for="(p,i) in confParaphrases" :key="i" class="tag-item"><span>{{p}}</span><button @click="removeFromList(confParaphrases,i)">×</button></div><div class="tag-input wide"><input v-model="newParaphrase" placeholder="用不同说法描述同一事实，按回车添加，提高检测命中率" @keydown.enter.prevent="addParaphrase()"><button type="button" @click="addParaphrase()">+</button></div></div>
        <button type="button" class="toggle-advanced" @click="showConfAdvanced=!showConfAdvanced">{{showConfAdvanced?'▲ 收起高级配置':'▼ 高级配置'}}</button>
        <div v-if="showConfAdvanced" class="advanced-section">
          <div class="field"><label class="field-label">摘要</label><input v-model="confForm.summary" placeholder="一句话概括这个事实，如：Q3财务预测"></div>
          <div class="field"><label class="field-label">关键词</label><div class="tag-list"><div v-for="(k,i) in confKeywords" :key="i" class="tag-item"><span>{{k}}</span><button @click="removeFromList(confKeywords,i)">×</button></div><div class="tag-input wide"><input v-model="newKeyword" placeholder="输入关键词（便于检索），按回车添加" @keydown.enter.prevent="addKeyword()"><button type="button" @click="addKeyword()">+</button></div></div></div>
          <div class="field"><div class="label-row"><label class="field-label">反例</label><span class="field-hint inline">与该事实相关但不涉密的正常问题，用于减少误报</span></div><div class="tag-list"><div v-for="(n,i) in confNegatives" :key="i" class="tag-item"><span>{{n}}</span><button @click="removeFromList(confNegatives,i)">×</button></div><div class="tag-input wide"><input v-model="newNegative" placeholder="输入反例，按回车添加" @keydown.enter.prevent="addNegative()"><button type="button" @click="addNegative()">+</button></div></div></div>
        </div>
        <div class="form-actions"><button class="primary" type="submit">添加到保密库</button></div>
      </form>
      <div class="vault-section">
        <div class="vault-header"><span>🔐 保密库内容</span><button v-if="confUnlocked" class="link-btn" @click="lockConf()">锁定</button></div>
        <div v-if="!confUnlocked" class="vault-lock"><input v-model="confUnlockPassword" type="password" placeholder="输入密码查看保密库内容" @keydown.enter="unlockConf()" @input="confUnlockError=''"><button class="primary" @click="unlockConf()">验证</button><span v-if="confUnlockError" class="error">{{confUnlockError}}</span></div>
        <template v-else>
          <div v-if="!confidential.length" class="vault-empty">暂无保密条目</div>
          <div v-else class="entry" v-for="x in confidential" :key="x.id"><div><b>{{x.category||'未分类'}} · {{x.confidential_level||'high'}}</b><p>{{x.text}}</p><small v-if="x.summary">{{x.summary}}</small></div><button @click="delEntry('confidential',x.id)">删除</button></div>
        </template>
      </div></div>
      <div v-if="settingsTab==='public'"><div class="section-header"><h3>公开库</h3><div class="section-actions"><button class="link-btn" @click="downloadTemplate('public')">📥 下载模板</button><label class="upload-btn">📤 导入<input type="file" accept=".jsonl" @change="importFile('public',$event)"></label></div></div><p class="section-desc">添加已知的公开联系信息，这些信息不会被规则脱敏（如公司官网电话、公开邮箱等）。</p><form class="inline-form compact" @submit.prevent="addPublic"><select v-model="pubForm.entity_type"><option value="phone">手机号</option><option value="email">邮箱</option><option value="id_card">身份证</option><option value="bank_card">银行卡</option></select><input v-model="pubForm.value" placeholder="值，如 13800138000" required><input v-model="pubForm.label" placeholder="备注，如 客服电话"><button class="primary">添加</button></form><div class="entry" v-for="x in publicEntries" :key="x.id"><div><b>{{x.entity_type}} · {{x.label}}</b><p>{{x.value}}</p></div><button @click="delEntry('public',x.id)">删除</button></div></div>
    </div></section></div>
    <div v-if="confirmDialog.show" class="modal" @click.self="confirmDialog.show=false"><div class="confirm-dialog"><h3>{{confirmDialog.title}}</h3><p>{{confirmDialog.message}}</p><div class="confirm-actions"><button @click="confirmDialog.show=false">取消</button><button class="danger" @click="confirmDialog.onConfirm();confirmDialog.show=false">确定</button></div></div></div>
    <Transition name="toast"><div v-if="notice" class="toast" @click="notice=''"><span>{{notice}}</span><button>×</button></div></Transition>
  </main>
</template>
