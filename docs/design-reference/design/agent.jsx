// Agent — hi-fi (Tandem 同舟)
// Sidebar dock (always docked, never a floating pill). Approvals on top,
// thread in the middle, composer + trust strip at the bottom. Plus a
// capability map separating LLM-proposes from deterministic-acts.

function WeekSummary() {
  const { WK, DayColumn } = window;
  return (
    <div className="col" style={{minHeight:0, gap:14, height:'100%'}}>
      <div className="row" style={{justifyContent:'space-between'}}>
        <div className="row" style={{gap:10}}>
          <span className="icon-btn">←</span>
          <h2 className="t-h2">Jul 6 — 12</h2>
          <span className="icon-btn">→</span>
        </div>
        <span className="muted" style={{fontSize:12.5}}>5 proposed · 5 accepted · 5 done</span>
      </div>
      <div className="cal-grid" style={{flex:1}}>
        {WK.map((d, i) => <DayColumn key={i} d={d} />)}
      </div>
    </div>
  );
}

function AgentDock() {
  return (
    <aside className="dock">
      {/* header */}
      <div className="dock-head">
        <div className="row" style={{justifyContent:'space-between', alignItems:'flex-start'}}>
          <div className="row" style={{gap:11}}>
            <span className="agent-mark">✦</span>
            <div>
              <div className="t-h3">Agent</div>
              <div className="muted" style={{fontSize:12}}>bounded · proposes only · you approve</div>
            </div>
          </div>
          <span className="icon-btn" title="collapse">→|</span>
        </div>
      </div>

      {/* approvals */}
      <div className="dock-section">
        <div className="row" style={{justifyContent:'space-between', marginBottom:10}}>
          <span className="label">Pending · 2 proposals</span>
          <span className="eyebrow" style={{cursor:'default'}}>Review all →</span>
        </div>
        <div className="col" style={{gap:8}}>
          {[
            {t:'Personal essay · draft 1', m:'Wed 10:00 · 1h focus'},
            {t:'Reflect — what stuck?', m:'Wed 8:00 · 15m'},
          ].map((a) => (
            <div key={a.t} className="approval">
              <div className="row" style={{justifyContent:'space-between', alignItems:'center', gap:10}}>
                <div style={{flex:1}}>
                  <div className="at">{a.t}</div>
                  <div className="am">{a.m}</div>
                </div>
                <div className="row" style={{gap:6}}>
                  <button className="btn btn-soft sm" style={{padding:'5px 9px'}}>✕</button>
                  <button className="btn btn-primary sm" style={{padding:'5px 11px'}}>✓ Accept</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* thread */}
      <div className="dock-section grow">
        <div className="label" style={{marginBottom:11}}>Thread · personal essay</div>
        <div className="chat" style={{flex:1, justifyContent:'flex-end', overflow:'hidden'}}>
          <div className="bubble agent">Good morning. Your personal essay draft is the only thing standing between you and Friday's milestone.</div>
          <div className="bubble agent">I drafted a 1h focus block at 10:00 — it's before your café shift, when you tend to write best. <b>Review above ↑</b></div>
          <div className="bubble me">Can you pull the details from my hospital volunteer activity for the opening?</div>
          <div className="bubble tool">⌁ read_file(activities-list.pdf) · 1.8k tokens</div>
          <div className="bubble agent">Found the key details. They'll surface in your essay draft when you start the block — nothing is pasted until you do.</div>
        </div>
      </div>

      {/* composer + trust */}
      <div className="dock-section" style={{borderBottom:'none'}}>
        <div className="composer">
          <span className="ph">Ask, plan, or reschedule…</span>
          <span className="send">↑</span>
        </div>
        <div className="row" style={{flexWrap:'wrap', gap:6, marginTop:11}}>
          <span className="slash">/recover</span>
          <span className="slash">/why</span>
          <span className="slash">/regen week</span>
          <span className="slash">/explain</span>
        </div>
        <div className="divider" style={{margin:'13px 0 11px'}}></div>
        <div className="guard">
          <span className="lk">🔒</span>
          <span>The agent never writes to your calendar without an explicit ✓. File reads are logged, and every accept has a 60-second undo.</span>
        </div>
      </div>
    </aside>
  );
}

function AgentScreen() {
  const { ProductTopbar, MilestoneBar } = window;
  return (
    <div className="app" style={{gridTemplateRows:'auto auto 1fr'}}>
      <ProductTopbar nav="Week" />
      <MilestoneBar />
      <div style={{display:'grid', gridTemplateColumns:'1fr 392px', minHeight:0, overflow:'hidden'}}>
        <div style={{padding:'18px 26px', minHeight:0, overflow:'hidden'}}>
          <WeekSummary />
        </div>
        <AgentDock />
      </div>
    </div>
  );
}

// ───────────────── Capability map ─────────────────
function CapabilityMap() {
  const { ProductTopbar } = window;
  const llm = [
    {icon:'¶', title:'Parse resume / files', desc:'Reads CV, transcripts, lit notes. Extracts roles, weak spots, target schools — you review every field.'},
    {icon:'⚑', title:'Generate syllabus', desc:'Turns goal + skill profile into a milestone tree. Always lands in the approval gate first.'},
    {icon:'↻', title:'Regenerate week', desc:'Takes your changes and drafts new proposed blocks. You review before anything is accepted.'},
    {icon:'⚐', title:'Recovery plan', desc:'When you fall behind. The policy engine decides IF; the model only writes HOW.'},
    {icon:'?', title:'Explain "why this"', desc:'Natural-language reasoning for any block — prereqs, milestone, energy fit.'},
    {icon:'∑', title:'Weekly reflection', desc:'Summarizes what got done, what slipped, and what to focus on next.'},
  ];
  const det = [
    {icon:'▷', title:'Accept & schedule', desc:'Writes accepted blocks to Google Calendar. Idempotent, retry-safe, no model in the path.'},
    {icon:'✓', title:'Mark done', desc:'Logs completion + actual duration. Feeds calibration and updates milestone progress.'},
    {icon:'⊘', title:'Drift detection', desc:'Rule-based: missed % + reschedule count → behind / on-track / ahead.'},
    {icon:'⤓', title:'Calendar sync', desc:'Pulls busy windows, respects quiet hours, never silently mutates an event.'},
    {icon:'⚐', title:'Permission gate', desc:'Sponsor visibility and parent reports — explicit, per-field consent.'},
    {icon:'$', title:'Cost & retry caps', desc:'Bounded budget, concurrency lock, no runaway loops.'},
  ];
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr', overflow:'hidden'}}>
      <ProductTopbar nav="Plan" />
      <div style={{padding:'34px 56px', overflow:'auto', minHeight:0}}>
        <span className="eyebrow">Capability map · v0.1</span>
        <h1 className="t-display" style={{marginTop:12, maxWidth:880}}>The model proposes. Deterministic infrastructure disposes.</h1>
        <p className="muted" style={{fontSize:15.5, marginTop:10, maxWidth:760}}>
          Every agent capability falls into one of two columns. Clay = AI-generated, and must be approved before any
          side effect. White = deterministic, acting directly with no model in the loop.
        </p>

        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:28, marginTop:30}}>
          {[
            {head:'AI · proposes', sub:'must be approved', kind:'llm', items:llm, tag:'preview →'},
            {head:'Deterministic · acts', sub:'no model in the loop', kind:'det', items:det, tag:'direct'},
          ].map((col) => (
            <div key={col.head}>
              <div className="row" style={{gap:13, marginBottom:16, alignItems:'center'}}>
                <span className="ci" style={{
                  width:42, height:42, borderRadius:12, flex:'none',
                  display:'grid', placeItems:'center', fontFamily:'var(--mono)', fontSize:14, fontWeight:700,
                  background: col.kind === 'llm' ? 'var(--clay)' : 'var(--paper-2)',
                  color: col.kind === 'llm' ? '#fff' : 'var(--ink)',
                  border: col.kind === 'llm' ? 'none' : '1px solid var(--line-2)'
                }}>{col.kind === 'llm' ? 'AI' : 'D'}</span>
                <div style={{lineHeight:1.15}}>
                  <h2 className="t-h2" style={{whiteSpace:'nowrap'}}>{col.head}</h2>
                  <div className="muted" style={{fontSize:13, marginTop:2}}>{col.sub}</div>
                </div>
              </div>
              <div className="col" style={{gap:11}}>
                {col.items.map((c) => (
                  <div key={c.title} className={'cap ' + col.kind}>
                    <span className="ci">{c.icon}</span>
                    <div style={{flex:1}}>
                      <div className="ct">{c.title}</div>
                      <div className="cd">{c.desc}</div>
                    </div>
                    <span className="tag">{col.tag}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AgentScreen, CapabilityMap });
