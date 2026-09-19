<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import {
    languageApi,
    type LanguageAnalysis,
    type LanguageAnalyzerStatus,
    type LanguageAnalyzerToken,
    type LanguageSavedAnalysis,
    type ManualWordInput,
  } from '../../lib/languageApi';

  const dispatch = createEventDispatcher<{
    openword: string;
    addword: Partial<ManualWordInput>;
  }>();

  let status: LanguageAnalyzerStatus | null = null;
  let history: LanguageSavedAnalysis[] = [];
  let text = '';
  let analysis: LanguageAnalysis | null = null;
  let selectedIndex = 0;
  let translationEn = '';
  let translationMn = '';
  let currentSavedId: string | undefined;
  let loading = false;
  let saving = false;
  let error = '';
  let message = '';
  let showHistory = false;
  let dictionaryBusy = false;
  let dictionaryEntries: Array<{
    word: string;
    part_of_speech: string;
    language: string;
    translated_word: string;
    definition: string;
  }> = [];

  $: selectedToken = analysis?.tokens.find((token) => token.token_index === selectedIndex) ?? analysis?.tokens[0] ?? null;
  $: selectedMatches = selectedToken ? analysis?.library.token_matches[String(selectedToken.token_index)] ?? [] : [];
  $: selectedGrammar = selectedToken?.grammar
    ? analysis?.grammar.find((rule) => rule.rule_id === selectedToken?.grammar?.rule_id) ?? null
    : null;

  function tokenMeaning(token: LanguageAnalyzerToken): string {
    const match = analysis?.library.token_matches[String(token.token_index)]?.[0];
    return match?.english || match?.mongolian || '';
  }

  function colorClass(token: LanguageAnalyzerToken): string {
    return `token-${token.color_group}`;
  }

  function usefulLemma(token: LanguageAnalyzerToken): string {
    return token.group_lemma || token.lemma || token.form;
  }

  async function loadLocalState() {
    try {
      const [nextStatus, nextHistory] = await Promise.all([
        languageApi.analyzerStatus(),
        languageApi.analyzerHistory(),
      ]);
      status = nextStatus;
      history = nextHistory.items;
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function runAnalysis() {
    if (!text.trim() || loading) return;
    loading = true;
    error = '';
    message = '';
    dictionaryEntries = [];
    currentSavedId = undefined;
    try {
      analysis = await languageApi.analyze(text);
      text = analysis.text;
      translationEn = analysis.translation.en;
      translationMn = analysis.translation.mn;
      selectedIndex = analysis.tokens[0]?.token_index ?? 0;
      message = analysis.cached
        ? 'Opened the local analysis cache. Library meanings were refreshed.'
        : `Analyzed locally with ${analysis.engine.name} ${analysis.engine.version ?? ''}.`;
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      loading = false;
    }
  }

  function speak() {
    if (!text.trim() || typeof speechSynthesis === 'undefined') return;
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'ko-KR';
    utterance.rate = 0.88;
    speechSynthesis.speak(utterance);
  }

  async function playMatchedExample() {
    const example = analysis?.library.exact_example;
    if (!example?.has_sentence_audio) return;
    try {
      await new Audio(
        languageApi.mediaUrl(example.word_id, 'sentence_audio'),
      ).play();
    } catch {
      error = 'Local sentence audio needs a click in this browser.';
    }
  }

  async function save() {
    if (!analysis || saving) return;
    saving = true;
    error = '';
    try {
      const response = await languageApi.saveAnalysis(
        analysis,
        translationEn,
        translationMn,
        currentSavedId,
      );
      currentSavedId = response.item.analysis_id;
      history = [
        response.item,
        ...history.filter((item) => item.analysis_id !== response.item.analysis_id),
      ];
      message = 'Analysis saved to your local Languages history.';
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      saving = false;
    }
  }

  function openSaved(item: LanguageSavedAnalysis) {
    text = item.source_text;
    analysis = item.analysis;
    translationEn = item.translation_en;
    translationMn = item.translation_mn;
    currentSavedId = item.analysis_id;
    selectedIndex = item.analysis.tokens[0]?.token_index ?? 0;
    showHistory = false;
    dictionaryEntries = [];
    message = 'Opened a saved local analysis.';
  }

  async function retireSaved(item: LanguageSavedAnalysis, event: MouseEvent) {
    event.stopPropagation();
    if (!window.confirm('Retire this saved analysis? Its row is preserved as history.')) return;
    try {
      await languageApi.retireAnalysis(item.analysis_id);
      history = history.filter((value) => value.analysis_id !== item.analysis_id);
      if (currentSavedId === item.analysis_id) currentSavedId = undefined;
    } catch (cause) {
      error = (cause as Error).message;
    }
  }

  async function lookupDictionary() {
    if (!selectedToken || dictionaryBusy) return;
    dictionaryBusy = true;
    error = '';
    try {
      const response = await languageApi.dictionaryLookup(usefulLemma(selectedToken));
      dictionaryEntries = response.entries;
      message = response.cached ? 'Opened cached KRDICT meanings.' : 'KRDICT lookup complete.';
    } catch (cause) {
      error = (cause as Error).message;
    } finally {
      dictionaryBusy = false;
    }
  }

  function addSelectedWord() {
    if (!selectedToken) return;
    const english = selectedMatches[0]?.english
      || dictionaryEntries.find((entry) => entry.language === 'en')?.definition
      || '';
    const mongolian = selectedMatches[0]?.mongolian
      || dictionaryEntries.find((entry) => entry.language === 'mn')?.definition
      || '';
    dispatch('addword', {
      headword: usefulLemma(selectedToken),
      sentence_form: selectedToken.original_surface || selectedToken.surface,
      reading: selectedToken.romanization,
      senses: [
        ...(english ? [{ lang: 'en', text: english }] : []),
        ...(mongolian ? [{ lang: 'mn', text: mongolian }] : []),
      ],
      examples: [{
        sentence: analysis?.text ?? '',
        translations: [
          ...(translationEn ? [{ lang: 'en', text: translationEn }] : []),
          ...(translationMn ? [{ lang: 'mn', text: translationMn }] : []),
        ],
      }],
      tags: ['analyzer'],
    });
  }

  onMount(loadLocalState);
</script>

<section class="analyzer-shell">
  <header class="analyzer-heading">
    <div>
      <p>Local Korean workbench</p>
      <h2>Sentence Analyzer</h2>
      <span>Kiwi morphology · Keivotos grammar · your Anki meanings</span>
    </div>
    <div class="heading-actions">
      <span class:ready={status?.available}>{status?.available ? `Kiwi ${status.engine_version}` : 'Engine loading'}</span>
      <button type="button" on:click={() => showHistory = !showHistory}>History {history.length ? `· ${history.length}` : ''}</button>
    </div>
  </header>

  {#if error}<div class="notice error">{error}</div>{/if}
  {#if message}<div class="notice">{message}</div>{/if}

  <div class="input-stage">
    <div class="input-card">
      <button type="button" class="speak" on:click={speak} aria-label="Speak Korean text" title="Use the installed Korean system voice">♪</button>
      <textarea
        bind:value={text}
        maxlength={status?.max_text_length ?? 5000}
        placeholder="분석할 한국어 문장이나 문단을 붙여넣으세요…"
        aria-label="Korean text to analyze"
        on:keydown={(event) => {
          if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            void runAnalysis();
          }
        }}
      ></textarea>
      <div class="input-footer">
        <span>{text.length.toLocaleString()} / {(status?.max_text_length ?? 5000).toLocaleString()}</span>
        <span class="local-badge">Runs locally</span>
        <button type="button" class="analyze-button" disabled={!text.trim() || loading} on:click={runAnalysis}>{loading ? 'Analyzing…' : 'Analyze sentence'}</button>
      </div>
    </div>
    {#if analysis?.romanization}<p class="romanization">{analysis.romanization}</p>{/if}
  </div>

  {#if analysis}
    <div class="analysis-stage">
      <div class="rail-label"><span>Morphology rail</span><small>Scroll sideways on long sentences · select any piece</small></div>
      <div class="token-rail" role="region" aria-label="Analyzed Korean tokens">
        {#each analysis.tokens as token (token.token_index)}
          <button
            type="button"
            class="token {colorClass(token)}"
            class:selected={selectedToken?.token_index === token.token_index}
            class:new-group={token.token_index > 0 && analysis.tokens[token.token_index - 1]?.group !== token.group}
            on:click={() => { selectedIndex = token.token_index; dictionaryEntries = []; }}
          >
            <span class="lemma">{usefulLemma(token) !== token.surface ? usefulLemma(token) : ''}</span>
            <strong>{token.surface}</strong>
            <span class="gloss">{tokenMeaning(token) || token.grammar?.title || ' '}</span>
            <small>{token.pos}</small>
          </button>
        {/each}
      </div>

      <div class="translation-card">
        <div class="translation-heading">
          <span>Meaning</span>
          <small>{analysis.translation.provenance} · editable before saving</small>
        </div>
        <label><span>EN</span><textarea bind:value={translationEn} placeholder="Add your English translation"></textarea></label>
        <label><span>MN</span><textarea bind:value={translationMn} placeholder="Монгол орчуулгаа нэмнэ үү"></textarea></label>
        <div class="translation-actions">
          <button type="button" on:click={speak}>♪ Listen</button>
          {#if analysis.library.exact_example?.has_sentence_audio}<button type="button" on:click={playMatchedExample}>♫ Anki example</button>{/if}
          <button type="button" class="save" disabled={saving} on:click={save}>{saving ? 'Saving…' : currentSavedId ? 'Update saved analysis' : 'Save analysis'}</button>
        </div>
      </div>

      {#if selectedToken}
        <div class="token-inspector">
          <div class="selected-token">
            <p>Selected morphology</p>
            <h3>{selectedToken.surface}</h3>
            <span>{usefulLemma(selectedToken)} · {selectedToken.tag} · {selectedToken.romanization}</span>
            <div class="provenance-row">
              <i>Kiwi morphology</i>
              {#if selectedGrammar}<i>Keivotos rule</i>{/if}
              {#if selectedMatches[0]}<i>{selectedMatches[0].provenance}</i>{/if}
            </div>
            <div class="token-actions">
              {#if selectedMatches.length}
                {#each selectedMatches as match}
                  <button type="button" class="open-word" on:click={() => dispatch('openword', match.word_id)}>Open {match.headword}</button>
                {/each}
              {:else}
                <button type="button" class="add-word" on:click={addSelectedWord}>+ Add lemma to Languages</button>
              {/if}
              {#if status?.dictionary.configured}
                <button type="button" disabled={dictionaryBusy} on:click={lookupDictionary}>{dictionaryBusy ? 'Looking up…' : 'Look up in KRDICT'}</button>
              {:else}
                <span class="dictionary-hint">Optional KRDICT lookup can be enabled in Languages settings.</span>
              {/if}
            </div>
          </div>
          <div class="explanation">
            <p>{selectedGrammar ? selectedGrammar.title : selectedToken.pos}</p>
            <h4>{selectedGrammar?.pattern || usefulLemma(selectedToken)}</h4>
            <span>{selectedGrammar?.summary || 'Kiwi identified this item by its grammatical role in the sentence. Select another token to compare the structure.'}</span>
          </div>
        </div>
      {/if}

      {#if dictionaryEntries.length}
        <section class="dictionary-results">
          <div><p>Official dictionary enrichment</p><h3>KRDICT · {selectedToken ? usefulLemma(selectedToken) : ''}</h3></div>
          <div class="dictionary-grid">
            {#each dictionaryEntries.slice(0, 8) as entry}
              <article>
                <span>{entry.language.toUpperCase()} · {entry.part_of_speech || 'entry'}</span>
                <strong>{entry.translated_word || entry.word}</strong>
                <p>{entry.definition}</p>
              </article>
            {/each}
          </div>
          {#if !selectedMatches.length}<button type="button" class="use-dictionary" on:click={addSelectedWord}>Use these meanings in a new word</button>{/if}
        </section>
      {/if}

      {#if analysis.grammar.length}
        <section class="grammar-section">
          <div class="section-heading"><p>Related structure</p><h3>Grammar found in this sentence</h3></div>
          <div class="grammar-grid">
            {#each analysis.grammar as rule}
              <button type="button" on:click={() => selectedIndex = rule.token_indexes[0]}>
                <span>{rule.level}</span>
                <small>{rule.category}</small>
                <strong>{rule.pattern}</strong>
                <h4>{rule.title}</h4>
                <p>{rule.summary}</p>
                <i>Inspect token →</i>
              </button>
            {/each}
          </div>
        </section>
      {/if}
    </div>
  {:else}
    <div class="analyzer-empty">
      <div class="sentence-ghost"><span>비록</span><span>우리</span><span>가</span><span>예상했</span><span>던</span><span>것</span><span>보다</span></div>
      <h3>See how a Korean sentence is built</h3>
      <p>Paste text above. Keivotos will separate sentences, identify morphemes and grammar, romanize the reading, and connect learned words from your local Anki mirror.</p>
      <div><span>No account</span><span>No automatic network</span><span>No Anki writes</span></div>
    </div>
  {/if}

  {#if showHistory}
    <aside class="history-panel">
      <div class="history-header"><div><p>Your local notes</p><h3>Analyzer history</h3></div><button type="button" on:click={() => showHistory = false}>×</button></div>
      {#if history.length}
        <div class="history-list">
          {#each history as item}
            <div class="history-item">
              <button type="button" class="history-open" on:click={() => openSaved(item)}>
                <strong>{item.source_text}</strong>
                <span>{item.translation_en || item.translation_mn || 'No saved translation'}</span>
                <small>{new Date(item.updated_at).toLocaleString()}</small>
              </button>
              <button type="button" class="history-retire" title="Retire saved analysis" aria-label="Retire saved analysis" on:click={(event) => retireSaved(item, event)}>×</button>
            </div>
          {/each}
        </div>
      {:else}
        <p class="history-empty">Save an analysis and it will appear here. Pasted text is not retained automatically.</p>
      {/if}
    </aside>
  {/if}
</section>

<style>
  .analyzer-shell { position:relative; min-height:44rem; overflow:hidden; border:1px solid rgba(255,255,255,.08); border-radius:1.35rem; background:radial-gradient(circle at 50% -20%,rgba(45,212,191,.1),transparent 32rem),#f6f4ef; color:#28272b; box-shadow:0 25px 80px rgba(0,0,0,.24); }
  .analyzer-heading { display:flex; align-items:center; justify-content:space-between; gap:1rem; border-bottom:1px solid rgba(25,24,29,.09); background:rgba(255,255,255,.78); padding:1rem 1.4rem; backdrop-filter:blur(16px); }
  .analyzer-heading p,.section-heading p,.history-header p,.dictionary-results>div>p { color:#119b98; font-size:.56rem; font-weight:850; letter-spacing:.16em; text-transform:uppercase; }
  .analyzer-heading h2 { margin-top:.1rem; font-size:1.35rem; font-weight:900; }
  .analyzer-heading>div>span { display:block; margin-top:.2rem; color:#77747c; font-size:.62rem; }
  .heading-actions { display:flex; align-items:center; gap:.5rem; }
  .heading-actions span,.heading-actions button { border:1px solid rgba(25,24,29,.1); border-radius:999px; padding:.42rem .7rem; color:#77747c; font-size:.59rem; font-weight:700; }
  .heading-actions span.ready { border-color:rgba(17,155,152,.2); background:rgba(17,155,152,.07); color:#087b79; }
  .heading-actions button:hover { background:white; color:#29272d; }
  .notice { margin:.75rem 1.4rem 0; border:1px solid rgba(17,155,152,.15); border-radius:.65rem; background:rgba(17,155,152,.06); padding:.55rem .75rem; color:#087b79; font-size:.62rem; }
  .notice.error { border-color:rgba(220,38,38,.15); background:rgba(220,38,38,.05); color:#b42323; }
  .input-stage { display:grid; place-items:center; padding:2.4rem 1rem 1.4rem; }
  .input-card { position:relative; width:min(42rem,100%); border:1px solid rgba(25,24,29,.12); border-radius:1rem; background:white; box-shadow:0 14px 38px rgba(39,35,45,.07); }
  .speak { position:absolute; left:.75rem; top:.8rem; display:grid; height:1.8rem; width:1.8rem; place-items:center; border-radius:999px; color:#77747c; }
  .speak:hover { background:#f0efec; color:#119b98; }
  .input-card textarea { display:block; min-height:6.2rem; width:100%; resize:vertical; border:0; background:transparent; padding:1rem 1rem .6rem 3rem; color:#343139; font-size:.82rem; line-height:1.8; outline:none; }
  .input-footer { display:flex; align-items:center; gap:.55rem; border-top:1px solid rgba(25,24,29,.07); padding:.5rem .6rem .5rem .9rem; }
  .input-footer>span { color:#aaa6ae; font-size:.55rem; }
  .input-footer .local-badge { margin-left:auto; border-radius:999px; background:#eef7f5; padding:.25rem .45rem; color:#2c8d87; font-weight:750; }
  .analyze-button { border-radius:.65rem; background:#63c8c1; padding:.52rem .8rem; color:white; font-size:.62rem; font-weight:800; box-shadow:0 5px 14px rgba(17,155,152,.18); }
  .analyze-button:hover { background:#48b8b1; }
  .analyze-button:disabled { opacity:.45; }
  .romanization { width:min(54rem,100%); margin-top:.65rem; color:#b4b0b7; font-size:.6rem; line-height:1.7; text-align:center; }
  .analysis-stage { padding:0 1.4rem 2.4rem; }
  .rail-label { display:flex; align-items:center; justify-content:space-between; width:min(76rem,100%); margin:0 auto .45rem; }
  .rail-label span { color:#626068; font-size:.65rem; font-weight:800; }
  .rail-label small { color:#aaa6ae; font-size:.55rem; }
  .token-rail { display:flex; width:min(76rem,100%); margin:0 auto; overflow-x:auto; border-bottom:2px solid rgba(25,24,29,.12); padding:.2rem .15rem .55rem; scrollbar-color:rgba(17,155,152,.25) transparent; scroll-snap-type:x proximity; }
  .token { --token:#55525a; position:relative; display:grid; min-width:5.25rem; max-width:8.5rem; flex:0 0 auto; grid-template-rows:1rem 1.75rem 1.15rem 1rem; align-items:center; border-radius:.55rem; padding:.25rem .4rem; text-align:center; scroll-snap-align:center; transition:background 140ms,transform 140ms; }
  .token.new-group { margin-left:.65rem; }
  .token.new-group::before { position:absolute; left:-.36rem; top:22%; height:58%; width:1px; content:""; background:rgba(25,24,29,.09); }
  .token:hover,.token.selected { background:rgba(255,255,255,.8); transform:translateY(-2px); box-shadow:0 8px 20px rgba(39,35,45,.06); }
  .token.selected::after { position:absolute; right:22%; bottom:-.62rem; left:22%; height:2px; content:""; background:var(--token); }
  .token .lemma { overflow:hidden; color:#49aaa5; font-size:.55rem; font-weight:700; text-overflow:ellipsis; white-space:nowrap; }
  .token strong { overflow:hidden; color:#343139; font-size:.98rem; font-weight:900; text-overflow:ellipsis; white-space:nowrap; }
  .token .gloss { overflow:hidden; color:var(--token); font-size:.54rem; font-weight:700; text-overflow:ellipsis; white-space:nowrap; }
  .token small { overflow:hidden; color:#aaa6ae; font-size:.49rem; text-overflow:ellipsis; white-space:nowrap; }
  .token-noun { --token:#d77d2d; }
  .token-verb { --token:#e65e57; }
  .token-adjective { --token:#9965d7; }
  .token-particle { --token:#ad63d8; }
  .token-ending { --token:#6c74da; }
  .token-modifier { --token:#2f9d87; }
  .token-affix { --token:#c75d94; }
  .translation-card { width:min(54rem,100%); margin:2rem auto 0; border:1px solid rgba(25,24,29,.1); border-radius:.8rem; background:rgba(255,255,255,.72); padding:.8rem; box-shadow:0 10px 30px rgba(39,35,45,.05); }
  .translation-heading { display:flex; justify-content:space-between; padding:.1rem .2rem .55rem; }
  .translation-heading span { color:#d77d2d; font-size:.62rem; font-weight:800; }
  .translation-heading small { color:#aaa6ae; font-size:.52rem; }
  .translation-card label { display:grid; grid-template-columns:2rem minmax(0,1fr); align-items:start; gap:.45rem; border-top:1px solid rgba(25,24,29,.06); padding:.55rem .2rem; }
  .translation-card label span { padding-top:.25rem; color:#a29ea6; font-size:.55rem; font-weight:850; }
  .translation-card textarea { min-height:2.3rem; resize:vertical; background:transparent; color:#55515a; font-size:.66rem; line-height:1.55; outline:none; }
  .translation-actions { display:flex; justify-content:end; gap:.4rem; border-top:1px solid rgba(25,24,29,.06); padding-top:.6rem; }
  .translation-actions button { border:1px solid rgba(25,24,29,.1); border-radius:.55rem; padding:.45rem .65rem; color:#6d6971; font-size:.57rem; font-weight:700; }
  .translation-actions .save { border-color:#65c9c1; background:#65c9c1; color:white; }
  .token-inspector { display:grid; width:min(54rem,100%); grid-template-columns:1.15fr .85fr; gap:.65rem; margin:1.3rem auto 0; }
  .selected-token,.explanation { border:1px solid rgba(25,24,29,.09); border-radius:.85rem; background:rgba(255,255,255,.64); padding:1rem; }
  .selected-token>p { color:#119b98; font-size:.52rem; font-weight:850; letter-spacing:.14em; text-transform:uppercase; }
  .selected-token h3 { margin-top:.4rem; color:#343139; font-size:1.55rem; font-weight:950; }
  .selected-token>span { color:#8f8b93; font-size:.6rem; }
  .provenance-row { display:flex; flex-wrap:wrap; gap:.25rem; margin-top:.65rem; }
  .provenance-row i { border-radius:999px; background:#edf5f3; padding:.22rem .42rem; color:#3a8c86; font-size:.49rem; font-style:normal; }
  .token-actions { display:flex; flex-wrap:wrap; gap:.35rem; margin-top:.8rem; }
  .token-actions button { border:1px solid rgba(25,24,29,.1); border-radius:.55rem; padding:.42rem .58rem; color:#656169; font-size:.55rem; font-weight:700; }
  .token-actions button:hover,.token-actions .add-word { border-color:rgba(17,155,152,.3); background:rgba(17,155,152,.06); color:#087b79; }
  .dictionary-hint { align-self:center; color:#aaa6ae !important; font-size:.52rem !important; }
  .explanation p { color:#9a70d5; font-size:.52rem; font-weight:850; text-transform:uppercase; }
  .explanation h4 { margin-top:.45rem; color:#4b4850; font-size:1.15rem; font-weight:850; }
  .explanation span { display:block; margin-top:.45rem; color:#77737b; font-size:.62rem; line-height:1.65; }
  .dictionary-results,.grammar-section { width:min(54rem,100%); margin:1.6rem auto 0; }
  .dictionary-results>div>h3,.section-heading h3 { margin-top:.18rem; color:#55515a; font-size:.9rem; font-weight:850; }
  .dictionary-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.45rem; margin-top:.6rem; }
  .dictionary-grid article { border:1px solid rgba(25,24,29,.08); border-radius:.7rem; background:rgba(255,255,255,.62); padding:.7rem; }
  .dictionary-grid span { color:#99959d; font-size:.48rem; font-weight:800; text-transform:uppercase; }
  .dictionary-grid strong { display:block; margin-top:.2rem; color:#3f3c43; font-size:.7rem; }
  .dictionary-grid p { margin-top:.25rem; color:#77737b; font-size:.58rem; line-height:1.5; }
  .use-dictionary { margin-top:.55rem; border-radius:.55rem; background:#65c9c1; padding:.48rem .65rem; color:white; font-size:.56rem; font-weight:750; }
  .grammar-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(11rem,1fr)); gap:.6rem; margin-top:.65rem; }
  .grammar-grid button { display:flex; min-height:10rem; flex-direction:column; align-items:start; border:1px solid rgba(25,24,29,.08); border-radius:.8rem; background:rgba(255,255,255,.68); padding:.8rem; text-align:left; box-shadow:0 8px 22px rgba(39,35,45,.04); transition:transform 150ms,box-shadow 150ms; }
  .grammar-grid button:hover { transform:translateY(-3px); box-shadow:0 14px 30px rgba(39,35,45,.08); }
  .grammar-grid span { border-radius:999px; background:#d9eddb; padding:.18rem .38rem; color:#589063; font-size:.47rem; font-weight:800; }
  .grammar-grid small { margin-top:.65rem; color:#aaa6ae; font-size:.48rem; font-weight:800; text-transform:uppercase; }
  .grammar-grid strong { margin-top:.35rem; color:#55515a; font-size:1rem; }
  .grammar-grid h4 { margin-top:.25rem; color:#706c74; font-size:.62rem; font-weight:800; }
  .grammar-grid p { margin-top:.35rem; color:#8e8a92; font-size:.55rem; line-height:1.5; }
  .grammar-grid i { margin-top:auto; padding-top:.55rem; color:#4dafaa; font-size:.51rem; font-style:normal; font-weight:750; }
  .analyzer-empty { display:grid; min-height:25rem; place-items:center; align-content:center; padding:2rem; text-align:center; }
  .sentence-ghost { display:flex; flex-wrap:wrap; justify-content:center; gap:.25rem; color:#6c696f; }
  .sentence-ghost span { border-bottom:2px solid rgba(17,155,152,.18); padding:.3rem .42rem; font-size:.8rem; font-weight:800; }
  .sentence-ghost span:nth-child(3n) { border-color:rgba(153,101,215,.25); }
  .analyzer-empty h3 { margin-top:1.5rem; font-size:1.2rem; font-weight:900; }
  .analyzer-empty p { max-width:36rem; margin-top:.5rem; color:#88848c; font-size:.68rem; line-height:1.7; }
  .analyzer-empty>div:last-child { display:flex; flex-wrap:wrap; justify-content:center; gap:.35rem; margin-top:1rem; }
  .analyzer-empty>div:last-child span { border:1px solid rgba(25,24,29,.08); border-radius:999px; padding:.32rem .52rem; color:#8c8990; font-size:.52rem; }
  .history-panel { position:absolute; z-index:30; right:0; top:0; bottom:0; width:min(23rem,92%); overflow-y:auto; border-left:1px solid rgba(25,24,29,.1); background:rgba(250,249,246,.97); box-shadow:-25px 0 70px rgba(39,35,45,.16); backdrop-filter:blur(18px); animation:history-in 180ms ease-out both; }
  .history-header { position:sticky; top:0; z-index:2; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid rgba(25,24,29,.08); background:rgba(250,249,246,.92); padding:1rem; }
  .history-header h3 { margin-top:.15rem; font-size:1rem; font-weight:900; }
  .history-header button { display:grid; height:2rem; width:2rem; place-items:center; border-radius:999px; color:#88848c; }
  .history-header button:hover { background:#eceae6; color:#333137; }
  .history-list { padding:.6rem; }
  .history-item { position:relative; border-radius:.7rem; }
  .history-item:hover { background:white; }
  .history-open { display:block; width:100%; padding:.7rem 2rem .7rem .7rem; text-align:left; }
  .history-list strong,.history-list span,.history-list small { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .history-list strong { color:#49464d; font-size:.68rem; }
  .history-list span { margin-top:.25rem; color:#8d8991; font-size:.57rem; }
  .history-list small { margin-top:.35rem; color:#b0acb3; font-size:.49rem; }
  .history-retire { position:absolute; right:.55rem; top:.55rem; display:grid; height:1.5rem; width:1.5rem; place-items:center; border-radius:999px; color:#b0acb3; }
  .history-retire:hover { background:#f4e3e3; color:#b42323; }
  .history-empty { padding:2rem 1rem; color:#8d8991; font-size:.62rem; line-height:1.65; text-align:center; }

  /* Keivotos owns the presentation; Kiwi supplies morphology only. */
  .analyzer-shell { border-color:rgba(255,255,255,.08); background:radial-gradient(circle at 50% -15%,rgba(20,184,166,.1),transparent 30rem),#121119; color:rgba(255,255,255,.86); box-shadow:0 25px 80px rgba(0,0,0,.38); }
  .analyzer-heading { border-color:rgba(255,255,255,.08); background:rgba(18,17,25,.88); }
  .analyzer-heading>div>span,.rail-label small,.input-footer>span,.romanization { color:rgba(255,255,255,.3); }
  .heading-actions span,.heading-actions button { border-color:rgba(255,255,255,.09); color:rgba(255,255,255,.45); }
  .heading-actions span.ready { border-color:rgba(45,212,191,.2); background:rgba(45,212,191,.07); color:rgba(153,246,228,.72); }
  .heading-actions button:hover { background:rgba(255,255,255,.07); color:white; }
  .notice { border-color:rgba(45,212,191,.18); background:rgba(45,212,191,.06); color:rgba(153,246,228,.76); }
  .notice.error { border-color:rgba(248,113,113,.2); background:rgba(248,113,113,.06); color:rgb(252 165 165); }
  .input-card { border-color:rgba(255,255,255,.1); background:#191820; box-shadow:0 14px 38px rgba(0,0,0,.25); }
  .input-card textarea { color:rgba(255,255,255,.82); }
  .input-footer { border-color:rgba(255,255,255,.07); }
  .input-footer .local-badge { background:rgba(45,212,191,.08); color:rgba(153,246,228,.72); }
  .speak { color:rgba(255,255,255,.42); }
  .speak:hover { background:rgba(255,255,255,.07); color:rgb(153 246 228); }
  .rail-label span { color:rgba(255,255,255,.6); }
  .token-rail { border-color:rgba(255,255,255,.1); }
  .token.new-group::before { background:rgba(255,255,255,.08); }
  .token:hover,.token.selected { background:rgba(255,255,255,.06); box-shadow:0 8px 20px rgba(0,0,0,.2); }
  .token strong { color:rgba(255,255,255,.9); }
  .token small { color:rgba(255,255,255,.3); }
  .translation-card,.selected-token,.explanation,.dictionary-grid article,.grammar-grid button { border-color:rgba(255,255,255,.09); background:rgba(255,255,255,.035); box-shadow:0 10px 30px rgba(0,0,0,.12); }
  .translation-card label,.translation-actions { border-color:rgba(255,255,255,.07); }
  .translation-heading small,.translation-card label span { color:rgba(255,255,255,.3); }
  .translation-card textarea { color:rgba(255,255,255,.67); }
  .translation-actions button,.token-actions button { border-color:rgba(255,255,255,.1); color:rgba(255,255,255,.55); }
  .selected-token h3,.explanation h4,.dictionary-results>div>h3,.section-heading h3,.dictionary-grid strong,.grammar-grid strong { color:rgba(255,255,255,.82); }
  .selected-token>span,.explanation span,.dictionary-grid p,.grammar-grid h4,.grammar-grid p { color:rgba(255,255,255,.42); }
  .provenance-row i { background:rgba(45,212,191,.08); color:rgba(153,246,228,.65); }
  .dictionary-hint,.dictionary-grid span,.grammar-grid small { color:rgba(255,255,255,.3) !important; }
  .grammar-grid button:hover { box-shadow:0 14px 30px rgba(0,0,0,.25); }
  .sentence-ghost { color:rgba(255,255,255,.58); }
  .analyzer-empty p,.analyzer-empty>div:last-child span { color:rgba(255,255,255,.36); }
  .analyzer-empty>div:last-child span { border-color:rgba(255,255,255,.08); }
  .history-panel { border-color:rgba(255,255,255,.09); background:rgba(17,16,23,.98); box-shadow:-25px 0 70px rgba(0,0,0,.4); }
  .history-header { border-color:rgba(255,255,255,.08); background:rgba(17,16,23,.94); }
  .history-header button,.history-retire { color:rgba(255,255,255,.35); }
  .history-header button:hover,.history-item:hover { background:rgba(255,255,255,.06); color:white; }
  .history-list strong { color:rgba(255,255,255,.72); }
  .history-list span,.history-empty { color:rgba(255,255,255,.36); }
  .history-list small { color:rgba(255,255,255,.24); }
  .history-retire:hover { background:rgba(248,113,113,.1); color:rgb(252 165 165); }
  @keyframes history-in { from { opacity:0; transform:translateX(12px); } to { opacity:1; transform:translateX(0); } }
  @media (max-width: 700px) {
    .analyzer-heading { align-items:start; flex-direction:column; }
    .analysis-stage { padding-right:.75rem; padding-left:.75rem; }
    .rail-label { align-items:start; flex-direction:column; }
    .token-inspector { grid-template-columns:1fr; }
    .dictionary-grid { grid-template-columns:1fr; }
    .translation-heading { align-items:start; flex-direction:column; gap:.2rem; }
  }
  :global(html[data-motion='reduced']) .token,:global(html[data-motion='reduced']) .grammar-grid button,:global(html[data-motion='reduced']) .history-panel { animation:none; transition:none; }
</style>
