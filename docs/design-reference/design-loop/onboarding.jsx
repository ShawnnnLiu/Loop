// Onboarding — hi-fi (Loop · interview-prep & job-search scheduler)
// Deterministic wizard with ONE LLM step: parsing the user's resume.
// Screens: Goal (det) · Deadline (det) · Skills & cadence (det) · Resume parse (LLM, centerpiece).

function Topbar() {
  return (
    <div className="tb">
      <div className="brand">
        <span className="glyph">L</span>
        <span className="word">Loop</span>
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
    <div className="col" style={{gap:8, alignItems:'flex-start'}}>
      <span className="mono" style={{fontSize:12, fontWeight:600, color:'var(--muted)'}}>Step {step} / {total}</span>
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

const STEPS = ['Goal','Hours','Deadline','Skills','Resume','Targets','Connect'];

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

// ───────────────── 1 · Stage, field & goal (deterministic) ─────────────────
const STAGES = ['High school', 'College', "Master's", 'PhD', 'Graduated', 'Working'];
const IN_SCHOOL = ['High school', 'College', "Master's", 'PhD'];

const MAJORS = [
  'Computer Science', 'Computer Engineering', 'Software Engineering', 'Electrical Engineering',
  'Data Science', 'Information Systems', 'Cybersecurity', 'Mathematics', 'Statistics',
  'Applied Mathematics', 'Cognitive Science', 'Computational Biology', 'Physics',
  'Mechanical Engineering', 'Robotics', 'Design / HCI', 'Game Design', 'Economics',
  'Business / Finance', 'Information Technology', 'Undecided',
];
const JOB_STATUS = [
  'Software engineer', 'Backend / infra engineer', 'Full-stack developer', 'Frontend engineer',
  'ML / AI engineer', 'Data scientist / analyst', 'DevOps / SRE', 'Mobile developer',
  'Career switcher', 'Bootcamp graduate', 'Recently graduated', 'Freelance / contract',
  'Founder / building',
];

function ScrollPicker({ items, value, onPick, query, onQuery, placeholder }) {
  const filtered = items.filter((i) => i.toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="card" style={{padding:0, overflow:'hidden', display:'flex', flexDirection:'column', height:300}}>
      <div style={{padding:'10px 12px', borderBottom:'1px solid var(--line)', display:'flex', alignItems:'center', gap:8, flex:'none'}}>
        <span style={{color:'var(--muted-2)', fontSize:14}}>⌕</span>
        <input value={query} onChange={(e) => onQuery(e.target.value)} placeholder={placeholder}
          style={{border:'none', outline:'none', background:'transparent', font:'inherit', fontSize:14, width:'100%', color:'var(--ink)'}} />
      </div>
      <div style={{overflow:'auto', flex:1, padding:'6px'}}>
        {filtered.length === 0 && <div className="muted" style={{padding:'14px 10px', fontSize:13}}>No match — “{query}” will be saved as-is.</div>}
        {filtered.map((i) => {
          const on = i === value;
          return (
            <button key={i} onClick={() => onPick(i)} style={{
              display:'flex', alignItems:'center', justifyContent:'space-between', width:'100%',
              textAlign:'left', border:'none', cursor:'pointer', borderRadius:8, padding:'9px 11px',
              font:'inherit', fontSize:14, fontWeight: on ? 600 : 500,
              color: on ? 'var(--clay-deep)' : 'var(--ink-soft)',
              background: on ? 'var(--clay-tint)' : 'transparent',
            }}>
              {i}{on && <span style={{color:'var(--clay)'}}>✓</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function OnbGoal() {
  const [stage, setStage] = React.useState('College');
  const [major, setMajor] = React.useState('Computer Science');
  const [job, setJob] = React.useState('Software engineer');
  const [query, setQuery] = React.useState('');
  const [goal, setGoal] = React.useState('');
  const inSchool = IN_SCHOOL.includes(stage);

  const fieldLabel = stage === 'High school' ? 'Preferred major'
    : inSchool ? 'Major / field of study'
    : 'Current role / status';
  const goalPlaceholder = inSchool
    ? 'e.g. Land a summer 2026 backend internship at an infra-focused company, and get comfortable with system design.'
    : 'e.g. Move from a mid-level role into a senior backend position within 6 months, focusing on distributed systems.';

  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr auto'}}>
      <Topbar />
      <div style={{display:'grid', gridTemplateColumns:'232px 1fr', minHeight:0}}>
        <div style={{padding:'30px 22px', borderRight:'1px solid var(--line)', display:'flex', flexDirection:'column', gap:18}}>
          <Stepper step={1} total={7} />
          <StepRail active={1} />
          <div className="spacer" />
          <div className="card soft" style={{padding:'13px 15px'}}>
            <div className="label" style={{marginBottom:6}}>Why a plain form?</div>
            <div style={{fontSize:12.5, color:'var(--ink-soft)', lineHeight:1.5}}>
              Simple questions don't need a model. Forms are faster, predictable, and never hallucinate an answer.
            </div>
            <div className="divider" style={{margin:'12px 0'}}></div>
            <div className="label" style={{marginBottom:8}}>AI is used only to</div>
            <div className="col" style={{gap:6, alignItems:'flex-start'}}>
              <span className="chip clay sm">read your résumé</span>
              <span className="chip clay sm">draft your prep plan</span>
            </div>
          </div>
        </div>

        <div style={{padding:'34px 56px 24px', display:'grid', gridTemplateColumns:'1fr', gap:18, alignContent:'start'}}>
          <div>
            <Engine kind="det" />
            <h1 className="t-h1" style={{marginTop:13}}>What are you aiming for?</h1>
            <p className="muted" style={{fontSize:15, maxWidth:620, marginTop:3}}>
              Tell us where you are and what you want — this shapes every milestone the planner builds.
            </p>
          </div>

          {/* stage of life */}
          <div>
            <div className="label" style={{marginBottom:10}}>Stage of life</div>
            <div className="row" style={{gap:9, flexWrap:'wrap'}}>
              {STAGES.map((s) => (
                <button key={s} onClick={() => { setStage(s); setQuery(''); }}
                  className={'chip ' + (s === stage ? 'clay-solid' : '') + ' lg'}
                  style={{cursor:'pointer'}}>{s}</button>
              ))}
            </div>
          </div>

          {/* conditional field + goal */}
          <div style={{display:'grid', gridTemplateColumns:'minmax(320px, 1fr) 1.15fr', gap:22, alignItems:'start'}}>
            {/* major OR job-status picker */}
            <div>
              <div className="row" style={{justifyContent:'space-between', marginBottom:10, alignItems:'baseline'}}>
                <div className="label">{fieldLabel}</div>
                <span className="muted" style={{fontSize:12}}>{inSchool ? 'scroll or search' : 'we say “graduated,” never “unemployed”'}</span>
              </div>
              {inSchool
                ? <ScrollPicker items={MAJORS} value={major} onPick={setMajor} query={query} onQuery={setQuery} placeholder="Search majors…" />
                : <ScrollPicker items={JOB_STATUS} value={job} onPick={setJob} query={query} onQuery={setQuery} placeholder="Search roles…" />}
            </div>

            {/* free-text goal */}
            <div>
              <div className="row" style={{justifyContent:'space-between', marginBottom:10, alignItems:'baseline'}}>
                <div className="label">Your goal — in your words</div>
                <span className="muted" style={{fontSize:12}}>plain text</span>
              </div>
              <textarea value={goal} onChange={(e) => setGoal(e.target.value)} placeholder={goalPlaceholder}
                style={{
                  width:'100%', height:158, resize:'none', borderRadius:14, border:'1px solid var(--line-2)',
                  background:'var(--card)', padding:'15px 17px', font:'inherit', fontSize:15.5, lineHeight:1.55,
                  color:'var(--ink)', outline:'none', boxSizing:'border-box',
                }} />
              <div className="row" style={{gap:8, marginTop:12, flexWrap:'wrap', alignItems:'center'}}>
                <span className="muted" style={{fontSize:12}}>Need a starting point?</span>
                {['Crack FAANG interviews', 'Get interview-ready in 12 weeks', 'Switch into backend'].map((ex) => (
                  <button key={ex} onClick={() => setGoal(ex)} className="chip dashed sm" style={{cursor:'pointer'}}>{ex}</button>
                ))}
              </div>
            </div>
          </div>

          <div className="row" style={{justifyContent:'space-between', marginTop:4}}>
            <button className="btn btn-quiet">← Back</button>
            <div className="row" style={{gap:12}}>
              <span className="muted" style={{fontSize:12.5}}>press <span className="kbd">↵</span></span>
              <button className="btn btn-primary lg">Next: Time budget →</button>
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bar" style={{padding:'13px 56px', borderTop:'1px solid var(--line)'}}>
        <span>Step 1 of 7 · ~3 min remaining</span>
        <span>Every answer is editable later in <b style={{color:'var(--ink-soft)'}}>Settings</b></span>
      </div>
    </div>
  );
}

// ───────────────── 3 · Deadline (deterministic) ─────────────────
function OnbDeadline() {
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr auto'}}>
      <Topbar />
      <div style={{display:'grid', gridTemplateColumns:'232px 1fr', minHeight:0}}>
        <div style={{padding:'30px 22px', borderRight:'1px solid var(--line)', display:'flex', flexDirection:'column', gap:18}}>
          <Stepper step={3} total={7} />
          <StepRail active={3} />
          <div className="spacer" />
          <div className="card soft" style={{padding:'13px 15px'}}>
            <div className="label" style={{marginBottom:6}}>Why a plain form?</div>
            <div style={{fontSize:12.5, color:'var(--ink-soft)', lineHeight:1.5}}>
              Picking a date is a fact, not a guess. We back-plan deterministically so the runway is exact.
            </div>
            <div className="divider" style={{margin:'12px 0'}}></div>
            <div className="label" style={{marginBottom:8}}>AI is used only to</div>
            <div className="col" style={{gap:6, alignItems:'flex-start'}}>
              <span className="chip clay sm">read your résumé</span>
              <span className="chip clay sm">draft your prep plan</span>
            </div>
          </div>
        </div>

        <div style={{padding:'44px 64px', display:'grid', gridTemplateColumns:'1fr', gap:8, alignContent:'start', maxWidth:760}}>
          <Engine kind="det" />
          <h1 className="t-display" style={{marginTop:14}}>When do you want to be interview-ready?</h1>
          <p className="muted" style={{fontSize:16, maxWidth:520, marginTop:2}}>
            We back-plan every milestone — DSA, system design, behavioral, applications — from this date.
          </p>

          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, marginTop:20, maxWidth:560}}>
            {[
              {k:'Sprint', v:'In 4 weeks', sub:'a specific onsite coming up'},
              {k:'Balanced', v:'In 12 weeks', sub:'recruiting season', on:true},
              {k:'Long runway', v:'In 6 months', sub:'start early, steady'},
              {k:'Custom', v:'Pick a date →', sub:'OA / onsite deadline', dashed:true},
            ].map((o) => (
              <div key={o.k} className="card" style={{
                padding:'16px 18px',
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
              <div className="t-h2" style={{marginTop:3}}>May 4, 2026</div>
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
              <button className="btn btn-primary lg">Next: Skills →</button>
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

// ───────────────── 4 · Skills & cadence (deterministic) ─────────────────
function OnbSkills() {
  const TOPICS = [
    {t:'Arrays & strings', lvl:'strong'},
    {t:'Hashing', lvl:'strong'},
    {t:'Two pointers', lvl:'ok'},
    {t:'Trees', lvl:'ok'},
    {t:'Graphs', lvl:'weak'},
    {t:'Dynamic programming', lvl:'weak'},
    {t:'System design', lvl:'weak'},
    {t:'Concurrency', lvl:'ok'},
    {t:'SQL', lvl:'ok'},
    {t:'Behavioral / STAR', lvl:'weak'},
  ];
  const lvlClass = (l) => l === 'weak' ? 'chip clay sm' : l === 'strong' ? 'chip on sm' : 'chip sm';
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr auto'}}>
      <Topbar />
      <div style={{padding:'30px 56px', minHeight:0, alignContent:'start', display:'grid', gap:16}}>
        <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
          <Engine kind="det" />
          <Stepper step={4} total={7} />
        </div>
        <h1 className="t-h1" style={{marginTop:4}}>Rate yourself &amp; set your cadence</h1>
        <p className="muted" style={{fontSize:15, marginTop:2, maxWidth:720}}>
          Tap each topic to set weak / ok / strong — no AI here. We pre-filled a few from your résumé; we protect more time for the weak ones.
        </p>

        <div style={{display:'grid', gridTemplateColumns:'1.5fr 1fr', gap:18, alignItems:'start'}}>
          {/* skill self-rating */}
          <div className="card" style={{padding:'16px 20px 20px'}}>
            <div className="row" style={{justifyContent:'space-between'}}>
              <div className="label">Skill self-rating</div>
              <div className="row" style={{gap:8}}>
                <span className="chip on sm">strong</span>
                <span className="chip sm">ok</span>
                <span className="chip clay sm">weak</span>
              </div>
            </div>
            <div className="row" style={{flexWrap:'wrap', gap:8, marginTop:14}}>
              {TOPICS.map((r) => (
                <span key={r.t} className={lvlClass(r.lvl)}>{r.t} · {r.lvl}</span>
              ))}
              <span className="chip dashed sm">+ topic</span>
            </div>
            <div className="divider" style={{margin:'16px 0 12px'}}></div>
            <div className="row" style={{gap:18}}>
              <span className="row" style={{gap:7, fontSize:13, color:'var(--ink-soft)'}}>
                <span style={{fontFamily:'var(--serif)', fontSize:18, fontWeight:600, color:'var(--clay-deep)'}}>3</span> weak areas to protect
              </span>
              <span className="chip clay">⚑ Graphs, DP &amp; system design get priority blocks</span>
            </div>
          </div>

          {/* cadence column */}
          <div className="col" style={{gap:14}}>
            <div className="card" style={{padding:'15px 17px'}}>
              <div className="row" style={{justifyContent:'space-between'}}>
                <div className="label">Hours per week</div>
                <div className="t-h4" style={{color:'var(--clay-deep)'}}>~15 hrs</div>
              </div>
              <div className="slider" style={{marginTop:14}}>
                <div className="fill" style={{width:'58%'}}></div>
                <div className="knob" style={{left:'58%'}}></div>
              </div>
              <div className="row" style={{justifyContent:'space-between', marginTop:8}}>
                <span className="muted" style={{fontSize:12}}>2</span>
                <span className="muted" style={{fontSize:12}}>25</span>
              </div>
            </div>

            <div className="card" style={{padding:'15px 17px'}}>
              <div className="label" style={{marginBottom:10}}>Accountability</div>
              <div className="col" style={{gap:8}}>
                <div className="opt"><span>Self only</span><span className="ring"></span></div>
                <div className="opt on"><span>Weekly check-in</span><span className="ring"></span></div>
                <div className="opt"><span>Peer / mentor (opt-in)</span><span className="ring"></span></div>
              </div>
            </div>

            <div className="card" style={{padding:'15px 17px'}}>
              <div className="label" style={{marginBottom:10}}>Quiet hours</div>
              <div className="row" style={{gap:8}}>
                <span className="chip sm" style={{fontFamily:'var(--mono)'}}>11pm</span>
                <span className="muted">→</span>
                <span className="chip sm" style={{fontFamily:'var(--mono)'}}>9am</span>
                <span className="spacer"></span>
                <span className="chip on sm">no Sun grind</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bar" style={{padding:'13px 56px', borderTop:'1px solid var(--line)'}}>
        <span>Step 4 of 7 · all deterministic</span>
        <div className="row" style={{gap:10}}>
          <button className="btn btn-quiet sm">← Back</button>
          <button className="btn btn-primary sm">Next: Résumé upload →</button>
        </div>
      </div>
    </div>
  );
}

// ───────────────── 5 · Resume parse (LLM) — centerpiece ─────────────────
function OnbResume() {
  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr auto'}}>
      <Topbar />
      <div style={{padding:'34px 56px', display:'grid', gridTemplateColumns:'1fr 1.08fr', gap:36, minHeight:0, alignContent:'start'}}>
        {/* upload */}
        <div className="col" style={{gap:14}}>
          <div className="row" style={{justifyContent:'space-between'}}>
            <Engine kind="llm" />
            <Stepper step={5} total={7} />
          </div>
          <h1 className="t-h1" style={{marginTop:6}}>Drop your résumé</h1>
          <p className="muted" style={{fontSize:15, maxWidth:460}}>
            This is the one place setup uses AI — it reads your résumé so you don't retype your stack, experience, and target companies. AI reads it; you confirm every field.
          </p>

          <div className="drop" style={{marginTop:4}}>
            <div className="ico">↧</div>
            <div className="t-h3">Drop your résumé here</div>
            <div className="muted" style={{fontSize:13, marginTop:5}}>PDF, DOCX or TXT · stays on your account, never shared</div>
            <div className="row" style={{justifyContent:'center', gap:9, marginTop:18}}>
              <button className="btn btn-ink">Browse files</button>
              <button className="btn btn-ghost">Paste LinkedIn URL</button>
              <button className="btn btn-quiet">Skip →</button>
            </div>
          </div>

          <div className="card" style={{padding:'13px 15px', background:'var(--paper-2)', boxShadow:'none'}}>
            <div className="label" style={{marginBottom:9}}>Just uploaded</div>
            <div className="filecard">
              <div className="fileglyph">PDF</div>
              <div style={{flex:1}}>
                <div style={{fontWeight:600, fontSize:14}}>maya_chen_resume.pdf</div>
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
            <span className="eyebrow">Extracted from your résumé</span>
            <span className="chip clay sm">AI · please review</span>
          </div>
          <h2 className="t-h2" style={{marginTop:10}}>Does this look right?</h2>
          <p className="muted" style={{fontSize:13.5, marginTop:3}}>We extracted these — edit anything wrong before continuing. Nothing is saved until you confirm.</p>

          <div className="col" style={{gap:9, marginTop:16}}>
            {/* role */}
            <div className="field">
              <div className="row" style={{justifyContent:'space-between'}}>
                <div className="fl">Role</div>
                <span className="muted" style={{fontSize:12.5}}>edit</span>
              </div>
              <div style={{fontWeight:600, fontSize:15, marginTop:4}}>CS senior · graduating May 2026</div>
            </div>

            {/* experience */}
            <div className="field">
              <div className="fl">Experience</div>
              <div className="row" style={{flexWrap:'wrap', gap:7, marginTop:8}}>
                <span className="chip sm">Backend intern · Stripe</span>
                <span className="chip sm">RA · NLP lab</span>
                <span className="chip dashed sm">+ add</span>
              </div>
            </div>

            {/* stack */}
            <div className="field">
              <div className="fl">Stack <span style={{textTransform:'none', letterSpacing:0, color:'var(--muted-2)'}}>(auto)</span></div>
              <div className="row" style={{flexWrap:'wrap', gap:7, marginTop:8}}>
                <span className="chip on sm">python</span>
                <span className="chip on sm">go</span>
                <span className="chip on sm">postgres</span>
                <span className="chip on sm">react</span>
                <span className="chip sm">aws</span>
                <span className="chip sm">redis</span>
              </div>
            </div>

            {/* inferred weak spots */}
            <div className="field flag">
              <div className="row" style={{justifyContent:'space-between'}}>
                <div className="fl" style={{color:'var(--clay-deep)'}}>Inferred weak spots</div>
                <span className="chip clay sm" style={{padding:'2px 8px'}}>a guess</span>
              </div>
              <div className="row" style={{flexWrap:'wrap', gap:7, marginTop:8}}>
                <span className="chip sm">graphs</span>
                <span className="chip sm">DP</span>
                <span className="chip sm">system design</span>
              </div>
              <div style={{fontSize:12.5, color:'var(--clay-deep)', marginTop:8, lineHeight:1.45}}>
                A guess from your projects &amp; coursework — you'll confirm these on the next step.
              </div>
            </div>

            {/* target companies */}
            <div className="field">
              <div className="fl">Target companies <span style={{textTransform:'none', letterSpacing:0, color:'var(--muted-2)'}}>(auto)</span></div>
              <div className="row" style={{flexWrap:'wrap', gap:7, marginTop:8}}>
                <span className="chip sm">FAANG-tier</span>
                <span className="chip sm">Infra startups</span>
                <span className="chip dashed sm">+ add</span>
              </div>
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
        <span>Step 5 of 7 · this is the AI step</span>
        <span>You're always shown what was extracted before it's used</span>
      </div>
    </div>
  );
}

// ───────────────── 2 · Time budget & constraints (deterministic) ─────────────────
function Stepit({ value, onBump }) {
  return (
    <div className="step">
      <button onClick={() => onBump(-1)} aria-label="decrease">−</button>
      <span className="val">{value}</span>
      <button onClick={() => onBump(1)} aria-label="increase">+</button>
    </div>
  );
}
function Swt({ on, onClick }) {
  return <button className={'swt' + (on ? ' on' : '')} onClick={onClick}><span className="dot"></span></button>;
}
function FieldStepper({ label, unit, value, onBump }) {
  return (
    <div>
      <div className="label" style={{marginBottom:7}}>{label}{unit ? <span style={{textTransform:'none', letterSpacing:0, color:'var(--muted-2)', fontWeight:500}}> ({unit})</span> : null}</div>
      <Stepit value={value} onBump={onBump} />
    </div>
  );
}

function OnbBudget() {
  const DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const [n, setN] = React.useState({ weeks:4, weekly:28, pref:60, maxlen:120, maxdaily:180, minbreak:30 });
  const [days, setDays] = React.useState({ Mon:true, Tue:true, Wed:true, Thu:true, Fri:true, Sat:false, Sun:false });
  const [weekends, setWeekends] = React.useState(false);
  const [prefs, setPrefs] = React.useState({ evening:true, longblocks:false, avoidB2B:true });

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const bump = (key, d, lo, hi) => setN((s) => ({ ...s, [key]: clamp(s[key] + d, lo, hi) }));
  const toggleDay = (d) => setDays((s) => ({ ...s, [d]: !s[d] }));
  const selectedDays = DAYS.filter((d) => days[d]).length;

  return (
    <div className="app" style={{gridTemplateRows:'auto 1fr auto'}}>
      <Topbar />
      <div style={{padding:'14px 56px 12px', minHeight:0, overflow:'auto', display:'grid', gap:11, alignContent:'start'}}>
        <div className="row" style={{justifyContent:'space-between', alignItems:'center'}}>
          <Engine kind="det" />
          <Stepper step={2} total={7} />
        </div>
        <div>
          <h1 className="t-h1" style={{lineHeight:1.05}}>Set your time budget &amp; constraints</h1>
          <p className="muted" style={{fontSize:14.5, marginTop:4, maxWidth:760}}>
            All deterministic — these rules bound how the planner schedules every block. No AI: the scheduler obeys them exactly.
          </p>
        </div>

        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, alignItems:'start'}}>
          {/* LEFT COLUMN */}
          <div className="col" style={{gap:13}}>
            {/* time budget */}
            <div className="card" style={{padding:'15px 18px'}}>
              <div className="label" style={{marginBottom:13}}>Time budget</div>
              <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:'16px 18px'}}>
                <FieldStepper label="Timeline" unit="weeks" value={n.weeks} onBump={(d) => bump('weeks', d, 1, 52)} />
                <FieldStepper label="Weekly hours" value={n.weekly} onBump={(d) => bump('weekly', d, 1, 60)} />
                <FieldStepper label="Preferred session" unit="min" value={n.pref} onBump={(d) => bump('pref', d * 15, 15, 180)} />
                <FieldStepper label="Max session" unit="min" value={n.maxlen} onBump={(d) => bump('maxlen', d * 15, 30, 240)} />
              </div>
            </div>

            {/* deep-work windows */}
            <div className="card" style={{padding:'15px 18px'}}>
              <div className="label" style={{marginBottom:6}}>Deep-work windows</div>
              <p className="muted" style={{fontSize:12.5, lineHeight:1.5, marginBottom:13}}>
                Pick the weekdays you can do focused work — the time range applies to each selected day. Leave blank to skip.
              </p>
              <div className="row" style={{gap:7, flexWrap:'wrap'}}>
                {DAYS.map((d) => (
                  <button key={d} onClick={() => toggleDay(d)} className={'chip ' + (days[d] ? 'clay-solid' : '') + ' sm'} style={{cursor:'pointer', minWidth:46, justifyContent:'center'}}>{d}</button>
                ))}
              </div>
              <div className="row" style={{gap:18, marginTop:16}}>
                <div>
                  <div className="label" style={{marginBottom:7}}>Start</div>
                  <div className="tfield"><span>06:00 PM</span><span className="ar">▾</span></div>
                </div>
                <div style={{alignSelf:'center', color:'var(--muted-2)', marginTop:18}}>→</div>
                <div>
                  <div className="label" style={{marginBottom:7}}>End</div>
                  <div className="tfield"><span>09:00 PM</span><span className="ar">▾</span></div>
                </div>
                <div className="spacer"></div>
                <div style={{alignSelf:'flex-end', marginBottom:9}}>
                  <span className="chip sage sm">{selectedDays} day{selectedDays===1?'':'s'} · 3h each</span>
                </div>
              </div>
            </div>

            {/* timezone */}
            <div className="card" style={{padding:'15px 18px'}}>
              <div className="label" style={{marginBottom:11}}>Timezone</div>
              <div className="row" style={{gap:12, alignItems:'center'}}>
                <div className="tfield" style={{minWidth:200}}><span>UTC</span><span className="ar">▾</span></div>
                <span className="muted" style={{fontSize:12}}>IANA — e.g. America/Los_Angeles, Europe/London</span>
              </div>
            </div>
          </div>

          {/* RIGHT COLUMN */}
          <div className="col" style={{gap:13}}>
            {/* hard constraints */}
            <div className="card" style={{padding:'15px 18px'}}>
              <div className="label" style={{marginBottom:6}}>Hard constraints</div>
              <div className="cfg-row">
                <div><div className="cl">No events before</div></div>
                <div className="tfield"><span>08:00 AM</span><span className="ar">▾</span></div>
              </div>
              <div className="cfg-row">
                <div><div className="cl">No events after</div></div>
                <div className="tfield"><span>10:30 PM</span><span className="ar">▾</span></div>
              </div>
              <div className="cfg-row">
                <div><div className="cl">Max daily study</div><div className="cs">caps total minutes per day</div></div>
                <Stepit value={n.maxdaily} onBump={(d) => bump('maxdaily', d * 30, 30, 600)} />
              </div>
              <div className="cfg-row">
                <div><div className="cl">Min break between deep blocks</div><div className="cs">minutes of recovery</div></div>
                <Stepit value={n.minbreak} onBump={(d) => bump('minbreak', d * 15, 0, 120)} />
              </div>
              <div className="cfg-row">
                <div><div className="cl">Allow weekends</div><div className="cs">schedule blocks Sat / Sun</div></div>
                <Swt on={weekends} onClick={() => setWeekends((v) => !v)} />
              </div>
            </div>

            {/* preferences */}
            <div className="card" style={{padding:'15px 18px'}}>
              <div className="label" style={{marginBottom:6}}>Preferences</div>
              <div className="muted" style={{fontSize:12, marginBottom:4}}>Soft — the planner honors them when it can.</div>
              {[
                {k:'evening', t:'Prefer evening sessions', s:'weight blocks toward later in the day'},
                {k:'longblocks', t:'Prefer weekend long blocks', s:'batch deep work on Sat / Sun'},
                {k:'avoidB2B', t:'Avoid back-to-back deep work', s:'insert breaks between focus blocks'},
              ].map((p) => (
                <div key={p.k} className="cfg-row">
                  <div><div className="cl">{p.t}</div><div className="cs">{p.s}</div></div>
                  <Swt on={prefs[p.k]} onClick={() => setPrefs((s) => ({ ...s, [p.k]: !s[p.k] }))} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bar" style={{padding:'13px 56px', borderTop:'1px solid var(--line)'}}>
        <span>Step 2 of 7 · all deterministic · {n.weekly} hrs/wk over {n.weeks} wks</span>
        <div className="row" style={{gap:10}}>
          <button className="btn btn-quiet sm">← Back</button>
          <button className="btn btn-primary">Save profile &amp; continue →</button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { OnbGoal, OnbDeadline, OnbSkills, OnbResume, OnbBudget, Topbar, Stepper, Engine, StepRail });
