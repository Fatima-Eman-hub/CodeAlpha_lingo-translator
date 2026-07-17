const LANGS = [
  {code:'auto', name:'Detect language', native:'Auto-detect', flag:'🌐'},
  {code:'en', name:'English', native:'English', flag:'🇬🇧'},
  {code:'ur', name:'Urdu', native:'اردو', flag:'🇵🇰'},
  {code:'es', name:'Spanish', native:'Español', flag:'🇪🇸'},
  {code:'fr', name:'French', native:'Français', flag:'🇫🇷'},
  {code:'de', name:'German', native:'Deutsch', flag:'🇩🇪'},
  {code:'ar', name:'Arabic', native:'العربية', flag:'🇸🇦'},
  {code:'zh', name:'Chinese', native:'中文', flag:'🇨🇳'},
  {code:'ja', name:'Japanese', native:'日本語', flag:'🇯🇵'},
  {code:'hi', name:'Hindi', native:'हिन्दी', flag:'🇮🇳'},
  {code:'ru', name:'Russian', native:'Русский', flag:'🇷🇺'},
  {code:'pt', name:'Portuguese', native:'Português', flag:'🇵🇹'},
  {code:'tr', name:'Turkish', native:'Türkçe', flag:'🇹🇷'},
  {code:'ko', name:'Korean', native:'한국어', flag:'🇰🇷'},
  {code:'it', name:'Italian', native:'Italiano', flag:'🇮🇹'},
];

let state = {
  source: LANGS[0], // auto
  target: LANGS[2], // urdu
  loading: false,
  history: [], // {id, source, target, srcText, tgtText, favorited}
  totalWords: 0,
};

// Every browser gets one random, permanent ID (kept in localStorage) so the
// backend can scope each visitor's history to them and nobody else. This is
// NOT a login system — it's device/browser-specific, like a cookie. Clearing
// browser data resets it, and it doesn't follow you to a different browser.
function getClientId(){
  let id = localStorage.getItem('lingo_client_id');
  if(!id){
    id = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : 'id-' + Date.now() + '-' + Math.random().toString(36).slice(2);
    localStorage.setItem('lingo_client_id', id);
  }
  return id;
}
const CLIENT_ID = getClientId();

// Chinese/Japanese/Korean don't use spaces between words, so a naive
// split(/\s+/) undercounts massively (a whole paragraph reads as "1 word").
// For CJK text we count characters instead, which is the standard convention.
function countWords(text){
  const trimmed = (text || '').trim();
  if(!trimmed) return 0;
  const cjkRegex = /[\u4e00-\u9fff\u3040-\u30ff\u30a0-\u30ff\uac00-\ud7af]/;
  if(cjkRegex.test(trimmed)){
    return trimmed.replace(/[\s\u3000-\u303F\uFF00-\uFFEF]/g, '').length;
  }
  return trimmed.split(/\s+/).length;
}

const $ = id => document.getElementById(id);

function renderDropdown(listEl, searchTerm, onPick){
  listEl.innerHTML = '';
  const term = (searchTerm||'').toLowerCase();
  LANGS.filter(l => l.name.toLowerCase().includes(term) || l.native.toLowerCase().includes(term)).forEach(l=>{
    const item = document.createElement('div');
    item.className = 'dd-item';
    item.innerHTML = `<span class="flag">${l.flag}</span><div class="meta"><span>${l.name}</span><span class="native">${l.native}</span></div>`;
    item.onclick = ()=> onPick(l);
    listEl.appendChild(item);
  });
}

function closeAllDropdowns(){
  $('sourceDropdown').classList.remove('open');
  $('targetDropdown').classList.remove('open');
}

function setupSelector(kind){
  const isSource = kind === 'source';
  const selectEl = $(isSource ? 'sourceSelect' : 'targetSelect');
  const ddEl = $(isSource ? 'sourceDropdown' : 'targetDropdown');
  const searchEl = $(isSource ? 'sourceSearch' : 'targetSearch');
  const listEl = $(isSource ? 'sourceList' : 'targetList');

  renderDropdown(listEl, '', (l)=>pickLang(kind, l));

  selectEl.addEventListener('click', (e)=>{
    e.stopPropagation();
    const wasOpen = ddEl.classList.contains('open');
    closeAllDropdowns();
    if(!wasOpen){
      ddEl.classList.add('open');
      searchEl.value='';
      renderDropdown(listEl,'',(l)=>pickLang(kind,l));
      searchEl.focus();
      setTimeout(()=> ddEl.scrollIntoView({block:'nearest', behavior:'smooth'}), 50);
    }
  });
  searchEl.addEventListener('click', e=>e.stopPropagation());
  searchEl.addEventListener('input', ()=> renderDropdown(listEl, searchEl.value, (l)=>pickLang(kind,l)));
}

function pickLang(kind, lang){
  if(kind === 'source') state.source = lang; else state.target = lang;
  updateLangUI();
  closeAllDropdowns();
}

function updateLangUI(){
  $('sourceFlag').textContent = state.source.flag;
  $('sourceName').textContent = state.source.name;
  $('sourceSub').textContent = state.source.native;
  $('sourceSelect').classList.toggle('auto', state.source.code === 'auto');

  $('targetFlag').textContent = state.target.flag;
  $('targetName').textContent = state.target.name;
  $('targetSub').textContent = state.target.native;
}

document.addEventListener('click', closeAllDropdowns);
setupSelector('source');
setupSelector('target');
updateLangUI();

// Swap
$('swapBtn').addEventListener('click', ()=>{
  if(state.source.code === 'auto'){
    const detectedName = lastResult && lastResult.detectedLanguage;
    if(!detectedName){
      showToast("Can't swap yet — translate something first so I know the source language");
      return;
    }
    const match = LANGS.find(l => l.name.toLowerCase() === detectedName.toLowerCase());
    if(match){
      state.source = match; // resolve "auto" to the actual detected language, then swap normally
    } else {
      showToast(`Detected "${detectedName}" isn't in the selectable language list, so it can't be swapped in`);
      return;
    }
  }
  $('swapBtn').classList.add('spin');
  setTimeout(()=>$('swapBtn').classList.remove('spin'), 350);
  [state.source, state.target] = [state.target, state.source];
  const inTxt = $('inputText').value;
  const outTxt = $('outputText').textContent;
  updateLangUI();
  if(outTxt && $('outputText').dataset.empty !== 'true'){
    $('inputText').value = outTxt;
    updateCounters();
  }
});

// Char / word counters
function updateCounters(){
  const val = $('inputText').value;
  const len = val.length;
  $('charNum').textContent = len;
  $('charFill').style.width = Math.min(100,(len/2000)*100)+'%';
  $('charFill').style.background = len > 1800 ? '#d9765b' : 'linear-gradient(90deg,var(--sage),var(--lav))';
  const words = countWords(val);
  $('wordNum').textContent = words;
}
$('inputText').addEventListener('input', updateCounters);

// Clear
$('clearBtn').addEventListener('click', clearAll);
function clearAll(){
  $('inputText').value = '';
  updateCounters();
  setOutputEmpty();
}

// Paste
$('pasteBtn').addEventListener('click', async ()=>{
  try{
    const text = await navigator.clipboard.readText();
    $('inputText').value = (text||'').replace(/\s+\n/g,'\n').trim();
    updateCounters();
  }catch(e){ showToast('Clipboard access denied'); }
});

// Output helpers
function setOutputEmpty(){
  const out = $('outputText');
  out.textContent = '';
  out.dataset.empty = 'true';
  $('altChips').innerHTML = '';
  $('detectedInfo').innerHTML = '&nbsp;';
  $('copyBtn').disabled = true;
  $('speakBtn').disabled = true;
  $('favBtn').disabled = true;
}

function showSkeleton(){
  const out = $('outputText');
  out.dataset.empty = 'false';
  out.innerHTML = `<div class="skeleton"><div class="sk-line w1"></div><div class="sk-line w2"></div><div class="sk-line w3"></div></div>`;
  $('altChips').innerHTML = '';
}

// Toast
function showToast(msg){
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  $('toastContainer').appendChild(t);
  setTimeout(()=>t.remove(), 2000);
}

// Backend base URL. Empty string = same origin as the page itself.
// Locally that's Flask on 127.0.0.1:5000 (which now also serves this page).
// Deployed, it's whatever domain the app is hosted on — no code change needed.
const BACKEND_URL = "";

// Translate call via our Flask backend (backend/app.py), which uses Google Translate
async function callBackend(text, sourceCode, targetCode){
  const response = await fetch(`${BACKEND_URL}/api/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, source: sourceCode, target: targetCode })
  });
  const data = await response.json();
  if(!response.ok){
    throw new Error(data.error || "Translation request failed");
  }
  return data; // { translation, detectedLanguage, phonetic, alternatives }
}

let lastResult = null;

async function translate(){
  const text = $('inputText').value.trim();
  if(!text){ showToast('Type something to translate'); return; }
  if(state.loading) return;
  state.loading = true;
  $('translateBtn').disabled = true;
  $('translateBtnLabel').textContent = 'Translating…';
  showSkeleton();

  try{
    const result = await callBackend(text, state.source.code, state.target.code);
    lastResult = result;
    renderOutput(result);
    addHistoryEntry(text, result.translation);
  }catch(err){
    console.error(err);
    setOutputEmpty();
    showToast(err.message === 'Failed to fetch' ? 'Backend not running — start Flask server first' : 'Translation failed — try again');
  }finally{
    state.loading = false;
    $('translateBtn').disabled = false;
    $('translateBtnLabel').textContent = 'Translate';
  }
}

function renderOutput(result){
  const out = $('outputText');
  out.dataset.empty = 'false';
  out.innerHTML = '';
  const mainSpan = document.createElement('span');
  mainSpan.textContent = result.translation || '';
  out.appendChild(mainSpan);
  if(result.phonetic){
    const ph = document.createElement('span');
    ph.className = 'phonetic';
    ph.textContent = result.phonetic;
    out.appendChild(ph);
  }
  if(state.source.code === 'auto' && result.detectedLanguage){
    $('detectedInfo').textContent = `Detected: ${result.detectedLanguage}`;
  } else {
    $('detectedInfo').innerHTML = '&nbsp;';
  }
  const altWrap = $('altChips');
  altWrap.innerHTML = '';
  (result.alternatives||[]).slice(0,2).forEach(alt=>{
    if(!alt) return;
    const chip = document.createElement('button');
    chip.className = 'alt-chip';
    chip.textContent = alt;
    chip.onclick = ()=>{
      mainSpan.textContent = alt;
      showToast('Alternative applied');
    };
    altWrap.appendChild(chip);
  });
  $('copyBtn').disabled = false;
  $('speakBtn').disabled = false;
  $('favBtn').disabled = false;
}

$('translateBtn').addEventListener('click', translate);

// Copy
$('copyBtn').addEventListener('click', ()=>{
  const txt = $('outputText').innerText;
  navigator.clipboard.writeText(txt).then(()=> showToast('Copied to clipboard'));
});

// Text to speech
// Two real bugs here on Windows/Edge: (1) plain 2-letter codes like 'ur' often
// don't match an installed voice's locale (e.g. voices report 'ur-PK'), so the
// browser silently does nothing; (2) voices load asynchronously — calling
// speak() before they're ready can also fail silently. Both fixed below.
const TTS_LOCALE = {
  en:'en-US', ur:'ur-PK', es:'es-ES', fr:'fr-FR', de:'de-DE', ar:'ar-SA',
  zh:'zh-CN', ja:'ja-JP', hi:'hi-IN', ru:'ru-RU', pt:'pt-PT', tr:'tr-TR',
  ko:'ko-KR', it:'it-IT'
};

let cachedVoices = [];
function loadVoices(){
  cachedVoices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
}
if(window.speechSynthesis){
  loadVoices();
  window.speechSynthesis.onvoiceschanged = loadVoices;
}

function speakText(text, langCode){
  if(!text || !window.speechSynthesis){
    showToast('Text-to-speech is not supported in this browser');
    return;
  }
  const locale = TTS_LOCALE[langCode] || 'en-US';
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = locale;

  // Prefer an exact/prefix voice match; otherwise let the browser fall back
  // (most engines still speak using a default voice even without an exact match).
  const match = cachedVoices.find(v => v.lang === locale) ||
                cachedVoices.find(v => v.lang && v.lang.startsWith(locale.split('-')[0]));
  if(match) utter.voice = match;

  let started = false;
  utter.onstart = () => { started = true; };
  utter.onerror = () => showToast(`No voice available for ${locale} on this device`);

  window.speechSynthesis.cancel();
  // Re-check voices right before speaking in case they finished loading late
  if(cachedVoices.length === 0) loadVoices();
  window.speechSynthesis.speak(utter);

  // Some browsers (notably Chrome on Windows) neither fire 'error' nor make any
  // sound when no voice matches the requested language — they just do nothing.
  // If speech genuinely never started, tell the user instead of staying silent.
  setTimeout(() => {
    if(!started && !window.speechSynthesis.speaking){
      showToast(match ? 'Playback failed — try again' : `No "${locale}" voice installed on this device, so it can't be spoken aloud`);
    }
  }, 400);
}

$('speakBtn').addEventListener('click', ()=>{
  speakText($('outputText').innerText, state.target.code === 'auto' ? 'en' : state.target.code);
});
$('micBtn').addEventListener('click', ()=>{
  speakText($('inputText').value, state.source.code === 'auto' ? 'en' : state.source.code);
});

// History
function langByCode(code){
  return LANGS.find(l => l.code === code) || LANGS[1]; // fallback to English display if unknown
}

async function addHistoryEntry(srcText, tgtText){
  const entry = {
    id: null, // filled in once the backend confirms the save
    source: state.source,
    target: state.target,
    srcText, tgtText,
    favorited: false
  };
  state.history.unshift(entry);
  if(state.history.length > 50) state.history.pop();
  renderHistory();
  updateStats(srcText);

  try{
    const res = await fetch(`${BACKEND_URL}/api/history`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: CLIENT_ID,
        source_code: state.source.code,
        target_code: state.target.code,
        src_text: srcText,
        tgt_text: tgtText
      })
    });
    if(res.ok){
      const data = await res.json();
      entry.id = data.id;
    }
    // if this silently fails, the entry just stays local for this session —
    // translation itself already succeeded, so we don't interrupt the user with a toast
  }catch(e){
    console.error('Failed to save history to backend:', e);
  }
}

async function loadHistoryFromServer(){
  try{
    const res = await fetch(`${BACKEND_URL}/api/history?user_id=${encodeURIComponent(CLIENT_ID)}`);
    if(!res.ok) return;
    const data = await res.json();
    state.history = (data.history || []).map(row => ({
      id: row.id,
      source: langByCode(row.source_code === 'auto' ? 'auto' : row.source_code),
      target: langByCode(row.target_code),
      srcText: row.src_text,
      tgtText: row.tgt_text,
      favorited: !!row.favorited
    }));
    state.totalWords = state.history.reduce((sum, h) => sum + countWords(h.srcText), 0);
    $('statCount').textContent = state.history.length;
    $('statWords').textContent = state.totalWords;
    renderHistory();
  }catch(e){
    console.error('Failed to load history from backend:', e);
    // backend not running yet — history panel just stays empty until a translation succeeds
  }
}

let historyFilter = 'all'; // 'all' | 'starred'
let historySearchTerm = '';

function renderHistory(){
  const body = $('historyBody');

  let list = state.history;
  if(historyFilter === 'starred') list = list.filter(h => h.favorited);
  if(historySearchTerm.trim()){
    const term = historySearchTerm.trim().toLowerCase();
    list = list.filter(h =>
      h.srcText.toLowerCase().includes(term) || h.tgtText.toLowerCase().includes(term)
    );
  }

  // toolbar badge + drawer subtitle always reflect the full (unfiltered) history
  $('historyBadge').textContent = state.history.length;
  const totalWordsAll = state.history.reduce((sum, h) => sum + countWords(h.srcText), 0);
  $('drawerSubtitle').textContent = `${state.history.length} saved · ${totalWordsAll} words total`;

  if(list.length === 0){
    const msg = state.history.length === 0
      ? 'No translations yet — your history will show up here.'
      : (historyFilter === 'starred' ? 'No starred translations yet.' : 'No matches found.');
    body.innerHTML = `<div class="history-empty"><span class="glyph">🗂️</span>${msg}</div>`;
    return;
  }
  body.innerHTML = '';
  const listEl = document.createElement('div');
  listEl.className = 'history-list';
  list.forEach(h=>{
    const row = document.createElement('div');
    row.className = 'hist-item';
    row.innerHTML = `
      <span class="pair">${h.source.flag}→${h.target.flag}</span>
      <div class="texts">
        <div class="src">${escapeHtml(h.srcText)}</div>
        <div class="tgt">${escapeHtml(h.tgtText)}</div>
      </div>
      <button class="star ${h.favorited?'favorited':''}">${h.favorited?'★':'☆'}</button>
    `;
    row.querySelector('.texts').onclick = ()=>{
      state.source = h.source; state.target = h.target;
      updateLangUI();
      $('inputText').value = h.srcText;
      updateCounters();
      renderOutput({translation: h.tgtText, phonetic:'', alternatives:[], detectedLanguage:''});
    };
    row.querySelector('.star').onclick = async (e)=>{
      e.stopPropagation();
      h.favorited = !h.favorited; // optimistic UI update
      renderHistory();
      if(h.id == null) return; // wasn't saved to backend (e.g. it failed silently earlier)
      try{
        await fetch(`${BACKEND_URL}/api/history/${h.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: CLIENT_ID })
        });
      }catch(e){
        console.error('Failed to sync favorite to backend:', e);
      }
    };
    listEl.appendChild(row);
  });
  body.appendChild(listEl);
}

function escapeHtml(s){
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function updateStats(srcText){
  const count = state.history.length;
  $('statCount').textContent = count;
  state.totalWords += countWords(srcText);
  $('statWords').textContent = state.totalWords;
}

loadHistoryFromServer();

// Keyboard shortcuts
document.addEventListener('keydown', (e)=>{
  if((e.ctrlKey || e.metaKey) && e.key === 'Enter'){
    e.preventDefault();
    translate();
  }
  if((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k'){
    e.preventDefault();
    clearAll();
  }
});

updateCounters();

// ---- Font size control (A- / A+) ----
const FONT_MIN = 12, FONT_MAX = 24, FONT_STEP = 1;
let fontSize = parseInt(localStorage.getItem('lingo_font_size') || '16', 10);
function applyFontSize(){
  fontSize = Math.max(FONT_MIN, Math.min(FONT_MAX, fontSize));
  document.documentElement.style.setProperty('--content-font-size', fontSize + 'px');
  $('fontSizeValue').textContent = fontSize;
  localStorage.setItem('lingo_font_size', String(fontSize));
}
$('fontDecBtn').addEventListener('click', ()=>{ fontSize -= FONT_STEP; applyFontSize(); });
$('fontIncBtn').addEventListener('click', ()=>{ fontSize += FONT_STEP; applyFontSize(); });
applyFontSize();

// ---- Contrast / dark mode toggle ----
function applyContrastMode(on){
  document.body.classList.toggle('dark-mode', on);
  localStorage.setItem('lingo_dark_mode', on ? '1' : '0');
}
$('contrastBtn').addEventListener('click', ()=>{
  applyContrastMode(!document.body.classList.contains('dark-mode'));
});
applyContrastMode(localStorage.getItem('lingo_dark_mode') === '1');

// ---- History drawer open/close ----
function openDrawer(){
  $('historyDrawer').classList.add('open');
  $('drawerOverlay').classList.add('open');
}
function closeDrawer(){
  $('historyDrawer').classList.remove('open');
  $('drawerOverlay').classList.remove('open');
}
$('historyOpenBtn').addEventListener('click', openDrawer);
$('historyCloseBtn').addEventListener('click', closeDrawer);
$('drawerOverlay').addEventListener('click', closeDrawer);
document.addEventListener('keydown', (e)=>{ if(e.key === 'Escape') closeDrawer(); });

// ---- History filter tabs (All / Starred) ----
$('filterAllBtn').addEventListener('click', ()=>{
  historyFilter = 'all';
  $('filterAllBtn').classList.add('active');
  $('filterStarredBtn').classList.remove('active');
  renderHistory();
});
$('filterStarredBtn').addEventListener('click', ()=>{
  historyFilter = 'starred';
  $('filterStarredBtn').classList.add('active');
  $('filterAllBtn').classList.remove('active');
  renderHistory();
});

// ---- History search ----
$('historySearch').addEventListener('input', (e)=>{
  historySearchTerm = e.target.value;
  renderHistory();
});
