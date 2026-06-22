// Single agent wireframe — sidebar dock (always docked right, no floating pill).
// Layout matches calendar's structure: topbar + milestone rail + main content + dock.
// The dock is part of the chrome, not a popup. Threads, capabilities, and
// approvals all live inside it.

function AgentTopbar() {
  return (
    <div className="topbar">
      <div className="logo"><span className="mark">S</span> scheduler</div>
      <div className="nav">
        <a>today</a>
        <a className="on">week</a>
        <a>milestones</a>
        <a>plan</a>
      </div>
      <div className="spacer" />
      <div className="sk-row">
        <div className="sk-box" style={{padding:'4px 10px', boxShadow:'none', borderWidth:1.5}}>
          <span className="sk-sub" style={{textTransform:'none', letterSpacing:0}}>
            <span style={{display:'inline-block', width:8, height:8, borderRadius:'50%', background:'#3b9d6e', marginRight:6, verticalAlign:'middle'}}></span>
            google calendar synced · 2m ago
          </span>
        </div>
        <span className="sk-btn tiny">⌘K</span>
        <div className="who"><div className="avatar">M</div></div>
      </div>
    </div>
  );
}

// Compact week-grid summary used as the calendar surface behind the dock
function WeekSummary() {
  const { WEEK, DayCol } = window;
  return (
    <div className="sk-col" style={{minHeight:0, overflow:'hidden', height:'100%'}}>
      <div className="sk-row" style={{justifyContent:'space-between'}}>
        <div className="sk-row">
          <span className="sk-btn tiny ghost">←</span>
          <h2 className="sk-h2">Apr 27 — May 3</h2>
          <span className="sk-btn tiny ghost">→</span>
        </div>
        <div className="sk-sub">5 proposed · 9 accepted · 4 done</div>
      </div>
      <div style={{display:'grid', gridTemplateColumns:'repeat(7, 1fr)', gap:8, marginTop:14, flex:1, minHeight:0}}>
        {WEEK.map((d, i) => <DayCol key={i} {...d} />)}
      </div>
    </div>
  );
}

function AgentDock() {
  return (
    <aside style={{
      borderLeft:'1.5px solid var(--ink)',
      background:'rgba(255,216,77,0.10)',
      display:'flex', flexDirection:'column', minHeight:0, height:'100%'
    }}>
      {/* Dock header */}
      <div style={{padding:'14px 18px', borderBottom:'1.5px dashed var(--line-soft)', display:'flex', justifyContent:'space-between', alignItems:'center'}}>
        <div>
          <div className="sk-row" style={{gap:8, alignItems:'center'}}>
            <div style={{width:26, height:26, border:'2px solid var(--ink)', borderRadius:6, background:'var(--accent)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:'var(--hand-title)', fontSize:16}}>✦</div>
            <h3 className="sk-h3">agent</h3>
          </div>
          <div className="sk-sub lc" style={{color:'var(--pencil)', marginTop:2}}>
            bounded · proposes only · you approve
          </div>
        </div>
        <span className="sk-btn tiny ghost" title="collapse">→|</span>
      </div>

      {/* Pending approvals — the trust surface */}
      <div style={{padding:'12px 18px', borderBottom:'1.5px dashed var(--line-soft)'}}>
        <div className="sk-row" style={{justifyContent:'space-between', alignItems:'center'}}>
          <div className="sk-sub">pending · 2 proposals</div>
          <span className="sk-sub" style={{color:'var(--accent)'}}>review →</span>
        </div>
        <div className="sk-col" style={{gap:6, marginTop:8}}>
          <div className="sk-box dashed" style={{padding:'8px 10px', background:'rgba(255,216,77,0.55)'}}>
            <div className="sk-row" style={{justifyContent:'space-between'}}>
              <div style={{flex:1}}>
                <div style={{fontSize:13, fontWeight:700}}>SOP v2 · intro</div>
                <div className="sk-sub lc" style={{color:'var(--pencil)', marginTop:2}}>wed 10:30 · 1h focus</div>
              </div>
              <div className="sk-row" style={{gap:5}}>
                <span className="sk-btn tiny ghost">✕</span>
                <span className="sk-btn tiny coral">✓</span>
              </div>
            </div>
          </div>
          <div className="sk-box dashed" style={{padding:'8px 10px', background:'rgba(255,216,77,0.55)'}}>
            <div className="sk-row" style={{justifyContent:'space-between'}}>
              <div style={{flex:1}}>
                <div style={{fontSize:13, fontWeight:700}}>reflect — what stuck?</div>
                <div className="sk-sub lc" style={{color:'var(--pencil)', marginTop:2}}>wed 5:00 · 15m</div>
              </div>
              <div className="sk-row" style={{gap:5}}>
                <span className="sk-btn tiny ghost">✕</span>
                <span className="sk-btn tiny coral">✓</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Conversation */}
      <div style={{flex:1, padding:'14px 18px', overflow:'hidden', display:'flex', flexDirection:'column'}}>
        <div className="sk-sub" style={{marginBottom:10}}>thread · graphs milestone</div>
        <div className="chat" style={{flex:1, justifyContent:'flex-end', overflow:'hidden'}}>
          <div className="bubble agent" style={{fontSize:14}}>good morning. SOP v2 intro is the only blocker for friday's milestone.</div>
          <div className="bubble agent" style={{fontSize:14}}>i drafted a 1h block at 10:30 — fits between your advisor mtg and lunch. <b>review above ↑</b></div>
          <div className="bubble me" style={{fontSize:14}}>can you also pull 3 quotes from my lit review for the intro?</div>
          <div className="bubble tool" style={{fontSize:11}}>+ tool: read_file(lit-review.md) · 4.2k tokens</div>
          <div className="bubble agent" style={{fontSize:14}}>got 3 candidates. they'll show in the SOP draft when you start the block — i won't paste anything until you do.</div>
        </div>
      </div>

      {/* Composer */}
      <div style={{padding:'12px 18px', borderTop:'1.5px dashed var(--line-soft)'}}>
        <div className="chat-input">
          <span className="ph" style={{fontSize:14}}>ask, plan, reschedule…</span>
          <span className="sk-btn tiny primary">↑</span>
        </div>
        <div className="sk-row" style={{flexWrap:'wrap', gap:5, marginTop:10}}>
          <span className="sk-chip" style={{fontSize:12}}>/recover</span>
          <span className="sk-chip" style={{fontSize:12}}>/why</span>
          <span className="sk-chip" style={{fontSize:12}}>/regen week</span>
          <span className="sk-chip" style={{fontSize:12}}>/explain</span>
        </div>

        {/* Trust strip — bounded, always visible */}
        <div style={{marginTop:12, paddingTop:10, borderTop:'1px dashed var(--line-soft)'}}>
          <div className="sk-sub" style={{textTransform:'none', letterSpacing:0, color:'var(--pencil-soft)', lineHeight:1.5}}>
            agent never writes to your calendar without an explicit ✓.<br/>
            file reads are logged · 60s undo on every accept.
          </div>
        </div>
      </div>
    </aside>
  );
}

function AgentMain() {
  return (
    <div className="app" style={{gridTemplateRows:'auto auto 1fr'}}>
      <AgentTopbar />
      <window.MilestoneRail />

      <div style={{display:'grid', gridTemplateColumns:'1fr 380px', minHeight:0, overflow:'hidden'}}>
        <div style={{padding:'18px 24px', minHeight:0, overflow:'hidden'}}>
          <WeekSummary />
        </div>
        <AgentDock />
      </div>
    </div>
  );
}

// ────────── Capability map (kept) ──────────
function CapabilityMap() {
  const llm = [
    {icon:'¶', title:'parse resume / files', desc:'reads CV, transcripts, lit notes. extracts roles, weak spots, target schools. user reviews extracted fields.'},
    {icon:'⚑', title:'generate syllabus', desc:'turns goal + skill profile into a milestone tree. always lands in the approval gate.'},
    {icon:'↻', title:'regenerate week', desc:'asks for changes, drafts new proposed blocks. user reviews before accept.'},
    {icon:'⚐', title:'recovery plan', desc:'when behind. policy engine decides IF; LLM writes HOW.'},
    {icon:'?', title:'explain "why this"', desc:'natural-language explanation of any block — prereqs, milestone, energy fit.'},
    {icon:'∑', title:'weekly reflection', desc:'summary of what got done, what slipped, what to focus on next.'},
  ];
  const det = [
    {icon:'▷', title:'accept & schedule', desc:'writes accepted blocks to gcal. idempotent. retry-safe. no LLM in this path.'},
    {icon:'✓', title:'mark done', desc:'logs completion + actual duration. feeds calibration. updates milestone progress.'},
    {icon:'⊘', title:'drift detection', desc:'rule-based: missed % + reschedule count → behind/on-track/ahead.'},
    {icon:'⤓', title:'gcal sync', desc:'pulls busy windows. respects quiet hours. never silently mutates.'},
    {icon:'⚐', title:'permission gate', desc:'sponsor visibility, parent reports — explicit per-field consent.'},
    {icon:'$', title:'cost & retry caps', desc:'bounded budget. concurrency lock. no runaway loops.'},
  ];
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr', overflow:'auto'}}>
      <AgentTopbar />
      <div style={{padding:'40px 80px'}}>
        <div className="sk-sub">capability map · v0.1</div>
        <h1 className="sk-h1">LLMs propose. Deterministic infrastructure disposes.</h1>
        <div className="sk-sub lc" style={{color:'var(--pencil)', marginTop:8, maxWidth:780}}>
          every agent capability falls into one of two columns. coral = LLM-generated (must be approved before any side effect). white = deterministic (acts directly, no LLM in the loop).
        </div>

        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:24, marginTop:32}}>
          <div>
            <div className="sk-row" style={{gap:10, marginBottom:14}}>
              <div style={{width:36, height:36, border:'2px solid var(--ink)', borderRadius:8, background:'var(--accent)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:'var(--hand-title)', fontSize:22}}>L</div>
              <h2 className="sk-h2">LLM · proposes</h2>
            </div>
            <div className="sk-col" style={{gap:10}}>
              {llm.map((c,i) => (
                <div key={i} className="sk-box thick" style={{padding:'14px 16px', display:'flex', gap:14, alignItems:'flex-start'}}>
                  <div style={{width:38, height:38, border:'2px solid var(--ink)', borderRadius:8, background:'var(--accent)', color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:'var(--hand-title)', fontSize:22, flexShrink:0}}>{c.icon}</div>
                  <div style={{flex:1}}>
                    <div className="sk-h4">{c.title}</div>
                    <div className="sk-sub lc" style={{color:'var(--pencil)', marginTop:4}}>{c.desc}</div>
                  </div>
                  <span className="sk-sub" style={{color:'var(--accent)', flexShrink:0}}>preview →</span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="sk-row" style={{gap:10, marginBottom:14}}>
              <div style={{width:36, height:36, border:'2px solid var(--ink)', borderRadius:8, background:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:'var(--hand-title)', fontSize:22}}>D</div>
              <h2 className="sk-h2">deterministic · acts</h2>
            </div>
            <div className="sk-col" style={{gap:10}}>
              {det.map((c,i) => (
                <div key={i} className="sk-box thick" style={{padding:'14px 16px', display:'flex', gap:14, alignItems:'flex-start'}}>
                  <div style={{width:38, height:38, border:'2px solid var(--ink)', borderRadius:8, background:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:'var(--hand-title)', fontSize:22, flexShrink:0}}>{c.icon}</div>
                  <div style={{flex:1}}>
                    <div className="sk-h4">{c.title}</div>
                    <div className="sk-sub lc" style={{color:'var(--pencil)', marginTop:4}}>{c.desc}</div>
                  </div>
                  <span className="sk-sub" style={{flexShrink:0}}>direct</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AgentMain, CapabilityMap });
