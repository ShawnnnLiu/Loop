// Tier 1 surfaces (Loop) — generation, approval gate, failure/recovery, OAuth.
// Plus the REUSABLE AIProposal shell that generalizes the résumé extract→review→approve
// pattern to every "AI proposes" moment (plan, replan, nudge).

// ───────────────── Reusable: AI proposed this → review / approve / reject ─────────────────
// Use everywhere the model emits something a human must confirm before it has effect.
function AIProposal({ title, sub, eyebrow = 'AI proposed this', children,
                      onReject, onRedo, approveLabel = 'Approve →', rejectLabel = 'Reject',
                      redoLabel = 'Regenerate', tone = 'clay' }) {
  return (
    <div className="card raise" style={{padding:'20px 22px'}}>
      <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
        <span className="eyebrow">{eyebrow}</span>
        <span className="chip clay sm">AI · please review</span>
      </div>
      <h2 className="t-h2" style={{marginTop:9}}>{title}</h2>
      {sub && <p className="muted" style={{fontSize:13.5, marginTop:3}}>{sub}</p>}
      <div style={{marginTop:15}}>{children}</div>
      <div className="row" style={{justifyContent:'space-between', marginTop:18}}>
        <button className="btn btn-quiet">{rejectLabel}</button>
        <div className="row" style={{gap:9}}>
          <button className="btn btn-soft">{redoLabel}</button>
          <button className="btn btn-primary">{approveLabel}</button>
        </div>
      </div>
    </div>
  );
}

// ───────────────── T1 · Generation in-progress (animated pipeline) ─────────────────
const PIPELINE = [
  {t:'Strategist · Opus', m:'setting strategy & milestones'},
  {t:'Planner · Haiku', m:'drafting weekly blocks'},
  {t:'Validation', m:'checking fit & constraints'},
  {t:'Scheduler', m:'placing around your calendar'},
];

function GenerationProgress() {
  const { ProductTopbar } = window;
  const [active, setActive] = React.useState(0);
  const [elapsed, setElapsed] = React.useState(0);
  const [repair, setRepair] = React.useState(false);
  React.useEffect(() => {
    const t = setInterval(() => {
      setActive((a) => {
        const next = a + 1;
        if (next === 2) setRepair(Math.random() > 0.5);
        if (next > PIPELINE.length) { setElapsed(0); return 0; }
        return next;
      });
    }, 1200);
    const e = setInterval(() => setElapsed((s) => s + 0.1), 100);
    return () => { clearInterval(t); clearInterval(e); };
  }, []);
  const done = active >= PIPELINE.length;

  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr'}}>
      <ProductTopbar nav="Plan" />
      <div style={{display:'grid', placeItems:'center', minHeight:0, padding:24}}>
        <div className="card raise" style={{padding:'30px 34px', width:560}}>
          <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
            <span className="eyebrow">Building your plan</span>
            {done
              ? <span className="pill" style={{background:'var(--sage-soft)', color:'var(--sage-deep)'}}><span className="pdot" style={{background:'var(--sage)'}}></span>ready</span>
              : <span className="chip clay sm"><span className="spin" style={{width:11,height:11,marginRight:5}}></span>working</span>}
          </div>
          <h2 className="t-h2" style={{marginTop:10}}>{done ? 'Your 12-week plan is ready' : 'Drafting your interview-prep plan'}</h2>
          <p className="muted" style={{fontSize:13.5, marginTop:3}}>
            A multi-stage pipeline — usually 10–30s. Nothing is written to your calendar yet.
          </p>

          <div style={{marginTop:18}}>
            {PIPELINE.map((s, i) => {
              const st = i < active || done ? 'done' : i === active ? 'active' : 'pending';
              return (
                <div key={s.t} className={'pl-step ' + st}>
                  <span className="pl-ico">{st === 'done' ? '✓' : st === 'active' ? (i+1) : (i+1)}</span>
                  <div>
                    <div className="pl-t">{s.t}</div>
                    {st === 'active' && i === 2 && repair && <div style={{fontSize:11.5, color:'var(--clay-deep)', marginTop:1}}>repair loop 1 of 2 — adjusting to fit constraints</div>}
                  </div>
                  <span className="pl-m">{st === 'done' ? 'ok' : st === 'active' ? <span className="spin"></span> : '—'}</span>
                </div>
              );
            })}
          </div>

          <div className="divider" style={{margin:'16px 0 13px'}}></div>
          <div className="row" style={{justifyContent:'space-between'}}>
            <span className="mono" style={{fontSize:12, color:'var(--muted)'}}>elapsed {elapsed.toFixed(1)}s · ≤2 repair loops / stage</span>
            <button className="btn btn-quiet sm">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ───────────────── T1 · Approval gate + post-write verification + rollback ─────────────────
const WRITE_BLOCKS = [
  {t:'Mon 4:00p', n:'Mock interview · peer'},
  {t:'Wed 10:30a', n:'Graphs · Dijkstra drill'},
  {t:'Wed 8:00p', n:'Reflect — what stuck?'},
  {t:'Thu 10:00a', n:'System design · URL shortener'},
  {t:'Thu 3:00p', n:'DP · review wrong set'},
  {t:'Fri 4:00p', n:'Behavioral · 3 STAR stories'},
];

function ApprovalGate() {
  const { ProductTopbar } = window;
  // phase: idle → gate → writing → verified | failed
  const [phase, setPhase] = React.useState('idle');
  const [simFail, setSimFail] = React.useState(false);

  const open = () => setPhase('gate');
  const confirm = () => {
    setPhase('writing');
    setTimeout(() => setPhase(simFail ? 'failed' : 'verified'), 1400);
  };

  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr', position:'relative'}}>
      <ProductTopbar nav="Week" />
      <div style={{padding:'24px 40px', display:'grid', gridTemplateColumns:'1fr 360px', gap:26, minHeight:0}}>
        {/* left: the blocks about to be written */}
        <div className="col" style={{gap:13}}>
          <div>
            <span className="eyebrow">Ready to schedule</span>
            <h2 className="t-h2" style={{marginTop:7}}>6 approved blocks for this week</h2>
            <p className="muted" style={{fontSize:13.5, marginTop:3}}>You've arranged these. The next step is the only place Loop writes to your calendar.</p>
          </div>
          <div className="card" style={{padding:'8px 10px'}}>
            {WRITE_BLOCKS.map((b, i) => (
              <div key={i} className="row" style={{justifyContent:'space-between', padding:'9px 8px', borderBottom: i<WRITE_BLOCKS.length-1?'1px solid var(--line)':'none'}}>
                <div className="row" style={{gap:10}}>
                  <span className="mono" style={{fontSize:12, color:'var(--muted)', width:74}}>{b.t}</span>
                  <span style={{fontSize:14, fontWeight:500}}>{b.n}</span>
                </div>
                <span className="chip sm" style={{background:'var(--clay-tint)', color:'var(--clay-deep)', border:'1px solid var(--clay-soft)'}}>approved</span>
              </div>
            ))}
          </div>
        </div>

        {/* right: gate trigger + verification result */}
        <div className="col" style={{gap:14}}>
          <div className="card soft" style={{padding:'16px 18px'}}>
            <div className="label" style={{marginBottom:8}}>The approval gate</div>
            <p style={{fontSize:13, color:'var(--ink-soft)', lineHeight:1.5}}>
              No silent writes. Loop never touches your calendar without an explicit approval + a payload-hash recheck, and verifies every event after writing.
            </p>
            <button className="btn btn-primary lg" style={{width:'100%', marginTop:14}} onClick={open}>Review &amp; write to calendar →</button>
            <label className="row" style={{gap:8, marginTop:12, cursor:'pointer', fontSize:12.5, color:'var(--muted)'}}>
              <input type="checkbox" checked={simFail} onChange={(e)=>setSimFail(e.target.checked)} />
              simulate a verification failure
            </label>
          </div>

          {phase === 'verified' && (
            <div className="card" style={{padding:'16px 18px', borderColor:'var(--sage)', background:'var(--sage-soft)'}}>
              <div className="row" style={{gap:8, alignItems:'center'}}>
                <span className="pill" style={{background:'#fff', color:'var(--sage-deep)'}}><span className="pdot" style={{background:'var(--sage)'}}></span>6 / 6 verified</span>
              </div>
              <div style={{fontSize:13.5, color:'var(--ink-soft)', marginTop:9, lineHeight:1.5}}>Written to <b>Personal · maya@gmail.com</b> and confirmed present on Google Calendar.</div>
              <div className="row" style={{gap:9, marginTop:12}}>
                <button className="btn btn-soft sm">Roll back all</button>
                <span className="mono" style={{fontSize:11.5, color:'var(--muted)', alignSelf:'center'}}>undo available 60s</span>
              </div>
            </div>
          )}
          {phase === 'failed' && (
            <div className="err hard">
              <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
                <span className="err-code" style={{color:'#a33', borderColor:'#d99'}}>CALENDAR_VERIFICATION_FAILED</span>
                <span className="pill" style={{background:'#fff', color:'#a33'}}>4 / 6 verified</span>
              </div>
              <div style={{fontSize:13.5, color:'var(--ink-2)', marginTop:10, lineHeight:1.5}}>
                4 events confirmed; <b>2 could not be verified</b> after writing (Google returned no event id). Loop rolled the 2 back to keep your calendar and plan in sync.
              </div>
              <div className="row" style={{gap:9, marginTop:12}}>
                <button className="btn btn-primary sm">Retry the 2 failed</button>
                <button className="btn btn-soft sm">Roll back all 4</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* the gate modal */}
      {(phase === 'gate' || phase === 'writing') && (
        <div className="scrim">
          <div className="modal">
            <div style={{padding:'20px 24px', borderBottom:'1px solid var(--line)'}}>
              <span className="eyebrow">Confirm calendar write</span>
              <h3 className="t-h3" style={{marginTop:7}}>Write 6 blocks to Google Calendar?</h3>
            </div>
            <div style={{padding:'18px 24px'}}>
              <div className="cfg-row"><div className="cl">Target calendar</div><span className="chip sm">Personal · maya@gmail.com</span></div>
              <div className="cfg-row"><div className="cl">Events to create</div><span style={{fontWeight:600}}>6</span></div>
              <div className="cfg-row"><div className="cl">Payload hash</div><span className="mono" style={{fontSize:12, color:'var(--muted)'}}>sha256:9f3a…c1d</span></div>
              <div className="cfg-row" style={{borderBottom:'none'}}><div className="cl">After write</div><span style={{fontSize:13, color:'var(--ink-soft)'}}>each event re-read & verified</span></div>
              <div className="guard" style={{marginTop:6}}>
                <span className="lk">🔒</span>
                <span>This is the only action that writes to your calendar. The hash is rechecked at write time; if your plan changed, the write is refused.</span>
              </div>
            </div>
            <div className="row" style={{justifyContent:'flex-end', gap:10, padding:'14px 24px', borderTop:'1px solid var(--line)', background:'var(--paper-2)'}}>
              <button className="btn btn-quiet" onClick={()=>setPhase('idle')}>Cancel</button>
              <button className="btn btn-primary" onClick={confirm} disabled={phase==='writing'}>
                {phase === 'writing' ? <><span className="spin" style={{width:12,height:12,marginRight:7}}></span>Writing…</> : 'Approve write →'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ───────────────── T1 · Failure / recovery pattern (typed reason_codes) ─────────────────
function ReasonCodeCard({ code, hard, what, why, actions }) {
  return (
    <div className={'err' + (hard ? ' hard' : '')}>
      <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
        <span className="err-code" style={hard ? {color:'#a33', borderColor:'#d99'} : null}>{code}</span>
        <span className="mono" style={{fontSize:10.5, color:'var(--muted)'}}>{hard ? 'hard stop' : 'recoverable'}</span>
      </div>
      <div style={{fontSize:14.5, fontWeight:600, color:'var(--ink)', marginTop:11}}>{what}</div>
      <div style={{fontSize:13, color:'var(--ink-soft)', marginTop:5, lineHeight:1.5}}>{why}</div>
      <div className="row" style={{gap:8, marginTop:13, flexWrap:'wrap'}}>
        {actions.map((a, i) => (
          <button key={a} className={'btn sm ' + (i===0 ? 'btn-primary' : 'btn-soft')}>{a}</button>
        ))}
      </div>
    </div>
  );
}

function FailureGallery() {
  const { ProductTopbar } = window;
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr'}}>
      <ProductTopbar nav="Plan" />
      <div style={{padding:'26px 48px', overflow:'auto', minHeight:0}}>
        <span className="eyebrow">One pattern, every failure</span>
        <h1 className="t-h1" style={{marginTop:10, maxWidth:820}}>When the backend can't proceed, it says exactly why — and how to recover</h1>
        <p className="muted" style={{fontSize:14.5, marginTop:8, maxWidth:760}}>
          Every step emits a typed <span className="mono" style={{fontSize:13}}>reason_code</span>. The surface is always the same three parts: <b>what went wrong</b> (the specific numbers), <b>why</b>, and the <b>recovery affordances</b>. No dead ends.
        </p>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginTop:22}}>
          <ReasonCodeCard code="INSUFFICIENT_WEEKLY_CAPACITY"
            what="Your plan needs ~18 hrs/week, but you budgeted 12."
            why="Covering graphs, DP and system design before May 4 requires more time than your weekly budget allows."
            actions={['Raise weekly hours', 'Extend timeline', 'Drop scope']} />
          <ReasonCodeCard code="USER_FIT_VIOLATED"
            what="3 blocks landed inside your quiet hours (after 10:30 PM)."
            why="The scheduler couldn't fit everything within your deep-work windows and hard constraints."
            actions={['Relax a constraint', 'Allow weekends', 'Regenerate']} />
          <ReasonCodeCard code="REPAIR_LIMIT_EXCEEDED"
            what="Couldn't satisfy all constraints after 2 repair loops."
            why="Your constraints are tight enough that the planner exhausted its repair budget without a valid plan."
            actions={['Review constraints', 'Regenerate', 'Talk to agent']} />
          <ReasonCodeCard code="CALENDAR_WRITE_FAILED" hard
            what="Google Calendar rejected the write (rate-limited)."
            why="A transient API error. Nothing was written; your plan is unchanged and safe to retry."
            actions={['Retry', 'Dismiss']} />
        </div>
        <div className="row" style={{gap:10, marginTop:18, flexWrap:'wrap'}}>
          <span className="muted" style={{fontSize:12.5}}>Also handled:</span>
          <span className="err-code">LLM_REFUSAL</span>
          <span className="err-code">COVERAGE_INCOMPLETE</span>
          <span className="err-code" style={{color:'#a33', borderColor:'#d99'}}>CALENDAR_VERIFICATION_FAILED</span>
        </div>
      </div>
    </div>
  );
}

// ───────────────── T1 · Connect / Google OAuth (onboarding step 7) ─────────────────
function OnbConnect() {
  const { Topbar, Stepper, Engine, StepRail } = window;
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr auto'}}>
      <Topbar />
      <div style={{display:'grid', gridTemplateColumns:'232px 1fr', minHeight:0}}>
        <div style={{padding:'30px 22px', borderRight:'1px solid var(--line)', display:'flex', flexDirection:'column', gap:18}}>
          <Stepper step={7} total={7} />
          <StepRail active={7} />
        </div>
        <div style={{padding:'40px 56px', display:'grid', gridTemplateColumns:'1.1fr 1fr', gap:32, alignContent:'start'}}>
          <div>
            <Engine kind="det" />
            <h1 className="t-h1" style={{marginTop:13}}>Connect Google Calendar</h1>
            <p className="muted" style={{fontSize:15, marginTop:4, maxWidth:440}}>
              The last step. Loop reads your busy times to schedule around them, and writes approved blocks back — nothing else.
            </p>
            <div className="card" style={{padding:'20px 22px', marginTop:20}}>
              <div className="col" style={{gap:11}}>
                <div className="cfg-row"><div><div className="cl">Read busy / free</div><div className="cs">so it never double-books you</div></div><span className="chip sage sm">needed</span></div>
                <div className="cfg-row"><div><div className="cl">Create events on one calendar</div><div className="cs">you pick which — approved blocks only</div></div><span className="chip sage sm">needed</span></div>
                <div className="cfg-row" style={{borderBottom:'none'}}><div><div className="cl">Read your email / contacts</div><div className="cs">never requested</div></div><span className="chip sm">no access</span></div>
              </div>
              <button className="btn btn-ink lg" style={{width:'100%', marginTop:16, gap:9}}>
                <span style={{fontFamily:'var(--mono)', fontWeight:700}}>G</span> Connect Google Calendar
              </button>
              <div className="guard" style={{marginTop:12}}><span className="lk">🔒</span><span>Revocable any time. Loop only writes to the one calendar you choose.</span></div>
            </div>
          </div>

          {/* edge states */}
          <div className="col" style={{gap:13}}>
            <div className="label">If something goes wrong</div>
            <div className="err">
              <span className="err-code">OAUTH_NOT_ALLOWLISTED</span>
              <div style={{fontSize:13.5, fontWeight:600, marginTop:9}}>This tester isn't on the allowlist yet</div>
              <div style={{fontSize:12.5, color:'var(--ink-soft)', marginTop:4, lineHeight:1.5}}>Loop is in limited testing. Your Google account needs to be added before it can connect.</div>
              <div className="row" style={{gap:8, marginTop:11}}><button className="btn btn-primary sm">Request access</button><button className="btn btn-soft sm">Use a different account</button></div>
            </div>
            <div className="err">
              <span className="err-code">CALENDAR_CONNECTION_LOST</span>
              <div style={{fontSize:13.5, fontWeight:600, marginTop:9}}>Connection to Google expired</div>
              <div style={{fontSize:12.5, color:'var(--ink-soft)', marginTop:4, lineHeight:1.5}}>Your token was revoked or timed out. Sync is paused until you reconnect — no blocks are written meanwhile.</div>
              <div className="row" style={{gap:8, marginTop:11}}><button className="btn btn-primary sm">Reconnect</button></div>
            </div>
          </div>
        </div>
      </div>
      <div className="footer-bar" style={{padding:'13px 56px', borderTop:'1px solid var(--line)'}}>
        <span>Step 7 of 7 · the entry point that gates everything</span>
        <div className="row" style={{gap:10}}><button className="btn btn-quiet sm">← Back</button><button className="btn btn-primary sm">Finish setup →</button></div>
      </div>
    </div>
  );
}

Object.assign(window, { AIProposal, GenerationProgress, ApprovalGate, ReasonCodeCard, FailureGallery, OnbConnect });
