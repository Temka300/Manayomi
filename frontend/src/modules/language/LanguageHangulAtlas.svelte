<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import {
    languageApi,
    type LanguageList,
    type LanguageWord,
  } from '../../lib/languageApi';
  import LanguageWordMenu from './LanguageWordMenu.svelte';

  export let items: LanguageWord[] = [];
  export let lists: LanguageList[] = [];

  const dispatch = createEventDispatcher<{
    details: LanguageWord;
    edit: LanguageWord;
    favorite: LanguageWord;
    addtolist: { word: LanguageWord; listId: string };
  }>();

  const INITIALS = ['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ'];

  function initialFor(word: string): string {
    const code = word.trim().charCodeAt(0);
    if (code >= 0xac00 && code <= 0xd7a3) {
      return INITIALS[Math.floor((code - 0xac00) / 588)] ?? '•';
    }
    return '•';
  }

  function sense(word: LanguageWord, lang: string): string {
    return word.senses.find((value) => value.lang === lang)?.text ?? '';
  }

  function sectionId(initial: string): string {
    return `hangul-${initial.charCodeAt(0).toString(16)}`;
  }

  $: grouped = Array.from(
    items.reduce((map, word) => {
      const initial = initialFor(word.headword);
      if (!map.has(initial)) map.set(initial, []);
      map.get(initial)?.push(word);
      return map;
    }, new Map<string, LanguageWord[]>()),
  ).sort(([left], [right]) => {
    const leftIndex = INITIALS.indexOf(left);
    const rightIndex = INITIALS.indexOf(right);
    return (leftIndex < 0 ? 99 : leftIndex) - (rightIndex < 0 ? 99 : rightIndex);
  });
</script>

<section class="atlas" aria-label="Hangul Atlas">
  <div class="atlas-intro">
    <div>
      <p>Experimental library view</p>
      <h2>Hangul Atlas</h2>
      <span>Words gather by their first Korean sound. Mastery changes the glow; hover or focus opens the meaning.</span>
    </div>
    <nav aria-label="Hangul initials">
      {#each grouped as [initial, words]}
        <a href={`#${sectionId(initial)}`} title={`${words.length} words beginning with ${initial}`}>{initial}</a>
      {/each}
    </nav>
  </div>

  <div class="atlas-sections">
    {#each grouped as [initial, words], sectionIndex}
      <section class="initial-cluster" id={sectionId(initial)}>
        <div class="initial-marker" aria-hidden="true">
          <strong>{initial}</strong>
          <span>{words.length}</span>
        </div>
        <div class="constellation">
          {#each words as word, wordIndex (word.word_id)}
            <article
              class="atlas-card group {word.stage} {(wordIndex + sectionIndex) % 7 === 0 ? 'featured' : ''} {word.media_by_role.image ? 'has-image' : ''}"
              style={`--delay:${Math.min(wordIndex, 12) * 25}ms;--orbit:${(wordIndex * 37 + sectionIndex * 13) % 100}%`}
            >
              {#if word.media_by_role.image}
                <img src={languageApi.mediaUrl(word.word_id, 'image')} alt="" loading="lazy" />
              {/if}
              <div class="grain"></div>
              <div class="card-top">
                <span class="index">{word.sort_index ?? '◇'}</span>
                <LanguageWordMenu compact {word} {lists} on:edit={(event) => dispatch('edit', event.detail)} on:details={(event) => dispatch('details', event.detail)} on:favorite={(event) => dispatch('favorite', event.detail)} on:addtolist={(event) => dispatch('addtolist', event.detail)} />
              </div>
              <button type="button" class="word-face" on:click={() => dispatch('details', word)}>
                <span class="word">{word.headword}</span>
                {#if word.sentence_form !== word.headword}<span class="form">{word.sentence_form}</span>{/if}
                <span class="meaning">
                  <b>{sense(word, 'en') || 'No English meaning'}</b>
                  <i>{sense(word, 'mn')}</i>
                </span>
              </button>
              <div class="mastery">
                <span style={`width:${Math.max(6, Math.min(100, word.weakest_interval / 21 * 100))}%`}></span>
              </div>
              <div class="orbit-dot" aria-hidden="true"></div>
            </article>
          {/each}
        </div>
      </section>
    {/each}
  </div>
</section>

<style>
  .atlas { position:relative; overflow:hidden; border:1px solid rgba(255,255,255,.08); border-radius:1.4rem; background:radial-gradient(circle at 20% 0%,rgba(56,189,248,.07),transparent 28rem),radial-gradient(circle at 90% 15%,rgba(251,191,36,.08),transparent 34rem),#0f0e14; }
  .atlas::before { position:absolute; inset:0; content:""; pointer-events:none; background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px); background-size:38px 38px; mask-image:linear-gradient(to bottom,black,transparent 48rem); }
  .atlas-intro { position:sticky; top:0; z-index:8; display:flex; align-items:end; justify-content:space-between; gap:1.5rem; border-bottom:1px solid rgba(255,255,255,.07); background:rgba(15,14,20,.9); padding:1.25rem 1.5rem; backdrop-filter:blur(18px); }
  .atlas-intro p { color:rgba(56,189,248,.55); font-size:.57rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }
  .atlas-intro h2 { margin-top:.2rem; font-size:1.65rem; font-weight:900; }
  .atlas-intro>div>span { display:block; margin-top:.3rem; color:rgba(255,255,255,.32); font-size:.68rem; }
  .atlas-intro nav { display:flex; max-width:55%; flex-wrap:wrap; justify-content:end; gap:.22rem; }
  .atlas-intro a { display:grid; height:1.7rem; min-width:1.7rem; place-items:center; border:1px solid rgba(255,255,255,.07); border-radius:.5rem; color:rgba(255,255,255,.35); font-size:.66rem; }
  .atlas-intro a:hover,.atlas-intro a:focus-visible { border-color:rgba(251,191,36,.24); background:rgba(251,191,36,.07); color:rgb(254 243 199 / .8); }
  .atlas-sections { position:relative; padding:1.5rem; }
  .initial-cluster { position:relative; display:grid; grid-template-columns:5rem minmax(0,1fr); gap:1rem; min-height:10rem; padding:1rem 0 2.2rem; scroll-margin-top:5rem; }
  .initial-cluster+.initial-cluster { border-top:1px solid rgba(255,255,255,.055); }
  .initial-marker { position:sticky; top:6rem; align-self:start; color:rgba(255,255,255,.08); text-align:center; }
  .initial-marker strong { display:block; font-size:4.4rem; font-weight:950; line-height:.9; }
  .initial-marker span { display:inline-flex; margin-top:.5rem; border:1px solid rgba(255,255,255,.08); border-radius:999px; padding:.15rem .4rem; color:rgba(255,255,255,.24); font-size:.55rem; }
  .constellation { display:grid; grid-template-columns:repeat(auto-fill,minmax(10.5rem,1fr)); grid-auto-flow:dense; gap:.65rem; }
  .atlas-card { --stage:148 163 184; position:relative; min-height:10rem; overflow:visible; border:1px solid rgb(var(--stage) / .12); border-radius:1rem 1rem 1rem .25rem; background:linear-gradient(145deg,rgb(var(--stage) / .08),rgba(20,19,26,.94) 52%); animation:atlas-in 300ms var(--delay) both; transition:transform 180ms,border-color 180ms,box-shadow 180ms; }
  .atlas-card.learning { --stage:251 191 36; }
  .atlas-card.young { --stage:56 189 248; }
  .atlas-card.mature { --stage:52 211 153; }
  .atlas-card.featured { grid-column:span 2; min-height:12rem; }
  .atlas-card:hover,.atlas-card:focus-within { z-index:4; transform:translateY(-4px) rotate(-.35deg); border-color:rgb(var(--stage) / .34); box-shadow:0 20px 50px rgba(0,0,0,.32),0 0 35px rgb(var(--stage) / .07); }
  .atlas-card img { position:absolute; inset:0; height:100%; width:100%; border-radius:inherit; object-fit:cover; opacity:.1; filter:saturate(.7) contrast(1.1); }
  .grain { position:absolute; inset:0; overflow:hidden; border-radius:inherit; pointer-events:none; background:radial-gradient(circle at var(--orbit) 18%,rgb(var(--stage) / .16),transparent 38%),repeating-linear-gradient(115deg,transparent 0 9px,rgba(255,255,255,.012) 10px); }
  .card-top { position:relative; z-index:3; display:flex; align-items:center; justify-content:space-between; padding:.55rem .6rem 0 .75rem; }
  .index { color:rgb(var(--stage) / .52); font-size:.57rem; font-variant-numeric:tabular-nums; }
  .word-face { position:relative; z-index:2; display:flex; min-height:7.4rem; width:100%; flex-direction:column; align-items:start; padding:.7rem 1rem 1rem; text-align:left; }
  .word { margin-top:auto; color:white; font-size:1.65rem; font-weight:950; letter-spacing:-.04em; line-height:1.05; }
  .featured .word { font-size:2.25rem; }
  .form { margin-top:.25rem; color:rgb(var(--stage) / .55); font-size:.68rem; }
  .meaning { display:grid; max-height:0; margin-top:0; overflow:hidden; opacity:0; transform:translateY(4px); transition:max-height 200ms,margin 200ms,opacity 160ms,transform 180ms; }
  .atlas-card:hover .meaning,.atlas-card:focus-within .meaning { max-height:5rem; margin-top:.75rem; opacity:1; transform:translateY(0); }
  .meaning b { color:rgba(255,255,255,.7); font-size:.68rem; font-weight:650; line-height:1.35; }
  .meaning i { margin-top:.2rem; color:rgba(186,230,253,.42); font-size:.6rem; font-style:normal; line-height:1.35; }
  .mastery { position:absolute; z-index:3; right:.7rem; bottom:.55rem; left:.7rem; height:2px; overflow:hidden; border-radius:999px; background:rgba(255,255,255,.06); }
  .mastery span { display:block; height:100%; border-radius:inherit; background:rgb(var(--stage) / .78); box-shadow:0 0 10px rgb(var(--stage) / .4); transition:width 250ms; }
  .orbit-dot { position:absolute; right:-3px; top:36%; height:6px; width:6px; border-radius:999px; background:rgb(var(--stage) / .7); box-shadow:0 0 12px rgb(var(--stage) / .55); }
  @keyframes atlas-in { from { opacity:0; transform:translateY(10px) scale(.98); } to { opacity:1; transform:translateY(0) scale(1); } }
  @media (max-width: 700px) {
    .atlas-intro { position:relative; align-items:start; flex-direction:column; }
    .atlas-intro nav { max-width:none; justify-content:start; }
    .atlas-sections { padding:.8rem; }
    .initial-cluster { grid-template-columns:2.4rem minmax(0,1fr); gap:.5rem; }
    .initial-marker strong { font-size:2.3rem; }
    .constellation { grid-template-columns:1fr; }
    .atlas-card.featured { grid-column:span 1; }
  }
  :global(html[data-motion='reduced']) .atlas-card { animation:none; transition:none; }
  :global(html[data-motion='reduced']) .meaning { transition:none; }
</style>
