// Tier 2 + Tier 3 surfaces (Loop) — the steady-state loop that is the product's actual value:
// check-in → telemetry, drift/accountability/nudges/recommitment, replan choice,
// multi-week navigation, and plan version diff.

// ───────────────── T2 · Check-in loop (Complete / Missed → consequence) ─────────────────
function CheckInDemo() {
  const { ProductTopbar } = window;
  const [state, setState] = React.useState('pending'); // pending | done | missed
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr'}}>
      <ProductTopbar nav="Today" />
      <div style={{display:'grid', placeItems:'center', minHeight:0, padding:24}}>
        <div style={{width:560}}>
          <span className="eyebrow">Check-in · the block's time has passed</span>
          <h2 className="t-h2" style={{marginTop:8}}>How did this go?</h2>
          <p className="muted" style={{fontSize:13.5, marginTop:3}}>Telemetry from every completed block is what powers calibration — the planner learns your real pace.</p>

          <div className="card" style={{padding:'16px 18px', marginTop:16}}>
            <div className="row" style={{justifyContent:'space-between', alignItems:'flex-start'}}>
              <div>
                <div className="mono" style={{fontSize:12, color:'var(--muted)'}}>Yesterday · 4:30–5:15 PM</div>
                <div className="t-h4" style={{marginTop:3}}>System design · URL shortener</div>
                <div className="muted" style={{fontSize:12.5, marginTop:2}}>45m planned · weak-spot block</div>
              </div>
              {state === 'pending' && (
                <div className="row" style={{gap:8}}>
                  <button className="btn btn-soft sm" onClick={()=>setState('missed')}>✕ Missed</button>
                  <button className="btn btn-ink sm" onClick={()=>setState('done')}>✓ Completed</button>
                </div>
              )}
              {state !== 'pending' && (
                <span className="pill" style={state==='done'
                  ? {background:'var(--sage-soft)', color:'var(--sage-deep)'}
                  : {background:'var(--gold-soft)', color:'#9a6a1e'}}>
                  <span className="pdot" style={{background: state==='done'?'var(--sage)':'var(--gold)'}}></span>{state==='done'?'completed':'missed'}
                </span>
              )}
            </div>

            {state === 'done' && (
              <div style={{marginTop:14}}>
                <div className="row" style={{gap:8, alignItems:'center'}}>
                  <span className="label">How long, really?</span>
                  <span className="chip on sm">52 min</span>
                  <span className="muted" style={{fontSize:12}}>vs 45 planned</span>
                </div>
                <div className="card soft" style={{padding:'12px 14px', marginTop:12, borderColor:'var(--sage-soft)', background:'var(--sage-soft)'}}>
                  <div style={{fontSize:13, color:'var(--ink-soft)', lineHeight:1.5}}>
                    <b>Logged → calibration updated.</b> You consistently run ~15% long on system-design. Loop padded your next two design blocks to 55m so the plan stays honest.
                  </div>
                </div>
              </div>
            )}
            {state === 'missed' && (
              <div className="card soft" style={{padding:'12px 14px', marginTop:14, borderColor:'var(--gold-soft)', background:'var(--gold-soft)'}}>
                <div style={{fontSize:13, color:'var(--ink-2)', lineHeight:1.5}}>
                  <b>Marked missed → drift +1.</b> That's your 2nd miss this week on weak-spot work. The agent will check in tomorrow with a recovery option — no judgment, just a path back.
                </div>
                <button className="btn btn-primary sm" style={{marginTop:11}}>See recovery options →</button>
              </div>
            )}
          </div>
          {state !== 'pending' && <button className="btn btn-quiet sm" style={{marginTop:12}} onClick={()=>setState('pending')}>↺ reset demo</button>}
        </div>
      </div>
    </div>
  );
}

// ───────────────── T2 · Drift / accountability / nudges / recommitment ─────────────────
const DRIFT = {
  on_track:        {label:'On track',        c:'var(--sage)',  bg:'var(--sage-soft)',  ink:'var(--sage-deep)', msg:"You're on pace — 9 of 11 blocks done this week. Keep going."},
  slightly_behind: {label:'Slightly behind', c:'var(--gold)',  bg:'var(--gold-soft)',  ink:'#9a6a1e',         msg:"You're ~1 block behind. A 30-min catch-up tonight closes the gap."},
  behind:          {label:'Behind',          c:'var(--gold)',  bg:'var(--gold-soft)',  ink:'#9a6a1e',         msg:"3 missed blocks this week. Graphs is slipping — the milestone date is now at risk."},
  far_behind:      {label:'Far behind',      c:'var(--clay)',  bg:'var(--clay-tint)',  ink:'var(--clay-deep)', msg:"5+ missed blocks. The current plan won't hit May 4 without a change."},
  disengaged:      {label:'Disengaged',      c:'#a33',         bg:'#f8e9e4',           ink:'#a33',            msg:"No activity in 6 days. Want to recommit, pause, or rescope? Either is fine."},
};
const DRIFT_ORDER = ['on_track','slightly_behind','behind','far_behind','disengaged'];

function DriftSurfaces() {
  const { ProductTopbar } = window;
  const [s, setS] = React.useState('behind');
  const d = DRIFT[s];
  const needsNudge = s === 'slightly_behind' || s === 'behind' || s === 'far_behind';
  const needsRecommit = s === 'far_behind' || s === 'disengaged';
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr'}}>
      <ProductTopbar nav="Today" />
      <div style={{padding:'22px 40px', overflow:'auto', minHeight:0}}>
        {/* state switcher (demo control) */}
        <div className="row" style={{gap:7, flexWrap:'wrap', marginBottom:18}}>
          <span className="muted" style={{fontSize:12, alignSelf:'center', marginRight:4}}>accountability status:</span>
          {DRIFT_ORDER.map((k) => (
            <button key={k} onClick={()=>setS(k)} className={'chip sm ' + (k===s?'clay-solid':'')} style={{cursor:'pointer'}}>{DRIFT[k].label}</button>
          ))}
        </div>

        <div style={{display:'grid', gridTemplateColumns:'1.3fr 1fr', gap:20, alignItems:'start'}}>
          <div className="col" style={{gap:16}}>
            {/* status banner */}
            <div className="card" style={{padding:'18px 20px', borderColor:d.c, background:d.bg}}>
              <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
                <span className="pill" style={{background:'#fff', color:d.ink}}><span className="pdot" style={{background:d.c}}></span>{d.label}</span>
                <span className="mono" style={{fontSize:11.5, color:d.ink}}>status · computed nightly</span>
              </div>
              <div style={{fontSize:15, color:'var(--ink-2)', marginTop:12, lineHeight:1.5, fontWeight:500}}>{d.msg}</div>
            </div>

            {/* nudge */}
            {needsNudge && (
              <div className="card" style={{padding:'16px 18px'}}>
                <div className="row" style={{gap:9, alignItems:'center'}}><span className="agent-mark" style={{flex:'none'}}>✦</span><span className="label">A nudge from your agent</span></div>
                <div style={{fontSize:14, color:'var(--ink-soft)', marginTop:10, lineHeight:1.55}}>
                  {s==='slightly_behind' && "“One graph problem tonight and you're square. Want me to drop a 30-min block at 8pm?”"}
                  {s==='behind' && "“Graphs is the thread pulling the whole week. Protect tomorrow's 10am block and we hold the milestone.”"}
                  {s==='far_behind' && "“The math no longer works as-is. Let's pick a recovery mode together — it'll take two minutes.”"}
                </div>
                <div className="row" style={{gap:8, marginTop:12}}>
                  <button className="btn btn-primary sm">{s==='far_behind'?'Choose recovery →':'Add the block'}</button>
                  <button className="btn btn-soft sm">Not now</button>
                </div>
              </div>
            )}

            {/* recommitment */}
            {needsRecommit && (
              <div className="err">
                <span className="err-code">RECOMMITMENT_PROMPTED</span>
                <div style={{fontSize:14.5, fontWeight:600, marginTop:9}}>Still want this goal?</div>
                <div style={{fontSize:13, color:'var(--ink-soft)', marginTop:5, lineHeight:1.5}}>No pressure — be honest. We can rescope to something you'll actually do, pause the plan, or recommit and replan.</div>
                <div className="row" style={{gap:8, marginTop:12, flexWrap:'wrap'}}>
                  <button className="btn btn-primary sm">Recommit &amp; replan</button>
                  <button className="btn btn-soft sm">Rescope smaller</button>
                  <button className="btn btn-quiet sm">Pause 1 week</button>
                </div>
              </div>
            )}
          </div>

          {/* weekly check-in card */}
          <div className="card soft" style={{padding:'18px 20px'}}>
            <div className="label" style={{marginBottom:4}}>Weekly check-in</div>
            <div className="muted" style={{fontSize:12, marginBottom:14}}>Sundays · 6pm</div>
            <div className="col" style={{gap:11}}>
              <div className="row" style={{justifyContent:'space-between'}}><span style={{fontSize:13.5, color:'var(--ink-soft)'}}>Blocks completed</span><span style={{fontWeight:600}}>8 / 11</span></div>
              <div className="slider"><div className="fill" style={{width:'73%'}}></div></div>
              <div className="row" style={{justifyContent:'space-between', marginTop:4}}><span style={{fontSize:13.5, color:'var(--ink-soft)'}}>Focus hours</span><span style={{fontWeight:600}}>11.5 / 15</span></div>
              <div className="row" style={{justifyContent:'space-between'}}><span style={{fontSize:13.5, color:'var(--ink-soft)'}}>Weakest topic</span><span className="chip clay sm">graphs</span></div>
              <div className="divider" style={{margin:'4px 0'}}></div>
              <div style={{fontSize:13, color:'var(--ink-soft)', lineHeight:1.5}}>“A solid week despite two misses. Next week front-loads graphs — fair?”</div>
              <button className="btn btn-primary sm" style={{marginTop:4}}>Confirm next week →</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ───────────────── T2 · Replan / recovery-mode choice ─────────────────
const RECOVERY = [
  {k:'Compress', sub:'keep the date', desc:'Fit the remaining work into the time left — denser weeks, longer sessions.', meta:'May 4 held · ~19 hrs/wk', tag:'higher intensity'},
  {k:'Extend', sub:'move the date', desc:'Push the deadline out so weekly load stays sustainable.', meta:'May 4 → May 25 · ~14 hrs/wk', tag:'recommended for you', on:true},
  {k:'Drop scope', sub:'cut the long tail', desc:'Keep core DSA + behavioral; defer system-design depth.', meta:'May 4 held · ~13 hrs/wk', tag:'narrower goal'},
];
function ReplanChoice() {
  const { ProductTopbar } = window;
  const [pick, setPick] = React.useState('Extend');
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr'}}>
      <ProductTopbar nav="Plan" />
      <div style={{padding:'30px 48px', overflow:'auto', minHeight:0}}>
        <div className="err" style={{maxWidth:760}}>
          <span className="err-code">REPLAN_REQUIRED · drift = behind</span>
          <div style={{fontSize:15, fontWeight:600, marginTop:9}}>Your plan needs to change</div>
          <div style={{fontSize:13.5, color:'var(--ink-soft)', marginTop:5, lineHeight:1.5}}>At your current pace you'll miss May 4 by ~9 days. Pick how to recover — your profile prefers <b>extending</b> over grinding.</div>
        </div>

        <div className="label" style={{margin:'22px 0 12px'}}>Recovery mode</div>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:14}}>
          {RECOVERY.map((r) => {
            const on = pick === r.k;
            return (
              <button key={r.k} onClick={()=>setPick(r.k)} style={{
                textAlign:'left', cursor:'pointer', borderRadius:16, padding:'18px 20px',
                border: on ? '1.5px solid var(--clay)' : '1px solid var(--line-2)',
                background: on ? 'var(--clay-tint)' : 'var(--card)',
                boxShadow: on ? '0 0 0 1px var(--clay)' : 'none', font:'inherit',
              }}>
                <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
                  <span className="t-h4" style={{color: on?'var(--clay-deep)':'var(--ink)'}}>{r.k}</span>
                  {r.on && <span className="chip clay-solid sm" style={{padding:'2px 8px'}}>for you</span>}
                </div>
                <div className="muted" style={{fontSize:12, marginTop:1}}>{r.sub}</div>
                <div style={{fontSize:13, color:'var(--ink-soft)', marginTop:10, lineHeight:1.5, minHeight:54}}>{r.desc}</div>
                <div className="mono" style={{fontSize:11.5, color: on?'var(--clay-deep)':'var(--muted)', marginTop:6}}>{r.meta}</div>
                <span className="chip sm" style={{marginTop:10}}>{r.tag}</span>
              </button>
            );
          })}
        </div>
        <div className="row" style={{gap:10, marginTop:20}}>
          <button className="btn btn-primary lg">Replan with “{pick}” →</button>
          <button className="btn btn-soft">Let the agent decide</button>
          <span className="muted" style={{fontSize:12.5, alignSelf:'center'}}>generates a new plan version you'll review &amp; approve</span>
        </div>
      </div>
    </div>
  );
}

// ───────────────── T2 · Multi-week navigation (horizon) ─────────────────
const HORIZON = Array.from({length:12}).map((_, i) => {
  const w = i + 1;
  let state = 'future';
  if (w <= 3) state = 'done';
  else if (w === 4) state = 'current';
  else if (w <= 6) state = 'approved';
  else state = 'proposed';
  return { w, state };
});
const H_MILES = {3:'Résumé + 12 apps', 4:'DSA core', 7:'System design', 10:'Mock loops', 12:'Onsites'};

function MultiWeekNav() {
  const { ProductTopbar } = window;
  const [sel, setSel] = React.useState(4);
  const color = (st) => st==='done' ? 'var(--sage)' : st==='current' ? 'var(--clay)' : st==='approved' ? 'var(--ink-soft)' : 'var(--line-3)';
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr'}}>
      <ProductTopbar nav="Plan" />
      <div style={{padding:'26px 40px', overflow:'auto', minHeight:0}}>
        <div className="row" style={{justifyContent:'space-between', alignItems:'flex-end'}}>
          <div>
            <span className="eyebrow">Full horizon</span>
            <h2 className="t-h2" style={{marginTop:7}}>Your 12-week plan</h2>
            <p className="muted" style={{fontSize:13.5, marginTop:3}}>Review and approve a long plan week-by-week — or approve a stretch at once. Only the current week writes to your calendar now; future weeks stay proposed until their time.</p>
          </div>
          <div className="row" style={{gap:9}}>
            <button className="btn btn-soft sm">Approve weeks 5–6</button>
            <button className="btn btn-primary sm">Approve all proposed</button>
          </div>
        </div>

        {/* horizon strip */}
        <div style={{display:'grid', gridTemplateColumns:'repeat(12, 1fr)', gap:8, marginTop:22}}>
          {HORIZON.map((h) => {
            const on = sel === h.w;
            return (
              <button key={h.w} onClick={()=>setSel(h.w)} style={{
                cursor:'pointer', textAlign:'left', borderRadius:11, padding:'11px 11px 13px', font:'inherit', minHeight:96,
                border: on ? '1.5px solid var(--clay)' : '1px solid var(--line-2)',
                background: h.state==='current' ? 'var(--clay-tint)' : on ? 'var(--paper-2)' : 'var(--card)',
              }}>
                <div className="mono" style={{fontSize:11, color:'var(--muted)'}}>W{h.w}</div>
                <div style={{width:'100%', height:4, borderRadius:2, background:color(h.state), marginTop:8}}></div>
                <div style={{fontSize:10.5, color:'var(--muted)', marginTop:8, textTransform:'capitalize'}}>{h.state==='current'?'this week':h.state}</div>
                {H_MILES[h.w] && <div style={{fontSize:10.5, fontWeight:600, color:'var(--ink-soft)', marginTop:6, lineHeight:1.25}}>◆ {H_MILES[h.w]}</div>}
              </button>
            );
          })}
        </div>
        <div className="legend" style={{marginTop:16}}>
          <span className="lg"><span className="sw" style={{background:'var(--sage)'}}></span>done</span>
          <span className="lg"><span className="sw" style={{background:'var(--clay)'}}></span>this week (on calendar)</span>
          <span className="lg"><span className="sw" style={{background:'var(--ink-soft)'}}></span>approved</span>
          <span className="lg"><span className="sw" style={{background:'var(--line-3)'}}></span>proposed</span>
        </div>

        {/* selected week detail */}
        <div className="card" style={{padding:'16px 18px', marginTop:18}}>
          <div className="row" style={{justifyContent:'space-between'}}>
            <div className="t-h4">Week {sel} · {HORIZON[sel-1].state==='current'?'in progress':HORIZON[sel-1].state}</div>
            {HORIZON[sel-1].state==='proposed' && <button className="btn btn-primary sm">Approve this week</button>}
          </div>
          <div className="muted" style={{fontSize:13, marginTop:6}}>{H_MILES[sel] ? `Milestone week — ${H_MILES[sel]}.` : 'Focus blocks for graphs, DP and system design, scheduled around your fixed events.'}</div>
        </div>
      </div>
    </div>
  );
}

// ───────────────── T3 · Plan version diff ─────────────────
function PlanDiff() {
  const { ProductTopbar } = window;
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr'}}>
      <ProductTopbar nav="Plan" />
      <div style={{padding:'28px 48px', overflow:'auto', minHeight:0, maxWidth:860}}>
        <div className="row" style={{gap:10, alignItems:'center'}}>
          <span className="eyebrow">What changed</span>
          <span className="chip sm">v3</span><span className="muted">→</span><span className="chip clay-solid sm">v4</span>
          <span className="muted" style={{fontSize:12.5}}>· replan · recovery = Extend</span>
        </div>
        <h2 className="t-h2" style={{marginTop:10}}>Review the change before it replaces v3</h2>
        <p className="muted" style={{fontSize:13.5, marginTop:3}}>Every plan is versioned. Here's the diff — approve to make v4 active, or keep v3.</p>

        <div className="card" style={{padding:'8px 12px', marginTop:18}}>
          {[
            {k:'~', c:'var(--gold)', t:'Deadline moved', d:'May 4 → May 25 (+21 days)'},
            {k:'+', c:'var(--sage)', t:'Added 4 graph blocks', d:'weeks 5–6 · your weakest topic'},
            {k:'~', c:'var(--gold)', t:'Weekly load eased', d:'18 hrs/wk → 14 hrs/wk'},
            {k:'−', c:'var(--clay)', t:'Removed 2 late-night blocks', d:'violated quiet hours after 10:30 PM'},
            {k:'=', c:'var(--muted-2)', t:'Behavioral & mock track', d:'unchanged'},
          ].map((r, i, arr) => (
            <div key={r.t} className="row" style={{gap:13, padding:'11px 8px', borderBottom: i<arr.length-1?'1px solid var(--line)':'none', alignItems:'flex-start'}}>
              <span style={{width:22, height:22, borderRadius:6, flex:'none', display:'grid', placeItems:'center', fontFamily:'var(--mono)', fontWeight:700, fontSize:13, color:'#fff', background:r.c}}>{r.k}</span>
              <div style={{flex:1}}>
                <div style={{fontSize:14, fontWeight:600}}>{r.t}</div>
                <div className="muted" style={{fontSize:12.5, marginTop:1}}>{r.d}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="row" style={{gap:10, marginTop:18}}>
          <button className="btn btn-quiet">Keep v3</button>
          <div className="spacer"></div>
          <button className="btn btn-soft">Compare side-by-side</button>
          <button className="btn btn-primary">Approve v4 →</button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { CheckInDemo, DriftSurfaces, ReplanChoice, MultiWeekNav, PlanDiff });
