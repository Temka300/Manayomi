<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { LanguageList, LanguageWord } from '../../lib/languageApi';
  import LanguageWordMenu from './LanguageWordMenu.svelte';

  export let items: LanguageWord[] = [];
  export let lists: LanguageList[] = [];
  export let selectedWord: LanguageWord | null = null;
  export let sort = 'index';
  export let descending = false;
  export let offset = 0;

  const dispatch = createEventDispatcher<{
    select: LanguageWord;
    closeinspector: void;
    details: LanguageWord;
    edit: LanguageWord;
    favorite: LanguageWord;
    addtolist: { word: LanguageWord; listId: string };
    sort: string;
  }>();

  function sense(word: LanguageWord, lang: string): string {
    return word.senses.find((value) => value.lang === lang)?.text ?? '';
  }

  function sortHeader(key: string, label: string) {
    return { key, label };
  }

  const headers = [
    sortHeader('index', 'Number'),
    sortHeader('source', 'Source'),
    sortHeader('korean', 'Korean'),
    sortHeader('sentence_form', 'Sentence form'),
    sortHeader('english', 'English'),
    sortHeader('mongolian', 'Mongolian'),
    sortHeader('note_type', 'Note type'),
    sortHeader('deck', 'Deck'),
    sortHeader('interval', 'Mastery'),
    sortHeader('due', 'Due'),
    sortHeader('media', 'Media'),
    sortHeader('flags', 'Flags'),
  ];
</script>

<section class="browser-shell" aria-label="Language library browser">
  <div class="table-shell">
    <table>
      <thead>
        <tr>
          {#each headers as header}
            <th class:active={sort === header.key}>
              <button type="button" on:click={() => dispatch('sort', header.key)}>
                {header.label}
                {#if sort === header.key}<span aria-hidden="true">{descending ? '↓' : '↑'}</span>{/if}
              </button>
            </th>
          {/each}
          <th class="actions"><span class="sr-only">Actions</span></th>
        </tr>
      </thead>
      <tbody>
        {#each items as word, rowIndex (word.word_id)}
          <tr
            class:selected={selectedWord?.word_id === word.word_id}
            tabindex="0"
            on:click={() => dispatch('select', word)}
            on:keydown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                dispatch('select', word);
              }
            }}
          >
            <td class="number">{word.sort_index ?? offset + rowIndex + 1}</td>
            <td><span class="source-badge {word.source}">{word.source === 'anki' ? 'Anki' : 'Manual'}</span><small>{word.source === 'anki' ? `#${word.source_key}` : 'Keivotos'}</small></td>
            <td class="korean"><strong>{word.headword}</strong>{#if word.reading}<small>{word.reading}</small>{/if}</td>
            <td class="sentence-form">{word.sentence_form !== word.headword ? word.sentence_form : '—'}</td>
            <td class:missing-value={!sense(word, 'en')}>{sense(word, 'en') || '—'}</td>
            <td class:missing-value={!sense(word, 'mn')}>{sense(word, 'mn') || '—'}</td>
            <td>{word.note_type || 'Keivotos'}</td>
            <td class="deck" title={word.deck}>{word.deck || 'Keivotos'}</td>
            <td><span class="stage {word.stage}">{word.stage}</span><small>{word.weakest_interval}d interval</small></td>
            <td>{word.due_now ? 'Today' : word.progress[0]?.due ?? '—'}</td>
            <td><span class="media-dots" aria-label="Available media"><i class:available={!!word.media_by_role.word_audio}>A</i><i class:available={!!word.media_by_role.sentence_audio}>S</i><i class:available={!!word.media_by_role.image}>I</i></span></td>
            <td><div class="flags">{#if word.edited}<span>Edited</span>{/if}{#if word.missing}<span class="danger">Missing</span>{/if}{#if word.suspended}<span>Suspended</span>{/if}{#if !word.edited && !word.missing && !word.suspended}<span>—</span>{/if}</div></td>
            <td class="actions"><LanguageWordMenu compact {word} {lists} on:edit={(event) => dispatch('edit', event.detail)} on:details={(event) => dispatch('details', event.detail)} on:favorite={(event) => dispatch('favorite', event.detail)} on:addtolist={(event) => dispatch('addtolist', event.detail)} /></td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  {#if selectedWord}
    <aside class="inspector">
      <button type="button" class="close" aria-label="Close word inspector" on:click={() => dispatch('closeinspector')}>×</button>
      <p class="eyebrow">{selectedWord.source === 'anki' ? 'Anki mirror' : 'Keivotos word'} · {selectedWord.sort_index ?? 'unindexed'}</p>
      <h2>{selectedWord.headword}</h2>
      {#if selectedWord.sentence_form !== selectedWord.headword}<p class="form">{selectedWord.sentence_form}</p>{/if}
      {#if selectedWord.reading}<p class="reading">{selectedWord.reading}</p>{/if}

      <div class="meaning-stack">
        <div><span>English</span><p>{sense(selectedWord, 'en') || 'No English meaning'}</p></div>
        <div><span>Mongolian</span><p>{sense(selectedWord, 'mn') || 'No Mongolian meaning'}</p></div>
      </div>

      {#if selectedWord.examples[0]}
        <div class="inspector-block">
          <span>Example</span>
          <p class="example">{selectedWord.examples[0].sentence}</p>
          <small>{selectedWord.examples[0].translations.map((value) => value.text).join(' · ')}</small>
        </div>
      {/if}

      <div class="facts">
        <div><span>Stage</span><strong class="capitalize">{selectedWord.stage}</strong></div>
        <div><span>Interval</span><strong>{selectedWord.weakest_interval} days</strong></div>
        <div><span>Cards</span><strong>{selectedWord.progress.length}</strong></div>
        <div><span>Note type</span><strong>{selectedWord.note_type || 'Keivotos'}</strong></div>
      </div>

      <div class="inspector-block">
        <span>Deck</span>
        <p>{selectedWord.deck || 'Keivotos'}</p>
      </div>

      <div class="inspector-actions">
        <button type="button" on:click={() => dispatch('details', selectedWord)}>Open details</button>
        <button type="button" class="accent" on:click={() => dispatch('edit', selectedWord)}>Edit locally</button>
      </div>
    </aside>
  {/if}
</section>

<style>
  .browser-shell { display:flex; min-height:34rem; overflow:hidden; border:1px solid rgba(255,255,255,.09); border-radius:1.1rem; background:#111016; box-shadow:0 20px 60px rgba(0,0,0,.18); }
  .table-shell { min-width:0; flex:1; overflow:auto; scrollbar-color:rgba(251,191,36,.2) transparent; }
  table { width:100%; min-width:112rem; border-collapse:separate; border-spacing:0; font-size:.68rem; }
  thead { position:sticky; top:0; z-index:4; background:rgba(20,19,26,.97); backdrop-filter:blur(14px); }
  th { border-bottom:1px solid rgba(255,255,255,.09); color:rgba(255,255,255,.3); font-size:.57rem; font-weight:800; letter-spacing:.08em; text-align:left; text-transform:uppercase; }
  th button { display:flex; width:100%; align-items:center; gap:.35rem; padding:.78rem .7rem; white-space:nowrap; }
  th.active,th button:hover { color:rgb(253 230 138); }
  tbody tr { cursor:pointer; outline:none; transition:background 120ms,box-shadow 120ms; }
  tbody tr:hover,tbody tr:focus-visible { background:rgba(255,255,255,.035); }
  tbody tr.selected { background:rgba(251,191,36,.075); box-shadow:inset 3px 0 rgb(251 191 36 / .72); }
  td { max-width:16rem; border-bottom:1px solid rgba(255,255,255,.055); padding:.66rem .7rem; color:rgba(255,255,255,.5); vertical-align:middle; }
  td small { display:block; margin-top:.15rem; color:rgba(255,255,255,.22); font-size:.57rem; }
  td.number { color:rgba(251,191,36,.55); font-variant-numeric:tabular-nums; }
  td.korean strong { color:white; font-size:.9rem; }
  td.sentence-form { color:rgba(253,230,138,.58); }
  td.missing-value { color:rgba(248,113,113,.42); }
  td.deck { max-width:15rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  td.actions,th.actions { position:sticky; right:0; width:3rem; background:#14131a; }
  .source-badge { display:inline-flex; border:1px solid rgba(255,255,255,.09); border-radius:999px; padding:.18rem .38rem; font-size:.55rem; font-weight:800; text-transform:uppercase; }
  .source-badge.anki { border-color:rgba(56,189,248,.2); background:rgba(56,189,248,.08); color:rgb(186 230 253 / .72); }
  .source-badge.manual { border-color:rgba(251,191,36,.2); background:rgba(251,191,36,.08); color:rgb(254 243 199 / .72); }
  .stage { display:inline-flex; border-radius:999px; padding:.2rem .4rem; font-size:.55rem; font-weight:800; text-transform:uppercase; }
  .stage.new { background:rgba(100,116,139,.12); color:rgb(203 213 225 / .62); }
  .stage.learning { background:rgba(251,191,36,.1); color:rgb(253 230 138 / .7); }
  .stage.young { background:rgba(56,189,248,.1); color:rgb(186 230 253 / .72); }
  .stage.mature { background:rgba(52,211,153,.1); color:rgb(167 243 208 / .72); }
  .media-dots { display:flex; gap:.2rem; }
  .media-dots i { display:grid; height:1.1rem; width:1.1rem; place-items:center; border-radius:999px; background:rgba(255,255,255,.04); color:rgba(255,255,255,.16); font-size:.5rem; font-style:normal; }
  .media-dots i.available { background:rgba(52,211,153,.09); color:rgb(167 243 208 / .65); }
  .flags { display:flex; flex-wrap:wrap; gap:.22rem; }
  .flags span { border-radius:999px; background:rgba(255,255,255,.05); padding:.18rem .35rem; font-size:.53rem; }
  .flags .danger { background:rgba(248,113,113,.08); color:rgb(254 202 202 / .7); }
  .inspector { position:relative; width:22rem; flex:none; overflow-y:auto; border-left:1px solid rgba(255,255,255,.08); background:radial-gradient(circle at 90% -10%,rgba(251,191,36,.12),transparent 40%),#15131a; padding:1.4rem; animation:inspector-in 180ms ease-out both; }
  .close { position:absolute; right:.8rem; top:.75rem; display:grid; height:2rem; width:2rem; place-items:center; border-radius:999px; color:rgba(255,255,255,.35); font-size:1.1rem; }
  .close:hover { background:rgba(255,255,255,.06); color:white; }
  .eyebrow { padding-right:2rem; color:rgba(251,191,36,.48); font-size:.58rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; }
  .inspector h2 { margin-top:1rem; color:white; font-size:2.25rem; font-weight:900; line-height:1.08; }
  .form { margin-top:.35rem; color:rgba(253,230,138,.58); }
  .reading { margin-top:.2rem; color:rgba(255,255,255,.28); font-size:.7rem; }
  .meaning-stack { display:grid; gap:.5rem; margin-top:1.35rem; }
  .meaning-stack div,.inspector-block { border:1px solid rgba(255,255,255,.07); border-radius:.85rem; background:rgba(0,0,0,.16); padding:.75rem; }
  .meaning-stack span,.inspector-block>span,.facts span { color:rgba(255,255,255,.25); font-size:.53rem; font-weight:800; letter-spacing:.1em; text-transform:uppercase; }
  .meaning-stack p,.inspector-block p { margin-top:.35rem; color:rgba(255,255,255,.68); font-size:.72rem; line-height:1.45; }
  .inspector-block { margin-top:.65rem; }
  .inspector-block .example { color:rgba(255,255,255,.78); font-size:.82rem; line-height:1.7; }
  .inspector-block small { display:block; margin-top:.35rem; color:rgba(255,255,255,.3); font-size:.62rem; line-height:1.5; }
  .facts { display:grid; grid-template-columns:1fr 1fr; gap:.45rem; margin-top:.65rem; }
  .facts div { border:1px solid rgba(255,255,255,.06); border-radius:.7rem; padding:.65rem; }
  .facts strong { display:block; margin-top:.25rem; color:rgba(255,255,255,.65); font-size:.66rem; }
  .inspector-actions { display:flex; gap:.5rem; margin-top:1rem; }
  .inspector-actions button { flex:1; border:1px solid rgba(255,255,255,.1); border-radius:.7rem; padding:.65rem; color:rgba(255,255,255,.6); font-size:.65rem; font-weight:700; }
  .inspector-actions button.accent { border-color:rgba(251,191,36,.24); background:rgba(251,191,36,.08); color:rgb(254 243 199 / .8); }
  @keyframes inspector-in { from { opacity:0; transform:translateX(12px); } to { opacity:1; transform:translateX(0); } }
  @media (max-width: 900px) {
    .browser-shell { min-height:30rem; }
    .inspector { position:fixed; z-index:65; inset:5rem 1rem 1rem auto; width:min(23rem,calc(100vw - 2rem)); border:1px solid rgba(255,255,255,.1); border-radius:1rem; box-shadow:0 30px 80px rgba(0,0,0,.65); }
  }
  :global(html[data-motion='reduced']) .inspector { animation:none; }
</style>
