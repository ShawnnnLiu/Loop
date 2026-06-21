// Onboarding — hi-fi (Tandem 同舟)
// Deterministic wizard with two LLM-powered parse steps (transcript, activities).
// Artboards: A · deadline (det), B · transcript parse (LLM),
// C · current courses + grades (det), D · activities parse (LLM).

function Topbar({ exit }) {
  return (
    <div className="tb">
      <div className="brand">
        <span className="glyph">同</span>
        <span className="word">Tandem <span className="zh">同舟</span></span>
      </div>
      <div className="spacer" />
      <span className="label" style={{letterSpacing:'0.1em'}}>First-run setup</span>
      <div className="row" style={{gap:6, marginLeft:6}}>
        <button className="btn btn-quiet sm">Save &amp; exit</button>
      </div>
    </div>
  );
}

function Stepper({ step, total }) {
  return (
    <div className="row" style={{gap:14}}>
      <span className="mono" style={{fontSize:12, fontWeight:600, color:'var(--muted)'}}>
        Step {step} / {total}
      </span>
      <div className="seg-track">
        {Array.from({length: total}).map((_, i) => (
          <div key={i} className={'seg' + (i < step ? ' fill' : '')} />
        ))}
      </div>
    </div>
  );
}

function Engine({ kind }) {
  const llm = kind === 'llm';
  return (
    <div className={'engine ' + (llm ? 'llm' : 'det')}>
      <span className="pip">{llm ? 'AI' : 'D'}</span>
      {llm ? 'AI-assisted step' : 'Deterministic step'}
    </div>
  );
}

const STEPS = ['Goal','Hours','Deadline','Transcript','Courses','Activities','Connect'];

function StepRail({ active }) {
  return (
    <div className="step-rail">
      {STEPS.map((s, i) => {
        const n = i + 1;
        const cls = n < active ? 'done' : n === active ? 'on' : '';
        return (
          <div key={s} className={'it ' + cls}>
            <span className="node">{n < active ? '✓' : n}</span>
            <span className="stp">{s}</span>
          </div>
        );
      })}
    </div>
  );
}

// ───────────────── A · deadline (deterministic) ─────────────────
function OnbDeadline() {
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr auto'}}>
      <Topbar />
      <div style={{display:'grid', gridTemplateColumns:'232px 1fr', minHeight:0}}>
        {/* rail */}
        <div style={{padding:'30px 22px', borderRight:'1px solid var(--line)', display:'flex', flexDirection:'column', gap:18}}>
          <Stepper step={3} total={7} />
          <StepRail active={3} />
          <div className="spacer" />
          <div className="card soft" style={{padding:'13px 15px'}}>
            <div className="label" style={{marginBottom:6}}>Why a plain form?</div>
            <div style={{fontSize:12.5, color:'var(--ink-soft)', lineHeight:1.5}}>
              Simple questions don't need a model. Forms are faster, predictable, and never hallucinate an answer.
            </div>
            <div className="divider" style={{margin:'12px 0'}}></div>
            <div className="label" style={{marginBottom:8}}>AI is used only to</div>
            <div className="col" style={{gap:6, alignItems:'flex-start'}}>
              <span className="chip clay sm">read your transcript</span>
              <span className="chip clay sm">read your activities</span>
              <span className="chip clay sm">draft your plan</span>
            </div>
          </div>
        </div>

        {/* main */}
        <div style={{padding:'44px 64px', display:'grid', gridTemplateColumns:'1fr', gap:8, alignContent:'start', maxWidth:760}}>
          <Engine kind="det" />
          <h1 className="t-display" style={{marginTop:14}}>When's your deadline?</h1>
          <p className="muted" style={{fontSize:16, maxWidth:520, marginTop:2}}>
            We back-plan every milestone from this date. Pick a runway — you can change it any time in settings.
          </p>

          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginTop:20, maxWidth:560}}>
            {[
              {k:'Soon', v:'In 4 weeks', sub:'tight, intensive'},
              {k:'Balanced', v:'In 12 weeks', sub:'recommended', on:true},
              {k:'Long runway', v:'In 6 months', sub:'steady pace'},
              {k:'Custom', v:'Pick a date →', sub:'choose exactly', dashed:true},
            ].map((o) => (
              <div key={o.k} className="card" style={{
                padding:'16px 18px', cursor:'default',
                borderColor: o.on ? 'var(--clay)' : undefined,
                borderStyle: o.dashed ? 'dashed' : 'solid',
                background: o.on ? 'var(--clay-tint)' : (o.dashed ? 'transparent' : '#fff'),
                boxShadow: o.on ? '0 0 0 1.5px var(--clay)' : undefined
              }}>
                <div className="row" style={{justifyContent:'space-between'}}>
                  <span className="label">{o.k}</span>
                  {o.on && <span className="chip clay-solid sm" style={{padding:'2px 8px'}}>selected</span>}
                </div>
                <div className="t-h3" style={{marginTop:8, color: o.on ? 'var(--clay-deep)' : 'var(--ink)'}}>{o.v}</div>
                <div className="muted" style={{fontSize:12.5, marginTop:2}}>{o.sub}</div>
              </div>
            ))}
          </div>

          <div className="card" style={{padding:'16px 20px', marginTop:14, maxWidth:560, display:'flex', justifyContent:'space-between', alignItems:'center', background:'var(--paper-2)', boxShadow:'none'}}>
            <div>
              <div className="label">Target date</div>
              <div className="t-h2" style={{marginTop:3}}>February 14, 2026</div>
            </div>
            <div style={{textAlign:'right'}}>
              <div className="label">Runway</div>
              <div className="t-h2" style={{marginTop:3, color:'var(--clay-deep)'}}>~12 weeks</div>
            </div>
          </div>

          <div className="row" style={{justifyContent:'space-between', marginTop:24, maxWidth:560}}>
            <button className="btn btn-quiet">← Back</button>
            <div className="row" style={{gap:12}}>
              <span className="muted" style={{fontSize:12.5}}>press <span className="kbd">↵</span></span>
              <button className="btn btn-primary lg">Next: Transcript →</button>
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bar" style={{padding:'13px 64px', borderTop:'1px solid var(--line)'}}>
        <span>Step 3 of 7 · ~2 min remaining</span>
        <span>Every answer is editable later in <b style={{color:'var(--ink-soft)'}}>Settings</b></span>
      </div>
    </div>
  );
}

// ───────────────── B · transcript parse (LLM) ─────────────────
function OnbTranscript() {
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr auto'}}>
      <Topbar />
      <div style={{padding:'32px 56px', display:'grid', gridTemplateColumns:'1fr 1.14fr', gap:36, minHeight:0, alignContent:'start'}}>
        {/* upload */}
        <div className="col" style={{gap:14}}>
          <div className="row" style={{justifyContent:'space-between'}}>
            <Engine kind="llm" />
            <Stepper step={4} total={7} />
          </div>
          <h1 className="t-h1" style={{marginTop:6}}>Drop your transcript in</h1>
          <p className="muted" style={{fontSize:15, maxWidth:460}}>
            We read your GPA and past courses so you don't retype four semesters of grades. AI reads it — you confirm every number.
          </p>

          <div className="drop" style={{marginTop:4}}>
            <div className="ico">↧</div>
            <div className="t-h3">Drop your transcript here</div>
            <div className="muted" style={{fontSize:13, marginTop:5}}>Official or unofficial PDF · stays on your account, never shared</div>
            <div className="row" style={{justifyContent:'center', gap:9, marginTop:18}}>
              <button className="btn btn-ink">Browse files</button>
              <button className="btn btn-ghost">Enter grades by hand</button>
            </div>
          </div>

          <div className="card" style={{padding:'13px 15px', background:'var(--paper-2)', boxShadow:'none'}}>
            <div className="label" style={{marginBottom:9}}>Just uploaded</div>
            <div className="filecard">
              <div className="fileglyph">PDF</div>
              <div style={{flex:1}}>
                <div style={{fontWeight:600, fontSize:14}}>maya_chen_transcript.pdf</div>
                <div className="mono" style={{fontSize:11, color:'var(--muted)', marginTop:2}}>208 KB · 4 semesters · parsed in 1.9s</div>
              </div>
              <span className="chip sage sm">✓ read</span>
              <button className="btn btn-quiet sm">Remove</button>
            </div>
          </div>

          <div className="guard" style={{marginTop:2}}>
            <span className="lk">🔒</span>
            <span>Grades stay private to your account and are never used for model training. Delete the file any time.</span>
          </div>
        </div>

        {/* extracted review */}
        <div className="card raise" style={{padding:'20px 24px', alignSelf:'start'}}>
          <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
            <span className="eyebrow">Extracted from your transcript</span>
            <span className="chip clay sm">AI · please review</span>
          </div>
          <h2 className="t-h2" style={{marginTop:9}}>Do these grades look right?</h2>
          <p className="muted" style={{fontSize:13.5, marginTop:3}}>Edit anything before continuing — nothing is saved until you confirm.</p>

          {/* GPA stats */}
          <div className="row" style={{gap:10, marginTop:15, alignItems:'stretch'}}>
            <div className="field" style={{flex:1}}>
              <div className="fl">Unweighted</div>
              <div className="t-h1" style={{marginTop:4}}>3.8<span style={{fontSize:15, color:'var(--muted)', fontFamily:'var(--sans)'}}> /4.0</span></div>
            </div>
            <div className="field" style={{flex:1}}>
              <div className="fl">Weighted</div>
              <div className="t-h1" style={{marginTop:4, color:'var(--clay-deep)'}}>4.12<span style={{fontSize:15, color:'var(--muted)', fontFamily:'var(--sans)'}}> /5.0</span></div>
            </div>
            <div className="field" style={{flex:1.1}}>
              <div className="fl">Class rank</div>
              <div style={{fontWeight:600, fontSize:13.5, marginTop:9, lineHeight:1.3}}>School doesn't rank</div>
            </div>
          </div>

          {/* course history */}
          <div className="field" style={{marginTop:10}}>
            <div className="row" style={{justifyContent:'space-between'}}>
              <div className="fl">Course history</div>
              <span className="muted" style={{fontSize:12.5}}>edit</span>
            </div>
            <div className="col" style={{gap:8, marginTop:10}}>
              <div className="row" style={{gap:7, alignItems:'center', flexWrap:'wrap'}}>
                <span className="chip sm" style={{minWidth:62, justifyContent:'center', background:'var(--paper-2)'}}>Grade 10</span>
                <span className="chip on sm">Chem H · A−</span>
                <span className="chip sm">Eng 10 · B+</span>
                <span className="chip on sm">Alg II · A</span>
                <span className="chip sm">World Hist · A−</span>
              </div>
              <div className="row" style={{gap:7, alignItems:'center', flexWrap:'wrap'}}>
                <span className="chip sm" style={{minWidth:62, justifyContent:'center', background:'var(--paper-2)'}}>Grade 9</span>
                <span className="chip on sm">Bio H · A</span>
                <span className="chip sm">Eng 9 · B+</span>
                <span className="chip sm">Geometry · A−</span>
                <span className="chip on sm">Spanish II · A</span>
              </div>
            </div>
          </div>

          {/* rigor + trajectory */}
          <div className="row" style={{gap:10, marginTop:10, alignItems:'stretch'}}>
            <div className="field" style={{flex:1}}>
              <div className="fl">Rigor so far</div>
              <div style={{fontWeight:600, fontSize:13.5, marginTop:7}}>2 Honors · 0 AP completed</div>
            </div>
            <div className="field" style={{flex:1, background:'var(--sage-soft)', borderColor:'#cfe0cf'}}>
              <div className="fl" style={{color:'var(--sage-deep)'}}>Trajectory</div>
              <div style={{fontWeight:600, fontSize:13.5, marginTop:7, color:'var(--sage-deep)'}}>Trending up ↗ 3.6 → 3.9</div>
            </div>
          </div>

          {/* inferred */}
          <div className="field flag" style={{marginTop:10}}>
            <div className="row" style={{justifyContent:'space-between'}}>
              <div className="fl" style={{color:'var(--clay-deep)'}}>Inferred</div>
              <span className="chip clay sm" style={{padding:'2px 8px'}}>a guess</span>
            </div>
            <div style={{fontSize:13, color:'var(--clay-deep)', marginTop:7, lineHeight:1.45}}>
              Course rigor is your biggest lever — few advanced classes so far. Your current AP Biology is a strong step up; we'll plan to protect that grade.
            </div>
          </div>

          <div className="row" style={{justifyContent:'space-between', marginTop:16}}>
            <button className="btn btn-quiet">← Back</button>
            <div className="row" style={{gap:9}}>
              <button className="btn btn-soft">Looks wrong, redo</button>
              <button className="btn btn-primary">Confirm &amp; continue →</button>
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bar" style={{padding:'13px 56px', borderTop:'1px solid var(--line)'}}>
        <span>Step 4 of 7 · AI reads, you confirm</span>
        <span>Next: your current courses</span>
      </div>
    </div>
  );
}

// ───────────────── C · activities parse (LLM) ─────────────────
function OnbResume() {
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr auto'}}>
      <Topbar />
      <div style={{padding:'34px 56px', display:'grid', gridTemplateColumns:'1fr 1.08fr', gap:36, minHeight:0, alignContent:'start'}}>
        {/* upload */}
        <div className="col" style={{gap:14}}>
          <div className="row" style={{justifyContent:'space-between'}}>
            <Engine kind="llm" />
            <Stepper step={6} total={7} />
          </div>
          <h1 className="t-h1" style={{marginTop:6}}>Drop your activities list in</h1>
          <p className="muted" style={{fontSize:15, maxWidth:460}}>
            This is the one place setup uses AI — it reads your résumé or activities list so you don't retype your activities, courses, and goals.
          </p>

          <div className="drop" style={{marginTop:4}}>
            <div className="ico">↧</div>
            <div className="t-h3">Drop a file here</div>
            <div className="muted" style={{fontSize:13, marginTop:5}}>PDF, DOCX or TXT · stays on your account, never shared</div>
            <div className="row" style={{justifyContent:'center', gap:9, marginTop:18}}>
              <button className="btn btn-ink">Browse files</button>
              <button className="btn btn-ghost">Paste Common App activities</button>
            </div>
          </div>

          <div className="card" style={{padding:'13px 15px', background:'var(--paper-2)', boxShadow:'none'}}>
            <div className="label" style={{marginBottom:9}}>Just uploaded</div>
            <div className="filecard">
              <div className="fileglyph">PDF</div>
              <div style={{flex:1}}>
                <div style={{fontWeight:600, fontSize:14}}>maya_chen_activities.pdf</div>
                <div className="mono" style={{fontSize:11, color:'var(--muted)', marginTop:2}}>112 KB · parsed in 1.4s</div>
              </div>
              <span className="chip sage sm">✓ read</span>
              <button className="btn btn-quiet sm">Remove</button>
            </div>
          </div>

          <div className="guard" style={{marginTop:2}}>
            <span className="lk">🔒</span>
            <span>Your file isn't shared with other users and is never used for model training. Delete it any time.</span>
          </div>
        </div>

        {/* extracted review */}
        <div className="card raise" style={{padding:'22px 24px', alignSelf:'start'}}>
          <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
            <span className="eyebrow">Extracted from your resume</span>
            <span className="chip clay sm">AI · please review</span>
          </div>
          <h2 className="t-h2" style={{marginTop:10}}>Does this look right?</h2>
          <p className="muted" style={{fontSize:13.5, marginTop:3}}>Edit anything before continuing — nothing is saved until you confirm.</p>

          <div className="col" style={{gap:9, marginTop:16}}>
            {/* Profile */}
            <div className="field">
              <div className="row" style={{justifyContent:'space-between'}}>
                <div className="fl">Profile</div>
                <span className="muted" style={{fontSize:12.5}}>edit</span>
              </div>
              <div style={{fontWeight:600, fontSize:15, marginTop:4}}>11th grade · Class of 2027</div>
              <div className="row" style={{flexWrap:'wrap', gap:7, marginTop:8}}>
                <span className="chip sm">Fall 2027 entry</span>
                <span className="chip sm">Regular Decision</span>
                <span className="chip sm">Intended major · Biology (Pre-med)</span>
              </div>
            </div>

            {/* Activities & leadership */}
            <div className="field">
              <div className="fl">Activities &amp; leadership</div>
              <div className="row" style={{flexWrap:'wrap', gap:7, marginTop:8}}>
                <span className="chip sm">Biology Club · member</span>
                <span className="chip sm">Hospital volunteer · 40 hrs</span>
                <span className="chip sm">Café barista · part-time</span>
                <span className="chip dashed sm">+ add</span>
              </div>
            </div>

            {/* Personal projects — required, currently thin */}
            <div className="field" style={{background:'var(--gold-soft)', borderColor:'#ecd9b6'}}>
              <div className="row" style={{justifyContent:'space-between'}}>
                <div className="fl" style={{color:'#8a6322'}}>Personal projects</div>
                <span className="chip gold sm" style={{padding:'2px 9px'}}>required</span>
              </div>
              <div className="row" style={{flexWrap:'wrap', gap:7, marginTop:8}}>
                <span className="chip sm">Health-tips Instagram · 600 followers</span>
                <span className="chip dashed sm" style={{borderColor:'#d9b878', color:'#8a6322'}}>+ add a project</span>
              </div>
              <div style={{fontSize:12.5, color:'#8a6322', marginTop:8, lineHeight:1.45}}>
                Add one self-started project — independent research, a health-awareness initiative, a portfolio. A clear “spike” stands out most in holistic review.
              </div>
            </div>

            {/* Strengths — theme tags, not skills */}
            <div className="field">
              <div className="fl">Strengths <span style={{textTransform:'none', letterSpacing:0, color:'var(--muted-2)'}}>(auto-detected)</span></div>
              <div className="row" style={{flexWrap:'wrap', gap:7, marginTop:8}}>
                <span className="chip sage sm">STEM curiosity</span>
                <span className="chip sage sm">Service-minded</span>
                <span className="chip sage sm">Steady academics</span>
              </div>
            </div>

            {/* Inferred weak spots */}
            <div className="field flag">
              <div className="row" style={{justifyContent:'space-between'}}>
                <div className="fl" style={{color:'var(--clay-deep)'}}>Inferred weak spots</div>
                <span className="chip clay sm" style={{padding:'2px 8px'}}>a guess</span>
              </div>
              <div className="row" style={{flexWrap:'wrap', gap:7, marginTop:8}}>
                <span className="chip sm">Course rigor — few APs</span>
                <span className="chip sm">No clear spike yet</span>
                <span className="chip sm">Leadership — member, not officer</span>
                <span className="chip sm">Essays not started</span>
              </div>
              <div style={{fontSize:12.5, color:'var(--clay-deep)', marginTop:8}}>We'll keep an eye on these as you plan.</div>
            </div>
          </div>

          <div className="row" style={{justifyContent:'space-between', marginTop:20}}>
            <button className="btn btn-quiet">← Back</button>
            <div className="row" style={{gap:9}}>
              <button className="btn btn-soft">Looks wrong, redo</button>
              <button className="btn btn-primary">Confirm &amp; continue →</button>
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bar" style={{padding:'13px 56px', borderTop:'1px solid var(--line)'}}>
        <span>Step 6 of 7 · AI reads, you confirm</span>
        <span>You're always shown what was extracted before it's used</span>
      </div>
    </div>
  );
}

// ───────────────── D · current courses + grades (deterministic) ─────────────────
function OnbSkills() {
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr auto'}}>
      <Topbar />
      <div style={{padding:'30px 56px', minHeight:0, alignContent:'start', display:'grid', gap:16}}>
        <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
          <Engine kind="det" />
          <Stepper step={5} total={7} />
        </div>
        <h1 className="t-h1" style={{marginTop:4}}>Your courses this term</h1>
        <p className="muted" style={{fontSize:15, marginTop:2, maxWidth:680}}>
          We pulled this term from your transcript — no AI here. Set an honest expected grade for each; we protect study time around the hard ones.
        </p>

        {/* current courses + expected grades */}
        <div className="card" style={{padding:'8px 22px 18px'}}>
          <div style={{display:'grid', gridTemplateColumns:'1.7fr 0.8fr 1fr 1.1fr', gap:14, padding:'14px 10px 9px', borderBottom:'1px solid var(--line)'}}>
            <span className="fl">Course</span>
            <span className="fl">Level</span>
            <span className="fl">Expected grade</span>
            <span className="fl">Focus</span>
          </div>
          {[
            {c:'AP Biology',       lvl:'AP',     lc:'chip clay-solid sm', g:'A−', focus:'okay'},
            {c:'Chemistry Honors', lvl:'Honors', lc:'chip gold sm',       g:'B+', focus:'needs work'},
            {c:'English 11',       lvl:'CP',     lc:'chip sm',            g:'B',  focus:'needs work'},
            {c:'Algebra II',       lvl:'CP',     lc:'chip sm',            g:'A',  focus:'strong'},
            {c:'US History',       lvl:'CP',     lc:'chip sm',            g:'A−', focus:'okay'},
            {c:'Spanish III',      lvl:'CP',     lc:'chip sm',            g:'A',  focus:'strong'},
          ].map((r) => {
            const fc = r.focus === 'needs work' ? 'chip clay sm' : r.focus === 'strong' ? 'chip on sm' : 'chip sm';
            return (
              <div key={r.c} style={{display:'grid', gridTemplateColumns:'1.7fr 0.8fr 1fr 1.1fr', gap:14, padding:'9px 10px', alignItems:'center', borderBottom:'1px solid var(--line)'}}>
                <span style={{fontWeight:600, fontSize:14.5}}>{r.c}</span>
                <span><span className={r.lc}>{r.lvl}</span></span>
                <span><span className="chip sm" style={{fontFamily:'var(--serif)', fontWeight:600, fontSize:14, minWidth:40, justifyContent:'center'}}>{r.g}</span></span>
                <span><span className={fc}>{r.focus}</span></span>
              </div>
            );
          })}
          <div style={{padding:'12px 10px 2px'}}>
            <span className="chip dashed sm">+ add a course</span>
          </div>
        </div>

        <div className="row" style={{justifyContent:'space-between', alignItems:'center', marginTop:-2}}>
          <div className="row" style={{gap:18}}>
            <span className="row" style={{gap:7, fontSize:13, color:'var(--ink-soft)'}}>
              <span style={{fontFamily:'var(--serif)', fontSize:18, fontWeight:600}}>6</span> courses · 1 AP
            </span>
            <span className="row" style={{gap:7, fontSize:13, color:'var(--ink-soft)'}}>
              Projected term GPA <b style={{fontFamily:'var(--serif)', fontSize:17, color:'var(--clay-deep)'}}>3.7</b>
            </span>
          </div>
          <div className="chip clay">⚑ We'll protect time for Chemistry Honors &amp; English 11</div>
        </div>
      </div>

      <div className="footer-bar" style={{padding:'13px 56px', borderTop:'1px solid var(--line)'}}>
        <span>Step 5 of 7 · all deterministic</span>
        <div className="row" style={{gap:10}}>
          <button className="btn btn-quiet sm">← Back</button>
          <button className="btn btn-primary sm">Next: Activities upload →</button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { OnbDeadline, OnbTranscript, OnbResume, OnbSkills });
